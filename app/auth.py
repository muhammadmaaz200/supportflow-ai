import hashlib
import hmac
import secrets
import sqlite3
from .config import DB_PATH

DEMO_USERS = {
    "admin@supportflow.local": ("admin", "Admin@123"),
    "user@supportflow.local": ("user", "User@123"),
}


def _hash(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 160_000).hex()
    return salt, digest


def init_auth_db():
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','user')),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    for email, (role, password) in DEMO_USERS.items():
        row = con.execute("SELECT id FROM auth_users WHERE email=?", (email,)).fetchone()
        if not row:
            salt, digest = _hash(password)
            con.execute(
                "INSERT INTO auth_users(email,password_hash,salt,role) VALUES (?,?,?,?)",
                (email, digest, salt, role),
            )
    con.commit()
    con.close()


def authenticate(email: str, password: str):
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT id,email,password_hash,salt,role FROM auth_users WHERE lower(email)=lower(?)",
        (email.strip(),),
    ).fetchone()
    con.close()
    if not row:
        return None
    candidate = _hash(password, row[3])[1]
    if hmac.compare_digest(row[2], candidate):
        return {"id": row[0], "email": row[1], "role": row[4]}
    return None
