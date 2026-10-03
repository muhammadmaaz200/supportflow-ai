import os
from pathlib import Path
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# Detect Vercel environment
IS_VERCEL = os.getenv("VERCEL") == "1"


# --------------------------------------------------
# Database
# --------------------------------------------------

if IS_VERCEL:
    # Vercel filesystem is read-only except /tmp
    DB_PATH = Path(
        os.getenv(
            "SUPPORTFLOW_DB",
            "/tmp/supportflow.db"
        )
    )
else:
    DB_PATH = Path(
        os.getenv(
            "SUPPORTFLOW_DB",
            str(BASE_DIR / "data" / "supportflow.db")
        )
    )


# --------------------------------------------------
# Knowledge Base
# --------------------------------------------------

if IS_VERCEL:
    # Temporary writable directory on Vercel
    KB_DIR = Path(
        os.getenv(
            "KB_DIR",
            "/tmp/supportflow_knowledge"
        )
    )
else:
    KB_DIR = Path(
        os.getenv(
            "KB_DIR",
            str(BASE_DIR / "data" / "knowledge")
        )
    )


# --------------------------------------------------
# Upload directory
# --------------------------------------------------

if IS_VERCEL:
    # Vercel allows temporary writes inside /tmp
    UPLOAD_DIR = Path(
        os.getenv(
            "UPLOAD_DIR",
            "/tmp/supportflow_uploads"
        )
    )
else:
    UPLOAD_DIR = Path(
        os.getenv(
            "UPLOAD_DIR",
            str(BASE_DIR / "data" / "uploads")
        )
    )


# --------------------------------------------------
# Session
# --------------------------------------------------

SESSION_SECRET = os.getenv(
    "SESSION_SECRET",
    "change-this-local-secret"
)


# --------------------------------------------------
# Gemini
# --------------------------------------------------

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    ""
).strip()

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)


# --------------------------------------------------
# Create writable directories
# --------------------------------------------------

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