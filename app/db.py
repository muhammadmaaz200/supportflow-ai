import os
import sqlite3
import json
from pathlib import Path


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel filesystem is read-only except /tmp
IS_VERCEL = os.getenv("VERCEL") == "1"

if IS_VERCEL:
    RUNTIME_DIR = Path("/tmp/supportflow")
else:
    RUNTIME_DIR = BASE_DIR / "data"

RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = RUNTIME_DIR / "supportflow.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# SERIALIZATION HELPER
# ============================================================

def serialize(value):
    """
    Convert Python dictionaries/lists into SQLite-safe strings.
    """

    if value is None:
        return None

    if isinstance(value, (dict, list, tuple)):
        return json.dumps(
            value,
            ensure_ascii=False
        )

    return str(value)


# ============================================================
# ANALYSIS HELPER
# ============================================================

def add_analysis_fields(item):
    """
    Extract sentiment, emotion, urgency and escalation
    from the JSON stored in the analysis column.

    This keeps the existing database structure while making
    the fields available to the dashboard/frontend.
    """

    item["sentiment"] = "neutral"
    item["emotion"] = "neutral"
    item["urgency"] = "normal"
    item["escalated"] = False

    analysis = item.get("analysis")

    if not analysis:
        return item

    try:

        # Analysis is already a dictionary
        if isinstance(analysis, dict):
            analysis_data = analysis

        # Analysis is stored as JSON string
        else:
            analysis_data = json.loads(analysis)

        item["sentiment"] = analysis_data.get(
            "sentiment",
            "neutral"
        )

        item["emotion"] = analysis_data.get(
            "emotion",
            "neutral"
        )

        item["urgency"] = analysis_data.get(
            "urgency",
            "normal"
        )

        item["escalated"] = analysis_data.get(
            "escalated",
            analysis_data.get(
                "escalation",
                False
            )
        )

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError
    ):

        item["sentiment"] = "neutral"
        item["emotion"] = "neutral"
        item["urgency"] = "normal"
        item["escalated"] = False

    return item


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():

    with get_connection() as con:

        # ----------------------------------------------------
        # Conversations
        # ----------------------------------------------------

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_email TEXT,
                message TEXT NOT NULL,
                answer TEXT NOT NULL,
                analysis TEXT,
                sources TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # DATABASE MIGRATION
        # ----------------------------------------------------

        conversation_columns = {
            row["name"]
            for row in con.execute(
                "PRAGMA table_info(conversations)"
            ).fetchall()
        }

        if "user_id" not in conversation_columns:

            con.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN user_id INTEGER
                """
            )

        if "user_email" not in conversation_columns:

            con.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN user_email TEXT
                """
            )

        if "analysis" not in conversation_columns:

            con.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN analysis TEXT
                """
            )

        if "sources" not in conversation_columns:

            con.execute(
                """
                ALTER TABLE conversations
                ADD COLUMN sources TEXT DEFAULT '[]'
                """
            )

        # ----------------------------------------------------
        # Audit Logs
        # ----------------------------------------------------

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                action TEXT,
                details TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # Knowledge Base
        # ----------------------------------------------------

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT UNIQUE NOT NULL,
                chunks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # Escalations
        # ----------------------------------------------------

        con.execute(
            """
            CREATE TABLE IF NOT EXISTS escalations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL,
                user_id INTEGER,
                user_email TEXT,
                reason TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # ----------------------------------------------------
        # Escalation Migration
        # ----------------------------------------------------

        escalation_columns = {
            row["name"]
            for row in con.execute(
                "PRAGMA table_info(escalations)"
            ).fetchall()
        }

        if "conversation_id" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN conversation_id INTEGER
                """
            )

        if "user_id" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN user_id INTEGER
                """
            )

        if "user_email" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN user_email TEXT
                """
            )

        if "reason" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN reason TEXT
                """
            )

        if "status" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN status TEXT DEFAULT 'open'
                """
            )

        if "created_at" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN created_at TEXT
                """
            )

        if "updated_at" not in escalation_columns:

            con.execute(
                """
                ALTER TABLE escalations
                ADD COLUMN updated_at TEXT
                """
            )

        con.commit()


# ============================================================
# AUDIT
# ============================================================

def audit(
    user_email,
    action,
    details="",
    status="success"
):
    """
    Save an audit event.
    """

    with get_connection() as con:

        con.execute(
            """
            INSERT INTO audit_logs
            (
                user_email,
                action,
                details,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                serialize(user_email),
                serialize(action),
                serialize(details),
                serialize(status)
            )
        )

        con.commit()


# ============================================================
# SAVE CONVERSATION
# ============================================================

def save_conversation(
    user,
    message,
    answer,
    analysis=None,
    sources=None
):
    """
    Save customer/AI conversation.
    """

    user_id = None
    user_email = None

    if isinstance(user, dict):

        user_id = user.get("id")

        user_email = (
            user.get("email")
            or user.get("username")
            or user.get("name")
        )

    elif isinstance(user, int):

        user_id = user

    elif user is not None:

        user_email = str(user)

    analysis = serialize(analysis)
    sources = serialize(sources)

    with get_connection() as con:

        cursor = con.execute(
            """
            INSERT INTO conversations
            (
                user_id,
                user_email,
                message,
                answer,
                analysis,
                sources
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user_email,
                str(message),
                str(answer),
                analysis,
                sources
            )
        )

        con.commit()

        return cursor.lastrowid


# ============================================================
# USER CONVERSATIONS
# ============================================================

def user_conversations(
    user_id,
    limit=100
):
    """
    Get conversations belonging to one user.
    """

    with get_connection() as con:

        rows = con.execute(
            """
            SELECT *
            FROM conversations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit
            )
        ).fetchall()

    results = []

    for row in rows:

        item = dict(row)

        item = add_analysis_fields(item)

        results.append(item)

    return results


# ============================================================
# ALL CONVERSATIONS
# ============================================================

def all_conversations(
    limit=500
):
    """
    Get all conversations for admin panel.
    """

    with get_connection() as con:

        rows = con.execute(
            """
            SELECT *
            FROM conversations
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            )
        ).fetchall()

    results = []

    for row in rows:

        item = dict(row)

        item = add_analysis_fields(item)

        results.append(item)

    return results


# ============================================================
# DASHBOARD
# ============================================================

def dashboard():

    with get_connection() as con:

        total_conversations = con.execute(
            """
            SELECT COUNT(*)
            FROM conversations
            """
        ).fetchone()[0]

        total_users = con.execute(
            """
            SELECT COUNT(
                DISTINCT user_id
            )
            FROM conversations
            WHERE user_id IS NOT NULL
            """
        ).fetchone()[0]

        total_knowledge = con.execute(
            """
            SELECT COUNT(*)
            FROM knowledge
            """
        ).fetchone()[0]

        total_chunks = con.execute(
            """
            SELECT COALESCE(
                SUM(chunks),
                0
            )
            FROM knowledge
            """
        ).fetchone()[0]

        open_escalations = con.execute(
            """
            SELECT COUNT(*)
            FROM escalations
            WHERE status IN (
                'open',
                'in_progress'
            )
            """
        ).fetchone()[0]

        total_escalations = con.execute(
            """
            SELECT COUNT(*)
            FROM escalations
            """
        ).fetchone()[0]

        total_audits = con.execute(
            """
            SELECT COUNT(*)
            FROM audit_logs
            """
        ).fetchone()[0]

    return {
        "total_conversations": total_conversations,
        "total_users": total_users,
        "total_knowledge": total_knowledge,
        "total_documents": total_knowledge,
        "total_chunks": total_chunks,
        "open_escalations": open_escalations,
        "total_escalations": total_escalations,
        "total_audits": total_audits
    }


# ============================================================
# AUDIT ROWS
# ============================================================

def audit_rows(
    limit=200
):
    """
    Get audit logs for admin panel.
    """

    with get_connection() as con:

        rows = con.execute(
            """
            SELECT *
            FROM audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            )
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SAVE KNOWLEDGE
# ============================================================

def save_knowledge(
    filename,
    chunks
):
    """
    Add/update knowledge-base document.
    """

    with get_connection() as con:

        con.execute(
            """
            INSERT INTO knowledge
            (
                filename,
                chunks
            )
            VALUES (?, ?)

            ON CONFLICT(filename)
            DO UPDATE SET
                chunks = excluded.chunks
            """,
            (
                str(filename),
                int(chunks)
            )
        )

        con.commit()


# ============================================================
# CREATE ESCALATION
# ============================================================

def create_escalation(
    conversation_id,
    user,
    reason
):
    """
    Create a human-support escalation.
    """

    user_id = None
    user_email = None

    if isinstance(user, dict):

        user_id = user.get("id")

        user_email = (
            user.get("email")
            or user.get("username")
            or user.get("name")
        )

    elif isinstance(user, int):

        user_id = user

    elif user is not None:

        user_email = str(user)

    with get_connection() as con:

        cursor = con.execute(
            """
            INSERT INTO escalations
            (
                conversation_id,
                user_id,
                user_email,
                reason,
                status
            )
            VALUES (?, ?, ?, ?, 'open')
            """,
            (
                conversation_id,
                user_id,
                user_email,
                str(reason)
            )
        )

        con.commit()

        return cursor.lastrowid


# ============================================================
# GET ESCALATIONS
# ============================================================

def escalations(
    limit=200
):

    with get_connection() as con:

        rows = con.execute(
            """
            SELECT *
            FROM escalations
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                limit,
            )
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# UPDATE ESCALATION
# ============================================================

def update_escalation(
    escalation_id,
    status
):

    with get_connection() as con:

        cursor = con.execute(
            """
            UPDATE escalations
            SET
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                escalation_id
            )
        )

        con.commit()

        return cursor.rowcount > 0


# ============================================================
# GET ONE ESCALATION
# ============================================================

def get_escalation(
    escalation_id
):

    with get_connection() as con:

        row = con.execute(
            """
            SELECT *
            FROM escalations
            WHERE id = ?
            """,
            (
                escalation_id,
            )
        ).fetchone()

    if row is None:
        return None

    return dict(row)


# ============================================================
# GET KNOWLEDGE DOCUMENTS
# ============================================================

def knowledge_rows():

    with get_connection() as con:

        rows = con.execute(
            """
            SELECT *
            FROM knowledge
            ORDER BY filename ASC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]