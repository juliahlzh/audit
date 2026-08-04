from datetime import datetime

from sqlalchemy.orm import Session

from ..models import (
    AuditLog,
    BankMutation,
    BranchInput,
    MatchingResult,
    RiskIndicatorResult,
    Transaction,
)


def archive_branch_input_with_results(db: Session, branch_input_id: int, user_id: int | None = None, reason: str = "") -> bool:
    row = db.query(BranchInput).filter(BranchInput.id == branch_input_id, BranchInput.archived_at.is_(None)).first()
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
    now = datetime.utcnow()
    archive_reason = reason or "Arsip/koreksi semua data approval"
    archived_count = (
        db.query(BranchInput)
        .filter(BranchInput.archived_at.is_(None))
        .update(
            {
                BranchInput.archived_at: now,
                BranchInput.correction_reason: archive_reason,
                BranchInput.correction_notes: archive_reason,
            },
            synchronize_session=False,
        )
    )
    db.add(
        AuditLog(
            user_id=user_id,
            action="Arsip/Koreksi Semua Data Approval",
            status="WARNING",
            notes=f"{archived_count} data approval diarsipkan. Alasan: {archive_reason}",
        )
    )
    db.commit()
    return archived_count


def restore_branch_input_with_results(db: Session, branch_input_id: int, user_id: int | None = None) -> bool:
    row = db.query(BranchInput).filter(BranchInput.id == branch_input_id, BranchInput.archived_at.is_not(None)).first()
    if not row:
        return False

    now = datetime.utcnow()
    (
        db.query(BranchInput)
        .filter(
            BranchInput.id != row.id,
            BranchInput.invoice_code == row.invoice_code,
            BranchInput.archived_at.is_(None),
        )
        .update(
            {
                BranchInput.archived_at: now,
                BranchInput.correction_reason: f"Digantikan oleh restore data #{row.id}",
                BranchInput.correction_notes: "Versi aktif sebelumnya dipindahkan ke arsip secara otomatis.",
            },
            synchronize_session=False,
        )
    )
    row.archived_at = None
    db.add(
        AuditLog(
            user_id=user_id,
            action="Restore Data Approval",
            status="INFO",
            notes=f"Data approval #{branch_input_id} dipulihkan dari arsip.",
        )
    )
    db.commit()
    return True


def permanently_delete_branch_input_with_results(
    db: Session, branch_input_id: int, user_id: int | None = None
) -> bool:
    """Hapus data arsip beserta hasil matching dalam satu transaksi."""
    row = db.query(BranchInput).filter(BranchInput.id == branch_input_id, BranchInput.archived_at.is_not(None)).first()
    if not row:
        return False

    deleted_results = (
        db.query(MatchingResult)
        .filter(MatchingResult.branch_input_id == branch_input_id)
        .delete(synchronize_session=False)
    )
    db.delete(row)
    db.add(
        AuditLog(
            user_id=user_id,
            action="Hapus Permanen Data Approval",
            status="WARNING",
            notes=f"Data approval #{branch_input_id} dan {deleted_results} hasil matching dihapus permanen.",
        )
    )
    db.commit()
    return True


def count_orphan_matching_results(db: Session) -> int:
    return (
        db.query(MatchingResult)
        .outerjoin(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .outerjoin(BankMutation, MatchingResult.bank_mutation_id == BankMutation.id)
        .filter(
            (MatchingResult.branch_input_id.is_not(None) & BranchInput.id.is_(None))
            | (MatchingResult.bank_mutation_id.is_not(None) & BankMutation.id.is_(None))
            | (MatchingResult.branch_input_id.is_(None) & MatchingResult.bank_mutation_id.is_(None))
        )
        .count()
    )


def purge_monitoring_data(db: Session) -> dict[str, int]:
    """Bersihkan data operasional tanpa menyentuh user, role, konfigurasi, atau master organisasi."""
    counts = {
        "matching_results": db.query(MatchingResult).delete(synchronize_session=False),
        "branch_inputs": db.query(BranchInput).delete(synchronize_session=False),
        "bank_mutations": db.query(BankMutation).delete(synchronize_session=False),
        "risk_indicator_results": db.query(RiskIndicatorResult).delete(synchronize_session=False),
    }
    db.query(AuditLog).filter(AuditLog.transaction_id.is_not(None)).update(
        {AuditLog.transaction_id: None}, synchronize_session=False
    )
    counts["transactions"] = db.query(Transaction).delete(synchronize_session=False)
    db.commit()
    return counts


def delete_branch_input_with_results(db: Session, branch_input_id: int) -> bool:
    return permanently_delete_branch_input_with_results(db, branch_input_id)


def delete_all_branch_inputs_with_results(db: Session) -> int:
    return archive_all_branch_inputs_with_results(db, reason="Koreksi semua dari tombol hapus lama")
