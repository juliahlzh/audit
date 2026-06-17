from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="created_by_user")
    logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    applicant_name: Mapped[str] = mapped_column(String(100), index=True)
    division: Mapped[str] = mapped_column(String(100), index=True)
    expense_type: Mapped[str] = mapped_column(String(100))
    amount_input: Mapped[float] = mapped_column(Float)
    vendor_name: Mapped[str] = mapped_column(String(150), index=True)
    destination_account: Mapped[str] = mapped_column(String(50), index=True)
    source_account: Mapped[str] = mapped_column(String(50))
    proof_file_path: Mapped[str] = mapped_column(String(255))
    proof_file_name: Mapped[str] = mapped_column(String(255))

    ocr_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_transaction_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ocr_bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    validation_status: Mapped[str] = mapped_column(String(30), default="Perlu Verifikasi", index=True)
    validation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="Hijau", index=True)
    risk_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_status: Mapped[str] = mapped_column(String(50), default="Open")

    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user: Mapped[User | None] = relationship("User", back_populates="transactions")
    indicators: Mapped[list["RiskIndicatorResult"]] = relationship(
        "RiskIndicatorResult", back_populates="transaction", cascade="all, delete-orphan"
    )
    logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="transaction", cascade="all, delete-orphan")


class RiskIndicatorResult(Base):
    __tablename__ = "risk_indicator_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"), index=True)
    indicator_name: Mapped[str] = mapped_column(String(120))
    score: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    transaction: Mapped[Transaction] = relationship("Transaction", back_populates="indicators")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(30), default="INFO")
    notes: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    transaction: Mapped[Transaction | None] = relationship("Transaction", back_populates="logs")
    user: Mapped[User | None] = relationship("User", back_populates="logs")


class BranchInput(Base):
    __tablename__ = "branch_inputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    branch_name: Mapped[str] = mapped_column(String(120), index=True)
    customer_name: Mapped[str] = mapped_column(String(150), index=True)
    amount_should_pay: Mapped[float] = mapped_column(Float)
    amount_input_branch: Mapped[float] = mapped_column(Float, index=True)
    payment_method: Mapped[str] = mapped_column(String(30), index=True)
    invoice_code: Mapped[str] = mapped_column(String(100), index=True)
    bank_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    officer_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    deposit_officer_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    approver_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    transaction_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    payment_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deposit_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bank_target: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    proof_bank: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    destination_account: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    proof_reference: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    student_list: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    correction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    correction_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    match_results: Mapped[list["MatchingResult"]] = relationship("MatchingResult", back_populates="branch_input")


class BankMutation(Base):
    __tablename__ = "bank_mutations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    incoming_date: Mapped[date] = mapped_column(Date, index=True)
    sender_name: Mapped[str] = mapped_column(String(150), index=True)
    amount_in: Mapped[float] = mapped_column(Float, index=True)
    company_account: Mapped[str] = mapped_column(String(60), index=True)
    mutation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    match_results: Mapped[list["MatchingResult"]] = relationship("MatchingResult", back_populates="bank_mutation")


class MatchingResult(Base):
    __tablename__ = "matching_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    branch_input_id: Mapped[int | None] = mapped_column(ForeignKey("branch_inputs.id"), nullable=True, index=True)
    bank_mutation_id: Mapped[int | None] = mapped_column(ForeignKey("bank_mutations.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="Low", index=True)
    mismatch_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    nominal_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    name_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    date_gap_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    follow_up_status: Mapped[str] = mapped_column(String(30), default="OPEN", index=True)
    follow_up_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    branch_input: Mapped[BranchInput | None] = relationship("BranchInput", back_populates="match_results")
    bank_mutation: Mapped[BankMutation | None] = relationship("BankMutation", back_populates="match_results")
