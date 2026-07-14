from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json

from sqlalchemy.orm import Session, joinedload

from ..models import BranchInput, MatchingResult, User
from .rule_config import RULE_CONFIG
from .organization import REGIONS, areas_for_region, locations_for_scope, scope_for_location


MONTH_NAMES_ID = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
]

def infer_region(location: str, explicit_region: str | None = None) -> str:
    if explicit_region and explicit_region.strip():
        return explicit_region.strip()
    return scope_for_location(location)[0]


def verification_label(status: str | None) -> str:
    return "Sudah Diverifikasi" if (status or "").upper() == "RESOLVED" else "Belum Diverifikasi"


def _month_bounds(month: str | None) -> tuple[date | None, date | None]:
    if not month:
        return None, None
    try:
        start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None, None
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, next_month


def _week_bounds(week: str | None) -> tuple[date | None, date | None]:
    if not week:
        return None, None
    try:
        start = datetime.strptime(f"{week}-1", "%G-W%V-%u").date()
    except ValueError:
        return None, None
    return start, start + timedelta(days=7)


def _period_bounds(
    period_type: str | None,
    month: str | None,
    week: str | None,
) -> tuple[date | None, date | None]:
    if (period_type or "bulanan") == "mingguan":
        return _week_bounds(week)
    return _month_bounds(month)


def _base_query(db: Session, user: User, enforce_user_scope: bool = True):
    query = (
        db.query(MatchingResult)
        .options(joinedload(MatchingResult.branch_input))
        .join(BranchInput, MatchingResult.branch_input_id == BranchInput.id)
        .filter(BranchInput.archived_at.is_(None))
    )
    if user.region and enforce_user_scope:
        query = query.filter(BranchInput.region == user.region)
    return query


def filtered_results(
    db: Session,
    user: User,
    *,
    region: str = "",
    area: str = "",
    location: str = "",
    period_type: str = "bulanan",
    month: str = "",
    week: str = "",
    indicator: str = "",
    verification: str = "",
    apply_month: bool = True,
    enforce_user_scope: bool = True,
):
    query = _base_query(db, user, enforce_user_scope)
    if region and (not user.region or not enforce_user_scope):
        query = query.filter(BranchInput.region == region)
    if area:
        query = query.filter(BranchInput.area == area)
    if location:
        query = query.filter(BranchInput.branch_name == location)
    if indicator:
        query = query.filter(MatchingResult.triggered_rules.ilike(f"%{indicator}%"))
    if verification == "sudah":
        query = query.filter(MatchingResult.follow_up_status == "RESOLVED")
    elif verification == "belum":
        query = query.filter(MatchingResult.follow_up_status != "RESOLVED")
    if apply_month:
        start, end = _period_bounds(period_type, month, week)
        if start and end:
            query = query.filter(BranchInput.transaction_date >= start, BranchInput.transaction_date < end)
    return query.order_by(MatchingResult.risk_score.desc(), MatchingResult.updated_at.desc()).all()


def _rule_names(result: MatchingResult) -> list[str]:
    try:
        rules = json.loads(result.triggered_rules or "[]")
    except (TypeError, json.JSONDecodeError):
        rules = []
    names = [rule.get("name") or rule.get("code") for rule in rules]
    return [name for name in names if name]


def _risk_label(max_score: int) -> str:
    if max_score > RULE_CONFIG["risk_level"]["medium_max"]:
        return "Tinggi"
    if max_score > RULE_CONFIG["risk_level"]["low_max"]:
        return "Sedang"
    return "Rendah"


def summarize_rankings(results, group_by: str):
    grouped = defaultdict(
        lambda: {
            "name": "-", "region": "-", "area": "-", "total": 0, "high": 0, "medium": 0,
            "low": 0, "score_total": 0, "max_score": 0, "verified": 0,
            "unverified": 0, "indicators": Counter(), "latest_date": None,
        }
    )
    for result in results:
        branch = result.branch_input
        if not branch:
            continue
        key = branch.region if group_by == "region" else f"{branch.region}|{branch.area}|{branch.branch_name}"
        row = grouped[key]
        row["name"] = branch.region if group_by == "region" else branch.branch_name
        row["region"] = branch.region
        row["area"] = branch.area
        row["total"] += 1
        score = result.risk_score or 0
        row["score_total"] += score
        row["max_score"] = max(row["max_score"], score)
        if score > RULE_CONFIG["risk_level"]["medium_max"]:
            row["high"] += 1
        elif score > RULE_CONFIG["risk_level"]["low_max"]:
            row["medium"] += 1
        else:
            row["low"] += 1
        if verification_label(result.follow_up_status).startswith("Sudah"):
            row["verified"] += 1
        else:
            row["unverified"] += 1
        row["indicators"].update(_rule_names(result))
        if row["latest_date"] is None or branch.transaction_date > row["latest_date"]:
            row["latest_date"] = branch.transaction_date

    ranked = []
    for row in grouped.values():
        row["avg_score"] = round(row["score_total"] / row["total"], 1) if row["total"] else 0
        row["risk_label"] = _risk_label(row["max_score"])
        row["indicator_summary"] = "; ".join(
            f"{name} ({count})" for name, count in row["indicators"].most_common(3)
        ) or "Tidak ada indikator"
        ranked.append(row)
    ranked.sort(
        key=lambda item: (-item["score_total"], -item["high"], -item["medium"], -item["total"], item["name"])
    )
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    return ranked


def _shift_month(value: date, offset: int) -> date:
    absolute = value.year * 12 + value.month - 1 + offset
    return date(absolute // 12, absolute % 12 + 1, 1)


def build_trend(results, period_type: str = "bulanan", month: str = "", week: str = ""):
    period_type = "mingguan" if period_type == "mingguan" else "bulanan"
    start, _ = _period_bounds(period_type, month, week)
    dated = [row for row in results if row.branch_input and row.branch_input.transaction_date]
    latest = max((row.branch_input.transaction_date for row in dated), default=date.today())

    if period_type == "mingguan":
        end_period = start or (latest - timedelta(days=latest.weekday()))
        periods = [end_period + timedelta(weeks=offset) for offset in range(-5, 1)]
        keys = {item.strftime("%G-W%V"): index for index, item in enumerate(periods)}
        labels = [f"M{item.isocalendar().week} {item.isocalendar().year}" for item in periods]
        key_for_date = lambda value: value.strftime("%G-W%V")
    else:
        end_period = start or latest.replace(day=1)
        periods = [_shift_month(end_period, offset) for offset in range(-5, 1)]
        keys = {item.strftime("%Y-%m"): index for index, item in enumerate(periods)}
        labels = [f"{MONTH_NAMES_ID[item.month - 1]} {item.year}" for item in periods]
        key_for_date = lambda value: value.strftime("%Y-%m")

    values = [0] * len(periods)
    for result in dated:
        key = key_for_date(result.branch_input.transaction_date)
        if key in keys:
            values[keys[key]] += result.risk_score or 0

    previous = values[-2] if len(values) > 1 else 0
    current = values[-1] if values else 0
    delta = current - previous
    if delta > 0:
        direction = "naik"
        recommendation = "Prioritaskan verifikasi lokasi dan indikator penyumbang skor terbesar."
    elif delta < 0:
        direction = "turun"
        recommendation = "Pertahankan tindak lanjut dan periksa apakah penurunan konsisten pada periode berikutnya."
    else:
        direction = "stabil"
        recommendation = "Lanjutkan pemantauan dan verifikasi temuan yang masih terbuka."
    comparison = f"{abs(delta)} poin" if previous == 0 else f"{abs(delta / previous * 100):.1f}%"
    return {
        "period_type": period_type,
        "labels": labels,
        "series": [{"name": "Total skor", "values": values}],
        "analysis": {
            "direction": direction,
            "headline": f"Skor {direction} {comparison} dari periode sebelumnya",
            "recommendation": recommendation,
            "current": current,
            "previous": previous,
        },
    }


def filter_options(db: Session, user: User, selected_region: str = "", selected_area: str = ""):
    query = (
        db.query(BranchInput.region, BranchInput.area, BranchInput.branch_name)
        .filter(BranchInput.archived_at.is_(None))
    )
    if user.region:
        query = query.filter(BranchInput.region == user.region)
    elif selected_region:
        query = query.filter(BranchInput.region == selected_region)
    pairs = (
        query.distinct()
        .order_by(BranchInput.region, BranchInput.area, BranchInput.branch_name)
        .all()
    )
    effective_region = user.region or selected_region
    regions = [user.region] if user.region else list(REGIONS)
    regions = sorted(set(regions) | {region for region, _, _ in pairs if region})
    data_areas = {
        row_area
        for row_region, row_area, _ in pairs
        if row_area and (not effective_region or row_region == effective_region)
    }
    areas = sorted(set(areas_for_region(effective_region)) | data_areas)
    data_locations = {
        row_location
        for row_region, row_area, row_location in pairs
        if row_location and (not effective_region or row_region == effective_region)
        and (not selected_area or row_area == selected_area)
    }
    locations = sorted(set(locations_for_scope(effective_region, selected_area)) | data_locations)
    indicators = [
        {"code": code, "name": rule["name"]}
        for code, rule in RULE_CONFIG["rules"].items()
    ]
    return {"regions": regions, "areas": areas, "locations": locations, "indicators": indicators}


def build_monitoring_context(db: Session, user: User, filters: dict):
    scoped = filtered_results(db, user, **filters)
    for result in scoped:
        result.indicator_names = _rule_names(result)
        result.verification_label = verification_label(result.follow_up_status)
    trend_scope = filtered_results(db, user, **filters, apply_month=False)
    region_rows = summarize_rankings(scoped, "region")
    location_rows = summarize_rankings(scoped, "location")
    indicator_counts = Counter()
    indicator_scores = Counter()
    for result in scoped:
        names = _rule_names(result)
        indicator_counts.update(names)
        for name in names:
            indicator_scores[name] += result.risk_score or 0
    indicator_rows = [
        {"name": name, "value": count, "score": indicator_scores[name]}
        for name, count in indicator_counts.most_common()
    ]
    trend = build_trend(
        trend_scope,
        filters.get("period_type", "bulanan"),
        filters.get("month", ""),
        filters.get("week", ""),
    )
    return {
        "filters": filters,
        "filter_options": filter_options(db, user, filters.get("region", ""), filters.get("area", "")),
        "total": len(scoped),
        "unverified": sum(1 for row in scoped if verification_label(row.follow_up_status).startswith("Belum")),
        "need_review": sum(1 for row in scoped if (row.risk_score or 0) > 0),
        "high": sum(1 for row in scoped if (row.risk_score or 0) > RULE_CONFIG["risk_level"]["medium_max"]),
        "region_total": len(region_rows),
        "region_rows": region_rows,
        "location_rows": location_rows,
        "top_location_rows": location_rows[:10],
        "bottom_location_rows": list(reversed(location_rows[-10:])),
        "location_chart_rows": [
            {"name": row["name"], "score_total": row["score_total"], "total": row["total"]}
            for row in location_rows[:10]
        ],
        "trend": trend,
        "trend_analysis": trend["analysis"],
        "indicator_rows": indicator_rows[:10],
        "detail_rows": scoped,
        "recent_rows": scoped[:20],
    }

def build_global_region_ranking(db: Session, user: User, filters: dict):
    """Ranking nasional terlihat tanpa membuka detail wilayah lain."""
    ranking_filters = {**filters, "region": "", "area": "", "location": ""}
    rows = filtered_results(db, user, **ranking_filters, enforce_user_scope=False)
    return summarize_rankings(rows, "region")
