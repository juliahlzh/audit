import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base, SessionLocal, engine
from app.seed import seed_data
from app.services.sample_loader import load_sample_file


DATASETS = {
    "uji": ROOT / "sample_data" / "fews_uji.csv",
    "realistis": ROOT / "sample_data" / "fews_realistis.csv",
}


def main():
    parser = argparse.ArgumentParser(description="Muat data sintetis FEWS secara idempoten.")
    parser.add_argument("dataset", choices=["uji", "realistis", "semua"])
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_data(db)
        selected = DATASETS.values() if args.dataset == "semua" else [DATASETS[args.dataset]]
        for path in selected:
            result = load_sample_file(db, path)
            print(f"{result['source']}: {result['inserted']} baris baru")
    finally:
        db.close()


if __name__ == "__main__":
    main()
