from datetime import datetime

from sqlalchemy.orm import Session

from ..models import AuditLog, BranchInput


def archive_branch_input_with_results(db: Session, branch_input_id: int, user_id: int | None = None, reason: str = "") -> bool:
    row = db.query(BranchInput).filter(BranchInput.id == branch_input_id).first()
    if not row:
        return False

    now = datetime.utcnow()
    row.archived_at = now
    row.correction_reason = reason or "Arsip/koreksi data approval"
    row.correction_notes = reason or row.correction_notes
    db.add(
        AuditLog(
            user_id=user_id,
            action="Arsip/Koreksi Data Approval",
            status="WARNING",
            notes=f"Data approval #{branch_input_id} diarsipkan. Alasan: {row.correction_reason}",
        )
    )
    db.commit()
    return True


def archive_all_branch_inputs_with_results(db: Session, user_id: int | None = None, reason: str = "") -> int:
    rows = db.query(BranchInput).filter(BranchInput.archived_at.is_(None)).all()
    now = datetime.utcnow()
    archive_reason = reason or "Arsip/koreksi semua data approval"
    for row in rows:
        row.archived_at = now
        row.correction_reason = archive_reason
        row.correction_notes = archive_reason
    db.add(
        AuditLog(
            user_id=user_id,
            action="Arsip/Koreksi Semua Data Approval",
            status="WARNING",
            notes=f"{len(rows)} data approval diarsipkan. Alasan: {archive_reason}",
        )
    )
    db.commit()
    return len(rows)


def delete_branch_input_with_results(db: Session, branch_input_id: int) -> bool:
    return archive_branch_input_with_results(db, branch_input_id, reason="Koreksi dari tombol hapus lama")


def delete_all_branch_inputs_with_results(db: Session) -> int:
    return archive_all_branch_inputs_with_results(db, reason="Koreksi semua dari tombol hapus lama")
