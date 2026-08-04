"""Benchmark reproducible untuk alur upload FEWS sebanyak 22.000 baris."""

from io import BytesIO
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.auth import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import BranchInput, MatchingResult, User  # noqa: E402


ROW_COUNT = 22_000


def build_csv() -> bytes:
    output = BytesIO()
    output.write(b"tgl_bukubesar,kodelokasi,keterangan_dr_lokasi,jumlah_biaya,jumlah_setor,idunix,bank\n")
    for index in range(ROW_COUNT):
        output.write(f"2026-08-04,278,Load {index},1000,1000,LOAD-{index},transfer\n".encode("utf-8"))
    return output.getvalue()


def main() -> int:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    session.add(User(username="admin", full_name="Load Test", password_hash=hash_password("admin123"), role="admin"))
    session.commit()

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    started = perf_counter()
    response = client.post(
        "/branch-inputs/upload",
        files={"excel_file": ("load-22000.csv", build_csv(), "text/csv")},
        follow_redirects=False,
    )
    elapsed = perf_counter() - started
    result = {
        "rows_requested": ROW_COUNT,
        "active_rows": session.query(BranchInput).filter(BranchInput.archived_at.is_(None)).count(),
        "matching_results": session.query(MatchingResult).count(),
        "status_code": response.status_code,
        "elapsed_seconds": round(elapsed, 3),
    }
    print(json.dumps(result, sort_keys=True))
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()
    return 0 if result["active_rows"] == ROW_COUNT and result["matching_results"] == ROW_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
