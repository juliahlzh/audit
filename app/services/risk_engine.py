from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import RiskIndicatorResult, Transaction


@dataclass
class IndicatorOutcome:
    name: str
    score: int
    severity: str
    notes: str


def classify_risk(total_score: int) -> str:
    if total_score >= 10:
        return "Merah"
    if total_score >= 6:
        return "Kuning"
    return "Hijau"


def validation_recommendation(risk_level: str, validation_status: str) -> str:
    if risk_level == "Merah" or validation_status == "Tidak Sesuai":
        return "Perlu audit manual dan penahanan proses pembayaran lanjutan."
    if risk_level == "Kuning" or validation_status == "Perlu Verifikasi":
        return "Lakukan verifikasi dokumen dan approval tambahan."
    return "Monitoring rutin, tidak ada tindakan khusus."


def evaluate_transaction(db: Session, transaction: Transaction):
    outcomes = [
        _check_unusual_amount(db, transaction),
        _check_duplicate_transaction(db, transaction),
        _check_vendor_frequency(db, transaction),
        _check_closing_window(transaction),
        _check_transfer_proof_difference(transaction),
        _check_repeat_applicant(db, transaction),
        _check_unusual_time(transaction),
    ]
    total_score = sum(item.score for item in outcomes)
    risk_level = classify_risk(total_score)
    summary = "; ".join(f"{item.name}: {item.notes}" for item in outcomes if item.score > 1) or "Tidak ada indikator signifikan yang terdeteksi."
    return total_score, risk_level, summary, outcomes


def persist_risk_results(db: Session, transaction: Transaction, outcomes):
    db.query(RiskIndicatorResult).filter(RiskIndicatorResult.transaction_id == transaction.id).delete()
    for item in outcomes:
        db.add(RiskIndicatorResult(transaction_id=transaction.id, indicator_name=item.name, score=item.score, severity=item.severity, notes=item.notes))


def _check_unusual_amount(db: Session, transaction: Transaction):
    avg_amount = db.query(func.avg(Transaction.amount_input)).scalar() or transaction.amount_input
    if transaction.amount_input >= avg_amount * 2:
        return IndicatorOutcome("Nominal tidak wajar", 3, "Risiko tinggi", "Nominal jauh di atas rata-rata historis.")
    if transaction.amount_input >= avg_amount * 1.3:
        return IndicatorOutcome("Nominal tidak wajar", 2, "Waspada", "Nominal lebih tinggi dari rata-rata historis.")
    return IndicatorOutcome("Nominal tidak wajar", 1, "Normal", "Nominal masih dalam pola wajar.")


def _check_duplicate_transaction(db: Session, transaction: Transaction):
    duplicates = db.query(Transaction).filter(
        Transaction.id != transaction.id,
        Transaction.transaction_date == transaction.transaction_date,
        Transaction.vendor_name == transaction.vendor_name,
        Transaction.amount_input == transaction.amount_input,
        Transaction.destination_account == transaction.destination_account,
    ).count()
    if duplicates >= 1:
        return IndicatorOutcome("Transaksi duplikat", 3, "Risiko tinggi", "Terdapat transaksi serupa pada tanggal yang sama.")
    return IndicatorOutcome("Transaksi duplikat", 1, "Normal", "Tidak ditemukan duplikasi identik.")


def _check_vendor_frequency(db: Session, transaction: Transaction):
    vendor_count = db.query(Transaction).filter(Transaction.vendor_name == transaction.vendor_name, Transaction.id != transaction.id).count()
    if vendor_count >= 8:
        return IndicatorOutcome("Frekuensi vendor tinggi", 3, "Risiko tinggi", "Vendor sering muncul pada histori transaksi.")
    if vendor_count >= 4:
        return IndicatorOutcome("Frekuensi vendor tinggi", 2, "Waspada", "Vendor cukup sering digunakan.")
    return IndicatorOutcome("Frekuensi vendor tinggi", 1, "Normal", "Frekuensi vendor masih normal.")


def _check_closing_window(transaction: Transaction):
    day = transaction.transaction_date.day
    if day in {29, 30, 31}:
        return IndicatorOutcome("Transaksi mendekati closing", 3, "Risiko tinggi", "Transaksi dibuat pada akhir bulan.")
    if day >= 26:
        return IndicatorOutcome("Transaksi mendekati closing", 2, "Waspada", "Transaksi mendekati periode closing.")
    return IndicatorOutcome("Transaksi mendekati closing", 1, "Normal", "Bukan periode closing.")


def _check_transfer_proof_difference(transaction: Transaction):
    if transaction.validation_status == "Tidak Sesuai":
        return IndicatorOutcome("Perbedaan bukti transfer", 3, "Risiko tinggi", "Data input dan bukti transfer tidak cocok.")
    if transaction.validation_status == "Perlu Verifikasi":
        return IndicatorOutcome("Perbedaan bukti transfer", 2, "Waspada", "OCR belum cukup yakin, perlu cek manual.")
    return IndicatorOutcome("Perbedaan bukti transfer", 1, "Normal", "Bukti transfer konsisten.")


def _check_repeat_applicant(db: Session, transaction: Transaction):
    same_applicant_count = db.query(Transaction).filter(Transaction.applicant_name == transaction.applicant_name, Transaction.id != transaction.id).count()
    if same_applicant_count >= 8:
        return IndicatorOutcome("Pengajuan berulang oleh user yang sama", 3, "Risiko tinggi", "Pemohon memiliki frekuensi pengajuan tinggi.")
    if same_applicant_count >= 4:
        return IndicatorOutcome("Pengajuan berulang oleh user yang sama", 2, "Waspada", "Pemohon cukup sering mengajukan transaksi.")
    return IndicatorOutcome("Pengajuan berulang oleh user yang sama", 1, "Normal", "Frekuensi pemohon masih wajar.")


def _check_unusual_time(transaction: Transaction):
    hour = transaction.created_at.hour if transaction.created_at else datetime.utcnow().hour
    if hour < 6 or hour >= 22:
        return IndicatorOutcome("Waktu transaksi tidak biasa", 3, "Risiko tinggi", "Transaksi dicatat pada jam tidak biasa.")
    if hour < 8 or hour >= 19:
        return IndicatorOutcome("Waktu transaksi tidak biasa", 2, "Waspada", "Transaksi dicatat di luar jam kerja inti.")
    return IndicatorOutcome("Waktu transaksi tidak biasa", 1, "Normal", "Waktu input masih normal.")
