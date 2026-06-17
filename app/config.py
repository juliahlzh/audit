import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
HOST = os.getenv("FEWS_HOST", "127.0.0.1")
PORT = int(os.getenv("FEWS_PORT", "8000"))
RELOAD = os.getenv("FEWS_RELOAD", "false").lower() in {"1", "true", "yes"}
SESSION_SECRET = os.getenv("FEWS_SESSION_SECRET", "fews-local-" + secrets.token_hex(16))
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
POPPLER_PATH = os.getenv("POPPLER_PATH", "")
