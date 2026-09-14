from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import math
import os

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ..models import CollectionActivity, CollectionReminder, CollectionTask, User
from .organization import resolve_location


FOLLOW_UP_RESULTS = {
    "Sudah Follow-up",
    "Promise to Pay",
    "Customer sudah bayar",
    "Minta Waktu",
    "Tidak Merespons",
    "Tidak Dapat Dihubungi",
    "Kendala Pembayaran",
    "Lainnya",
}


def reminder_thresholds() -> tuple[int, ...]:
    values = []
    for raw in os.getenv("FEWS_COLLECTION_REMINDER_DAYS", "1,3,7,14").split(","):
        try:
            value = int(raw.strip())
        except ValueError:
            continue
        if value > 0:
            values.append(value)
    return tuple(sorted(set(values))) or (1, 3, 7, 14)


def payment_status(amount_due: float, outstanding: float, due_date: date, today: date | None = None) -> str:
    current = today or date.today()
    if outstanding <= 0:
        return "Paid"
    if due_date < current:
        return "Overdue"
    if outstanding < amount_due:
        return "Partial"
    return "Unpaid"


def overdue_days(task: CollectionTask, today: date | None = None) -> int:
    current = today or date.today()
    if task.payment_status != "Overdue" or task.due_date >= current:
        return 0
    return (current - task.due_date).days


def attention_label(task: CollectionTask, today: date | None = None) -> str:
    if task.payment_status == "Paid":
        return "Resolved"
    days = overdue_days(task, today)
    promise_missed = bool(task.promise_to_pay_date and task.promise_to_pay_date < (today or date.today()))
    no_progress = task.collection_status in {"Belum Follow-up", "Tidak Merespons", "Tidak Dapat Dihubungi"}
    if days >= 14 and no_progress:
        return "Escalation"
    if days >= 7 or promise_missed or (task.reminder_level >= 2 and no_progress):
        return "Needs Attention"
    return "Monitoring"


def next_reminder_level(task: CollectionTask, today: date | None = None) -> int:
    days = overdue_days(task, today)
    reached = sum(1 for threshold in reminder_thresholds() if days >= threshold)
    return min(reached, len(reminder_thresholds()))


def scoped_collection_query(db: Session, user: User):
    query = db.query(CollectionTask)
    if user.region:
        query = query.filter(CollectionTask.region == user.region)
    return query


def refresh_overdue_statuses(db: Session) -> int:
    updated = (
        db.query(CollectionTask)
        .filter(
            CollectionTask.outstanding > 0,
            CollectionTask.due_date < date.today(),
            CollectionTask.payment_status.in_(["Unpaid", "Partial"]),
        )
        .update({CollectionTask.payment_status: "Overdue", CollectionTask.updated_at: datetime.utcnow()}, synchronize_session=False)
    )
    if updated:
        db.commit()
    return updated


def ingest_va_payload(db: Session, payload: dict) -> tuple[CollectionTask, bool]:
    required = ["external_id", "student_id", "student_name", "location", "installment_number", "amount_due", "due_date", "outstanding"]
    missing = [key for key in required if payload.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Field wajib belum lengkap: {', '.join(missing)}")

    location_code, branch_name, region, area = resolve_location(payload["location"])
    if not location_code:
        raise ValueError(f"Kode lokasi SIL '{payload['location']}' tidak dikenal")
    try:
        due_date = date.fromisoformat(str(payload["due_date"])[:10])
        amount_due = float(payload["amount_due"])
        outstanding = float(payload["outstanding"])
        last_payment_at = datetime.fromisoformat(str(payload["last_payment_at"]).replace("Z", "+00:00")).replace(tzinfo=None) if payload.get("last_payment_at") else None
    except (TypeError, ValueError) as exc:
        raise ValueError("Format due_date, nominal, outstanding, atau last_payment_at tidak valid") from exc
    if amount_due < 0 or outstanding < 0:
        raise ValueError("Nominal dan outstanding tidak boleh negatif")

    external_id = str(payload["external_id"]).strip()
    if not external_id or not str(payload["student_id"]).strip() or not str(payload["student_name"]).strip():
        raise ValueError("external_id, student_id, dan student_name tidak boleh kosong")
    if not math.isfinite(amount_due) or not math.isfinite(outstanding):
        raise ValueError("Nominal dan outstanding harus berupa angka terbatas")
    task = db.query(CollectionTask).filter(CollectionTask.external_id == external_id).first()
    created = task is None
    previous_payment_status = task.payment_status if task else None
    if task is None:
        task = CollectionTask(external_id=external_id)
        db.add(task)

    task.student_id = str(payload["student_id"]).strip()
    task.student_name = str(payload["student_name"]).strip()
    task.location_code = location_code
    task.branch_name = branch_name
    task.region = region
    task.area = area
    task.staff_pic = str(payload.get("staff_pic") or "").strip() or None
    task.installment_number = str(payload["installment_number"]).strip()
    task.amount_due = amount_due
    task.due_date = due_date
    task.outstanding = outstanding
    task.last_payment_at = last_payment_at
    task.payment_status = payment_status(amount_due, outstanding, due_date)
    task.updated_at = datetime.utcnow()
    if task.payment_status == "Paid":
        task.collection_status = "Resolved"
        task.next_follow_up_date = None
        task.resolved_at = task.resolved_at or datetime.utcnow()
    elif task.collection_status == "Resolved":
        task.collection_status = "Belum Follow-up"
        task.resolved_at = None
    db.flush()
    if task.payment_status == "Paid" and previous_payment_status != "Paid":
        db.add(
            CollectionActivity(
                task_id=task.id,
                result="Resolved by VA",
                note="Outstanding menjadi nol dari pembaruan pembayaran Virtual Account.",
            )
        )
    return task, created


def collection_summary(db: Session, user: User) -> dict:
    query = scoped_collection_query(db, user)
    overdue = CollectionTask.payment_status == "Overdue"
    totals = query.with_entities(
        func.count(CollectionTask.id),
        func.sum(case((CollectionTask.due_date <= date.today(), 1), else_=0)),
        func.sum(case((CollectionTask.payment_status == "Overdue", 1), else_=0)),
        func.sum(case((CollectionTask.payment_status == "Overdue", CollectionTask.outstanding), else_=0.0)),
        func.sum(case((CollectionTask.payment_status == "Paid", 1), else_=0)),
        func.sum(CollectionTask.outstanding),
        func.sum(case((overdue & (CollectionTask.collection_status == "Belum Follow-up"), 1), else_=0)),
        func.sum(case((overdue & (CollectionTask.collection_status != "Belum Follow-up"), 1), else_=0)),
        func.sum(case((overdue & (CollectionTask.collection_status == "Promise to Pay"), 1), else_=0)),
        func.sum(case((overdue & CollectionTask.collection_status.in_(["Tidak Merespons", "Tidak Dapat Dihubungi"]), 1), else_=0)),
        func.sum(case((overdue & (CollectionTask.next_follow_up_date <= date.today()), 1), else_=0)),
    ).one()
    keys = ["total", "due", "overdue", "overdue_amount", "paid", "outstanding", "not_followed", "followed", "promise", "unresponsive", "follow_up_due"]
    return {key: (value or 0) for key, value in zip(keys, totals)}


def location_progress(tasks: list[CollectionTask]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[CollectionTask]] = defaultdict(list)
    for task in tasks:
        grouped[(task.location_code, task.branch_name, task.region)].append(task)
    rows = []
    for (code, branch, region), items in grouped.items():
        overdue = [item for item in items if item.payment_status == "Overdue"]
        followed = [item for item in overdue if item.collection_status != "Belum Follow-up"]
        not_followed = len(overdue) - len(followed)
        promise = sum(item.collection_status == "Promise to Pay" for item in overdue)
        progress = round((len(followed) / len(overdue)) * 100) if overdue else 100
        labels = [attention_label(item) for item in overdue]
        label = "Escalation" if "Escalation" in labels else "Needs Attention" if "Needs Attention" in labels or not_followed else "Monitoring"
        rows.append({"code": code, "branch": branch, "region": region, "overdue": len(overdue), "followed": len(followed), "not_followed": not_followed, "promise": promise, "progress": progress, "label": label})
    return sorted(rows, key=lambda row: (row["label"] != "Escalation", row["label"] != "Needs Attention", -row["not_followed"], -row["overdue"], row["branch"]))


def location_progress_for_query(query) -> list[dict]:
    """Build location progress with one grouped query instead of loading every installment."""
    today = date.today()
    no_progress = CollectionTask.collection_status.in_({"Belum Follow-up", "Tidak Merespons", "Tidak Dapat Dihubungi"})
    rows = query.filter(CollectionTask.payment_status == "Overdue").with_entities(
        CollectionTask.location_code,
        CollectionTask.branch_name,
        CollectionTask.region,
        func.count(CollectionTask.id),
        func.sum(case((CollectionTask.collection_status != "Belum Follow-up", 1), else_=0)),
        func.sum(case((CollectionTask.collection_status == "Promise to Pay", 1), else_=0)),
        func.sum(case(((CollectionTask.due_date <= today - timedelta(days=14)) & no_progress, 1), else_=0)),
        func.sum(case(((CollectionTask.due_date <= today - timedelta(days=7)) | (CollectionTask.collection_status == "Belum Follow-up"), 1), else_=0)),
    ).group_by(CollectionTask.location_code, CollectionTask.branch_name, CollectionTask.region).all()
    result = []
    for code, branch, region, overdue, followed, promise, escalations, attention in rows:
        followed = followed or 0
        not_followed = overdue - followed
        label = "Escalation" if escalations else "Needs Attention" if attention else "Monitoring"
        result.append({
            "code": code,
            "branch": branch,
            "region": region,
            "overdue": overdue,
            "followed": followed,
            "not_followed": not_followed,
            "promise": promise or 0,
            "progress": round((followed / overdue) * 100) if overdue else 100,
            "label": label,
        })
    return sorted(result, key=lambda row: (row["label"] != "Escalation", row["label"] != "Needs Attention", -row["not_followed"], -row["overdue"], row["branch"]))


def record_follow_up(db: Session, task: CollectionTask, user: User, result: str, next_date: date | None, note: str) -> None:
    if result not in FOLLOW_UP_RESULTS:
        raise ValueError("Hasil follow-up tidak dikenal")
    now = datetime.utcnow()
    task.collection_status = result
    task.last_follow_up_at = now
    task.next_follow_up_date = next_date
    task.promise_to_pay_date = next_date if result == "Promise to Pay" else None
    task.last_note = note.strip() or None
    task.updated_at = now
    db.add(CollectionActivity(task_id=task.id, user_id=user.id, result=result, next_follow_up_date=next_date, note=note.strip() or None))
    db.commit()


def record_reminder(db: Session, task: CollectionTask, user: User) -> CollectionReminder:
    level = max(1, next_reminder_level(task))
    days = overdue_days(task)
    message = f"Level {level}: {task.branch_name} memiliki cicilan {task.student_id} overdue {days} hari dan memerlukan update follow-up."
    task.reminder_level = max(task.reminder_level, level)
    task.last_reminder_at = datetime.utcnow()
    reminder = CollectionReminder(task_id=task.id, user_id=user.id, level=level, message=message)
    db.add(reminder)
    db.commit()
    return reminder


def record_location_reminders(db: Session, tasks: list[CollectionTask], user: User) -> int:
    """Record one central reminder for every overdue task at a location in one transaction."""
    now = datetime.utcnow()
    reminders = []
    for task in tasks:
        if task.payment_status != "Overdue":
            continue
        level = max(1, next_reminder_level(task))
        days = overdue_days(task)
        task.reminder_level = max(task.reminder_level, level)
        task.last_reminder_at = now
        reminder = CollectionReminder(
            task_id=task.id,
            user_id=user.id,
            level=level,
            message=(
                f"Reminder lokasi level {level}: {task.branch_name} memiliki cicilan "
                f"{task.student_id} overdue {days} hari dan memerlukan update follow-up."
            ),
        )
        db.add(reminder)
        reminders.append(reminder)
    if reminders:
        db.commit()
    return len(reminders)


def run_automatic_reminders(db: Session) -> list[CollectionReminder]:
    """Create at most one reminder for each threshold reached by an unresolved task."""
    today = date.today()
    tasks = db.query(CollectionTask).filter(CollectionTask.payment_status == "Overdue").all()
    reminders = []
    for task in tasks:
        reached_level = next_reminder_level(task, today)
        needs_update = (
            task.collection_status in {"Belum Follow-up", "Tidak Merespons", "Tidak Dapat Dihubungi"}
            or bool(task.promise_to_pay_date and task.promise_to_pay_date < today)
            or bool(task.next_follow_up_date and task.next_follow_up_date <= today)
        )
        if reached_level == 0 or not needs_update or task.reminder_level >= reached_level:
            continue
        days = overdue_days(task, today)
        message = (
            f"Reminder otomatis level {reached_level}: {task.branch_name} memiliki cicilan "
            f"{task.student_id} overdue {days} hari dan memerlukan update follow-up."
        )
        task.reminder_level = reached_level
        task.last_reminder_at = datetime.utcnow()
        reminder = CollectionReminder(task_id=task.id, level=reached_level, message=message)
        db.add(reminder)
        reminders.append(reminder)
    if reminders:
        db.commit()
    return reminders
