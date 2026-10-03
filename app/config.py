import os
from pathlib import Path
from dotenv import load_dotenv


# ============================================================
# BASE DIRECTORY
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# ============================================================
# VERCEL DETECTION
# ============================================================

IS_VERCEL = os.getenv("VERCEL") == "1"


# ============================================================
# PATH CONFIGURATION
# ============================================================

if IS_VERCEL:

    # Vercel's writable temporary directory
    RUNTIME_DIR = Path("/tmp/supportflow")

    DB_PATH = RUNTIME_DIR / "supportflow.db"
    KB_DIR = RUNTIME_DIR / "knowledge"
    UPLOAD_DIR = RUNTIME_DIR / "uploads"

else:

    RUNTIME_DIR = BASE_DIR / "data"

    DB_PATH = Path(
        os.getenv(
            "SUPPORTFLOW_DB",
            str(RUNTIME_DIR / "supportflow.db")
        )
    )

    KB_DIR = Path(
        os.getenv(
            "KB_DIR",
            str(RUNTIME_DIR / "knowledge")
        )
    )

    UPLOAD_DIR = Path(
        os.getenv(
            "UPLOAD_DIR",
            str(RUNTIME_DIR / "uploads")
        )
    )


# ============================================================
# APPLICATION SETTINGS
# ============================================================

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "change-this-local-secret"
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


# ============================================================
# CREATE WRITABLE DIRECTORIES
# ============================================================

RUNTIME_DIR.mkdir(
    parents=True,
    exist_ok=True
)

DB_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)

KB_DIR.mkdir(
    parents=True,
    exist_ok=True
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)