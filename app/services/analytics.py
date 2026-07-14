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
    month: str = "",
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
        start, end = _month_bounds(month)
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


def build_trend(results, month: str = ""):
    start, _ = _month_bounds(month)
    dated = [row for row in results if row.branch_input and row.branch_input.transaction_date]
    if start:
        end_month = start
    elif dated:
        latest = max(row.branch_input.transaction_date for row in dated)
        end_month = latest.replace(day=1)
    else:
        end_month = date.today().replace(day=1)
    months = [_shift_month(end_month, offset) for offset in range(-5, 1)]
    month_keys = {item.strftime("%Y-%m"): index for index, item in enumerate(months)}
    region_values = defaultdict(lambda: [0] * len(months))
    for result in dated:
        key = result.branch_input.transaction_date.strftime("%Y-%m")
        if key in month_keys:
            region_values[result.branch_input.region][month_keys[key]] += result.risk_score or 0
    return {
        "labels": [f"{MONTH_NAMES_ID[item.month - 1]} {item.year}" for item in months],
        "series": [
            {"name": region, "values": values}
            for region, values in sorted(region_values.items())
        ],
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
    for result in scoped:
        indicator_counts.update(_rule_names(result))
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
        "trend": build_trend(trend_scope, filters.get("month", "")),
        "indicator_rows": [
            {"name": name, "value": value} for name, value in indicator_counts.most_common(6)
        ],
        "recent_rows": scoped[:12],
    }

def build_global_region_ranking(db: Session, user: User, filters: dict):
    """Ranking nasional terlihat tanpa membuka detail wilayah lain."""
    ranking_filters = {**filters, "region": "", "area": "", "location": ""}
    rows = filtered_results(db, user, **ranking_filters, enforce_user_scope=False)
    return summarize_rankings(rows, "region")
