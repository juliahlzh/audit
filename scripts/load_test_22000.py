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
from app.services.branch_inputs import count_orphan_matching_results  # noqa: E402


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
    upload_elapsed = perf_counter() - started
    uploaded_rows = session.query(BranchInput).filter(BranchInput.archived_at.is_(None)).count()
    uploaded_results = session.query(MatchingResult).count()

    archive_started = perf_counter()
    archive_response = client.post("/branch-inputs/delete-all", follow_redirects=False)
    archive_elapsed = perf_counter() - archive_started

    delete_started = perf_counter()
    delete_response = client.post(
        "/archives/delete-all",
        data={"confirmation": "DELETE_ALL_ARCHIVES"},
        follow_redirects=False,
    )
    delete_elapsed = perf_counter() - delete_started
    result = {
        "rows_requested": ROW_COUNT,
        "uploaded_rows": uploaded_rows,
        "uploaded_results": uploaded_results,
        "upload_status_code": response.status_code,
        "upload_elapsed_seconds": round(upload_elapsed, 3),
        "archive_status_code": archive_response.status_code,
        "archive_elapsed_seconds": round(archive_elapsed, 3),
        "delete_status_code": delete_response.status_code,
        "delete_elapsed_seconds": round(delete_elapsed, 3),
        "remaining_rows": session.query(BranchInput).count(),
        "remaining_results": session.query(MatchingResult).count(),
        "orphan_results": count_orphan_matching_results(session),
    }
    print(json.dumps(result, sort_keys=True))
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()
    return (
        0
        if result["uploaded_rows"] == ROW_COUNT
        and result["uploaded_results"] == ROW_COUNT
        and result["remaining_rows"] == 0
        and result["remaining_results"] == 0
        and result["orphan_results"] == 0
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
