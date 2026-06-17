from pathlib import Path
import shutil

from ..config import POPPLER_PATH, TESSERACT_CMD
from ..database import DATABASE_URL, DB_IS_PERSISTENT, DB_KIND, DB_RUNTIME_LABEL, IS_VERCEL_RUNTIME, UPLOAD_DIR, raw_database_url


def _tesseract_ready():
    if Path(TESSERACT_CMD).exists():
        return True, f"Tesseract ditemukan di {TESSERACT_CMD}"
    if shutil.which("tesseract"):
        return True, "Tesseract ditemukan di PATH"
    return False, "Tesseract belum ditemukan. OCR gambar akan fallback ke manual verification."


def _poppler_ready():
    if POPPLER_PATH and Path(POPPLER_PATH).exists():
        return True, f"Poppler ditemukan di {POPPLER_PATH}"
    return False, "Poppler belum diset. PDF scan masih bisa dibaca jika PDF berisi teks, tetapi OCR PDF scan bisa terbatas."


def build_database_status(database_url: str, runtime_label: str, raw_database_url: str, is_vercel: bool):
    is_external = bool(raw_database_url)
    is_persistent = is_external or (database_url.startswith("sqlite:///") and not is_vercel)

    if is_external:
        return {
            "name": "Database Postgres/Supabase",
            "ok": True,
            "message": "Database permanen aktif melalui DATABASE_URL. Data upload, hasil deteksi, dan follow-up akan tersimpan lintas logout/restart.",
        }

    if is_vercel:
        return {
            "name": "Database SQLite sementara",
            "ok": False,
            "message": "Database production belum aktif. Data dapat hilang jika aplikasi restart. Set DATABASE_URL Supabase/Postgres di Vercel.",
        }

    return {
        "name": "Database SQLite Lokal",
        "ok": is_persistent,
        "message": f"Database lokal aktif di {runtime_label}. Data tersimpan di laptop ini, tetapi belum menjadi database online bersama.",
    }


def get_system_status():
    tesseract_ok, tesseract_message = _tesseract_ready()
    poppler_ok, poppler_message = _poppler_ready()
    database_status = build_database_status(DATABASE_URL, DB_RUNTIME_LABEL, raw_database_url, IS_VERCEL_RUNTIME)
    return [
        database_status,
        {"name": "Folder Upload", "ok": UPLOAD_DIR.exists(), "message": f"Upload directory: {UPLOAD_DIR}"},
        {"name": "Tesseract OCR", "ok": tesseract_ok, "message": tesseract_message},
        {"name": "Poppler PDF", "ok": poppler_ok, "message": poppler_message},
    ]


def get_database_warning() -> str | None:
    if DB_IS_PERSISTENT:
        return None
    if IS_VERCEL_RUNTIME:
        return "Database production belum aktif. Data dapat hilang jika aplikasi restart. Hubungkan Supabase/Postgres melalui DATABASE_URL."
    if DB_KIND == "SQLite sementara":
        return "Database sementara aktif. Data dapat hilang saat aplikasi ditutup/restart."
    return None
