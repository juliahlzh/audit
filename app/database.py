import os
import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "storage"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "fews_dana_masuk.db"

try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Vercel serverless filesystem read-only di source directory.
    DATA_DIR = Path("/tmp/fews_storage")
    UPLOAD_DIR = DATA_DIR / "uploads"
    DB_PATH = DATA_DIR / "fews_dana_masuk.db"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DB_RUNTIME_LABEL = str(DB_PATH)
raw_database_url = os.getenv("DATABASE_URL", "").strip()
IS_VERCEL_RUNTIME = bool(os.getenv("VERCEL") or os.getenv("VERCEL_ENV"))
DB_IS_PERSISTENT = False
DB_KIND = "SQLite lokal"


def _normalize_database_url(url: str) -> str:
    # Vercel/Supabase kadang menyediakan skema postgres://
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+" not in url.split("://", 1)[0]:
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def _sqlite_file_writable(path: Path) -> bool:
    try:
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE IF NOT EXISTS __healthcheck (id INTEGER)")
        conn.execute("DROP TABLE IF EXISTS __healthcheck")
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error:
        return False


if raw_database_url:
    DATABASE_URL = _normalize_database_url(raw_database_url)
    DB_RUNTIME_LABEL = "external DATABASE_URL"
    DB_IS_PERSISTENT = True
    DB_KIND = "Postgres/Supabase"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
elif _sqlite_file_writable(DB_PATH):
    DATABASE_URL = f"sqlite:///{DB_PATH}"
    DB_IS_PERSISTENT = not IS_VERCEL_RUNTIME
    DB_KIND = "SQLite sementara" if IS_VERCEL_RUNTIME else "SQLite lokal"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # Fallback untuk environment yang tidak mengizinkan file-lock SQLite.
    DATABASE_URL = "sqlite+pysqlite:///:memory:"
    DB_RUNTIME_LABEL = "in-memory (fallback)"
    DB_IS_PERSISTENT = False
    DB_KIND = "SQLite sementara"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
