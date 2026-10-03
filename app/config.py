import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("SUPPORTFLOW_DB", str(BASE_DIR / "data" / "supportflow.db")))
KB_DIR = Path(os.getenv("KB_DIR", str(BASE_DIR / "data" / "knowledge")))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "data" / "uploads")))
SESSION_SECRET = os.getenv("SESSION_SECRET", "change-this-local-secret")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
KB_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
