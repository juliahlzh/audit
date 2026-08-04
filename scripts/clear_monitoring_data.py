"""Hapus data monitoring FEWS tanpa menyentuh akun dan master organisasi."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402
from app.services.branch_inputs import count_orphan_matching_results, purge_monitoring_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="Wajib diisi untuk menjalankan penghapusan")
    args = parser.parse_args()
    if not args.confirm:
        print("Tidak ada perubahan. Jalankan ulang dengan --confirm.")
        return 2

    db = SessionLocal()
    try:
        users_before = db.query(User).count()
        counts = purge_monitoring_data(db)
        users_after = db.query(User).count()
        payload = {
            "deleted": counts,
            "users_before": users_before,
            "users_after": users_after,
            "orphan_matching_results": count_orphan_matching_results(db),
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        if users_before != users_after or payload["orphan_matching_results"] != 0:
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
