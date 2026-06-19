"""Jalankan migration FEWS secara eksplisit sebelum deployment production."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import init_db


if __name__ == "__main__":
    init_db()
    print("Migration FEWS selesai.")
