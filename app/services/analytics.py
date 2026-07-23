from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
import json

from sqlalchemy.orm import Session, joinedload

from ..models import BranchInput, MatchingResult, User
from .rule_config import RULE_CONFIG
from .organization import REGIONS, areas_for_region, location_code_for_name, locations_for_scope, resolve_location, scope_for_location


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
        code, normalized_location, _, _ = resolve_location(location)
        query = query.filter(BranchInput.branch_name == (normalized_location if code else location))
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


def _rule_codes(result: MatchingResult) -> list[str]:
    try:
        rules = json.loads(result.triggered_rules or "[]")
    except (TypeError, json.JSONDecodeError):
        rules = []
    return [str(rule.get("code")) for rule in rules if rule.get("code")]


def _risk_label(max_score: int) -> str:
    if max_score > RULE_CONFIG["risk_level"]["medium_max"]:
        return "Tinggi"
    if max_score > RULE_CONFIG["risk_level"]["low_max"]:
        return "Sedang"
    return "Rendah"


def summarize_rankings(results, group_by: str):
    grouped = defaultdict(
        lambda: {
            "name": "-", "code": "", "region": "-", "area": "-", "total": 0, "high": 0, "medium": 0,
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
        row["code"] = "" if group_by == "region" else (branch.location_code or location_code_for_name(branch.branch_name))
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
        row["indicator_rows"] = [
            {"name": name, "value": count}
            for name, count in row["indicators"].most_common()
        ]
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


def _empty_ranking_row(name: str, region: str, area: str = "", code: str = "") -> dict:
    return {
        "name": name,
        "code": code,
        "region": region,
        "area": area,
        "total": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "score_total": 0,
        "max_score": 0,
        "avg_score": 0,
        "verified": 0,
        "unverified": 0,
        "indicators": Counter(),
        "indicator_rows": [],
        "indicator_summary": "Tidak ada indikator",
        "latest_date": None,
        "risk_label": "Rendah",
    }


def _rerank(rows: list[dict]) -> list[dict]:
    rows.sort(
        key=lambda item: (-item["score_total"], -item["high"], -item["medium"], -item["total"], item["name"])
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def complete_region_rankings(rows: list[dict], selected_region: str = "") -> list[dict]:
    """Tambahkan wilayah tanpa temuan agar dashboard eksekutif tidak menyembunyikan kategori."""
    source = {row["name"]: row for row in rows}
    names = [selected_region] if selected_region else list(REGIONS)
    complete = [
        source.get(name) or _empty_ranking_row(name=name, region=name)
        for name in names
    ]
    complete.extend(row for name, row in source.items() if name not in names)
    return _rerank(complete)


def complete_location_rankings(rows: list[dict], user: User, filters: dict) -> list[dict]:
    """Tambahkan lokasi master bernilai nol sesuai scope/filter dashboard."""
    selected_region = user.region or filters.get("region", "")
    selected_area = filters.get("area", "")
    selected_location = filters.get("location", "")
    names = locations_for_scope(selected_region, selected_area)
    if selected_location:
        names = [selected_location]

    source = {row["name"]: row for row in rows}
    complete = []
    for name in names:
        if name in source:
            complete.append(source[name])
            continue
        region, area = scope_for_location(name)
        complete.append(
            _empty_ranking_row(
                name=name,
                code=location_code_for_name(name),
                region=region or selected_region or "Belum Dipetakan",
                area=area or selected_area or "Belum Dipetakan",
            )
        )
    complete.extend(row for name, row in source.items() if name not in names)
    return _rerank(complete)


def _double_input_group_key(branch: BranchInput) -> tuple | None:
    reference = " ".join((branch.proof_reference or "").strip().casefold().split())
    if not reference:
        return None
    return (
        reference,
        round(float(branch.amount_input_branch or branch.amount_should_pay or 0), 2),
        branch.transaction_date,
        (branch.payment_method or "").strip().casefold(),
        (branch.location_code or branch.branch_name or "").strip().casefold(),
    )


def build_double_input_groups(results) -> list[dict]:
    grouped = defaultdict(list)
    for result in results:
        if "double_input" not in _rule_codes(result) or not result.branch_input:
            continue
        key = _double_input_group_key(result.branch_input)
        if key:
            grouped[key].append(result)
    groups = []
    for key, items in grouped.items():
        branch = items[0].branch_input
        groups.append(
            {
                "group_id": f"{branch.location_code or branch.branch_name}-{branch.transaction_date}-{branch.proof_reference}",
                "proof_reference": branch.proof_reference,
                "amount": branch.amount_input_branch or branch.amount_should_pay or 0,
                "transaction_date": branch.transaction_date,
                "payment_method": branch.payment_method,
                "location_code": branch.location_code,
                "location": branch.branch_name,
                "count": len(items),
                "rows": items,
            }
        )
    return sorted(groups, key=lambda item: (-item["count"], item["location"], item["proof_reference"] or ""))


def _shift_month(value: date, offset: int) -> date:
    absolute = value.year * 12 + value.month - 1 + offset
    return date(absolute // 12, absolute % 12 + 1, 1)


def previous_period_filters(filters: dict) -> dict | None:
    previous = dict(filters)
    if filters.get("period_type") == "mingguan" and filters.get("week"):
        start, _ = _week_bounds(filters["week"])
        if not start:
            return None
        previous_start = start - timedelta(days=7)
        iso = previous_start.isocalendar()
        previous["week"] = f"{iso.year}-W{iso.week:02d}"
        return previous
    if filters.get("month"):
        start, _ = _month_bounds(filters["month"])
        if not start:
            return None
        previous["month"] = _shift_month(start, -1).strftime("%Y-%m")
        return previous
    return None


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
    location_labels = {
        location: f"{location_code_for_name(location)} — {location}" if location_code_for_name(location) else location
        for location in locations
    }
    indicators = [
        {"code": code, "name": rule["name"]}
        for code, rule in RULE_CONFIG["rules"].items()
    ]
    return {
        "regions": regions,
        "areas": areas,
        "locations": locations,
        "location_labels": location_labels,
        "indicators": indicators,
    }


def build_indicator_trend(
    results,
    period_type: str = "bulanan",
    month: str = "",
    week: str = "",
):
    """Hitung jumlah kemunculan indikator dalam enam bulan atau minggu terakhir."""
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
            values[keys[key]] += len(_rule_codes(result))

    previous = values[-2] if len(values) > 1 else 0
    current = values[-1] if values else 0
    delta = current - previous
    if delta > 0:
        direction = "naik"
        recommendation = "Periksa wilayah, lokasi, dan jenis indikator penyumbang kenaikan terbesar."
    elif delta < 0:
        direction = "turun"
        recommendation = "Pastikan penurunan konsisten dan temuan terbuka tetap ditindaklanjuti."
    else:
        direction = "stabil"
        recommendation = "Lanjutkan pemantauan pada indikator yang masih muncul di periode aktif."
    comparison = f"{abs(delta)} indikator" if previous == 0 else f"{abs(delta / previous * 100):.1f}%"
    return {
        "period_type": period_type,
        "period_label": "Mingguan" if period_type == "mingguan" else "Bulanan",
        "labels": labels,
        "values": values,
        "analysis": {
            "direction": direction,
            "headline": f"Jumlah indikator {direction} {comparison} dari periode sebelumnya",
            "recommendation": recommendation,
            "current": current,
            "previous": previous,
        },
    }


def build_monitoring_context(db: Session, user: User, filters: dict):
    filters = dict(filters)
    if filters.get("location"):
        code, normalized_location, _, _ = resolve_location(filters["location"])
        if code:
            filters["location"] = normalized_location
    scoped = filtered_results(db, user, **filters)
    for result in scoped:
        result.indicator_names = _rule_names(result)
        result.verification_label = verification_label(result.follow_up_status)
    trend_scope = filtered_results(db, user, **filters, apply_month=False)
    region_rows = summarize_rankings(scoped, "region")
    location_rows = summarize_rankings(scoped, "location")
    executive_region_rows = complete_region_rankings(region_rows, user.region or filters.get("region", ""))
    executive_location_rows = complete_location_rankings(location_rows, user, filters)
    safest_region_rows = sorted(
        executive_region_rows,
        key=lambda item: (item["score_total"], item["total"], item["name"]),
    )
    safest_location_rows = sorted(
        executive_location_rows,
        key=lambda item: (item["score_total"], item["total"], item["name"]),
    )
    indicator_counts = Counter()
    indicator_scores = Counter()
    for result in scoped:
        names = _rule_names(result)
        indicator_counts.update(names)
        for name in names:
            indicator_scores[name] += result.risk_score or 0
    indicator_rows = [
        {
            "code": code,
            "name": rule["name"],
            "category": rule["category"],
            "value": indicator_counts[rule["name"]],
            "score": indicator_scores[rule["name"]],
        }
        for code, rule in RULE_CONFIG["rules"].items()
    ]
    indicator_rows.sort(key=lambda row: (-row["value"], row["name"]))
    trend = build_trend(
        trend_scope,
        filters.get("period_type", "bulanan"),
        filters.get("month", ""),
        filters.get("week", ""),
    )
    indicator_trend = build_indicator_trend(
        trend_scope,
        filters.get("period_type", "bulanan"),
        filters.get("month", ""),
        filters.get("week", ""),
    )
    double_input_count = sum(1 for result in scoped if "double_input" in _rule_codes(result))
    high_count = sum(1 for row in scoped if (row.risk_score or 0) > RULE_CONFIG["risk_level"]["medium_max"])
    medium_count = sum(
        1
        for row in scoped
        if RULE_CONFIG["risk_level"]["low_max"] < (row.risk_score or 0) <= RULE_CONFIG["risk_level"]["medium_max"]
    )
    low_count = len(scoped) - high_count - medium_count
    total_score = sum(row.risk_score or 0 for row in scoped)
    use_location_groups = bool(user.region or filters.get("region"))
    executive_group_rows = executive_location_rows if use_location_groups else executive_region_rows
    executive_group_type = "location" if use_location_groups else "region"
    group_indicator_counts = defaultdict(Counter)
    for result in scoped:
        branch = result.branch_input
        if not branch:
            continue
        group_name = branch.branch_name if use_location_groups else branch.region
        group_indicator_counts[group_name].update(_rule_codes(result))
    indicator_group_chart_rows = []
    for row in executive_group_rows:
        counts = group_indicator_counts[row["name"]]
        indicator_group_chart_rows.append(
            {
                "name": (
                    f"{row['code']} — {row['name']}"
                    if use_location_groups and row.get("code")
                    else row["name"]
                ),
                "total": sum(counts.values()),
                "values": {item["code"]: counts[item["code"]] for item in indicator_rows},
            }
        )
    return {
        "filters": filters,
        "filter_options": filter_options(db, user, filters.get("region", ""), filters.get("area", "")),
        "total": len(scoped),
        "unverified": sum(1 for row in scoped if verification_label(row.follow_up_status).startswith("Belum")),
        "need_review": sum(1 for row in scoped if (row.risk_score or 0) > 0),
        "high": high_count,
        "medium": medium_count,
        "low": low_count,
        "total_score": total_score,
        "average_score": round(total_score / len(scoped), 1) if scoped else 0,
        "double_input_count": double_input_count,
        "double_input_groups": build_double_input_groups(scoped),
        "region_total": len(executive_region_rows),
        "location_total": len(executive_location_rows),
        "region_rows": region_rows,
        "location_rows": location_rows,
        "executive_region_rows": executive_region_rows,
        "executive_location_rows": executive_location_rows,
        "executive_group_type": executive_group_type,
        "executive_group_label": "Lokasi" if use_location_groups else "Wilayah",
        "executive_group_rows": executive_group_rows,
        "executive_group_chart_rows": [
            {
                "name": f"{row['code']} — {row['name']}" if use_location_groups and row.get("code") else row["name"],
                "total": row["total"],
                "score_total": row["score_total"],
                "high": row["high"],
                "medium": row["medium"],
                "low": row["low"],
            }
            for row in executive_group_rows
        ],
        "top_region_rows": executive_region_rows[:10],
        "bottom_region_rows": safest_region_rows[:10],
        "top_location_rows": location_rows[:10],
        "bottom_location_rows": list(reversed(location_rows[-10:])),
        "executive_top_location_rows": executive_location_rows[:10],
        "executive_bottom_location_rows": safest_location_rows[:10],
        "location_chart_rows": [
            {
                "name": f"{row['code']} — {row['name']}" if row.get("code") else row["name"],
                "score_total": row["score_total"],
                "total": row["total"],
            }
            for row in location_rows[:10]
        ],
        "trend": trend,
        "trend_analysis": trend["analysis"],
        "indicator_trend": indicator_trend,
        "indicator_trend_analysis": indicator_trend["analysis"],
        "indicator_chart_rows": indicator_rows,
        "indicator_group_chart_rows": indicator_group_chart_rows,
        "region_bar_rows": [
            {
                "name": row["name"],
                "value": row["total"],
                "score_total": row["score_total"],
            }
            for row in region_rows
        ],
        "dashboard_location_bar_rows": [
            {
                "name": f"{row['code']} — {row['name']}" if row.get("code") else row["name"],
                "value": row["total"],
                "score_total": row["score_total"],
                "area": row["area"],
            }
            for row in location_rows
        ],
        "indicator_rows": indicator_rows,
        "location_indicator_rows": location_rows[:10],
        "highest_risk_region": executive_region_rows[0] if scoped and executive_region_rows else None,
        "best_region": safest_region_rows[0] if safest_region_rows else None,
        "highest_risk_location": executive_location_rows[0] if scoped and executive_location_rows else None,
        "best_location": safest_location_rows[0] if safest_location_rows else None,
        "risk_distribution": [
            {"name": "High Risk", "value": high_count, "tone": "high"},
            {"name": "Medium Risk", "value": medium_count, "tone": "medium"},
            {"name": "Low Risk", "value": low_count, "tone": "low"},
        ],
        "dashboard_detail_rows": executive_location_rows,
        "detail_rows": scoped,
        "recent_rows": scoped[:20],
        "dashboard_rows": scoped[:10],
    }

def build_global_region_ranking(db: Session, user: User, filters: dict):
    """Ranking nasional terlihat tanpa membuka detail wilayah lain."""
    ranking_filters = {**filters, "region": "", "area": "", "location": ""}
    rows = filtered_results(db, user, **ranking_filters, enforce_user_scope=False)
    return summarize_rankings(rows, "region")


def build_global_location_ranking(db: Session, user: User, filters: dict):
    """Ranking lokasi nasional untuk Admin Pusat; akun wilayah tetap terkunci."""
    if user.region:
        rows = filtered_results(db, user, **filters)
        return complete_location_rankings(summarize_rankings(rows, "location"), user, filters)
    ranking_filters = {**filters, "region": "", "area": "", "location": ""}
    rows = filtered_results(db, user, **ranking_filters, enforce_user_scope=False)
    return complete_location_rankings(
        summarize_rankings(rows, "location"),
        user,
        ranking_filters,
    )
