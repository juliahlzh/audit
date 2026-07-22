import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
HOST = os.getenv("FEWS_HOST", "127.0.0.1")
PORT = int(os.getenv("FEWS_PORT", "8000"))
RELOAD = os.getenv("FEWS_RELOAD", "false").lower() in {"1", "true", "yes"}
SESSION_SECRET = os.getenv("FEWS_SESSION_SECRET", "fews-local-" + secrets.token_hex(32))
IS_PRODUCTION = os.getenv("FEWS_ENV", "").lower() == "production" or os.getenv("VERCEL_ENV", "").lower() == "production"
SESSION_COOKIE_SECURE = os.getenv("FEWS_COOKIE_SECURE", "true" if IS_PRODUCTION else "false").lower() in {"1", "true", "yes"}
SESSION_MAX_AGE_SECONDS = int(os.getenv("FEWS_SESSION_MAX_AGE", str(8 * 60 * 60)))
MAX_UPLOAD_BYTES = int(os.getenv("FEWS_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
MAX_UPLOAD_ROWS = int(os.getenv("FEWS_MAX_UPLOAD_ROWS", "25000"))
MAX_XLSX_UNCOMPRESSED_BYTES = int(os.getenv("FEWS_MAX_XLSX_UNCOMPRESSED_BYTES", str(100 * 1024 * 1024)))
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
