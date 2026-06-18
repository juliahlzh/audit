from io import BytesIO
import json
from collections import Counter, defaultdict

DAY_NAMES_ID = {
    0: "Senin",
    1: "Selasa",
    2: "Rabu",
    3: "Kamis",
    4: "Jumat",
    5: "Sabtu",
    6: "Minggu",
}


def _date_label(value) -> str:
    if not value:
        return "-"
    return f"{DAY_NAMES_ID[value.weekday()]}, {value:%d/%m/%Y}"


def _rule_names(txn) -> list[str]:
    try:
        rules = json.loads(txn.triggered_rules or "[]")
    except (TypeError, json.JSONDecodeError):
        rules = []
    names = [rule.get("name") or rule.get("code") for rule in rules if rule.get("name") or rule.get("code")]
    if names:
        return names
    if txn.mismatch_type:
        return [part.strip() for part in txn.mismatch_type.split(";") if part.strip()]
    return []


def summarize_by_location(transactions):
    grouped = defaultdict(
        lambda: {
            "location": "-",
            "total": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "score_sum": 0,
            "max_score": 0,
            "indicator_counts": Counter(),
            "follow_up_counts": Counter(),
            "latest_date": None,
        }
    )

    for txn in transactions:
        branch = txn.branch_input.branch_name if txn.branch_input else "-"
        row = grouped[branch]
        row["location"] = branch
        row["total"] += 1
        row["score_sum"] += txn.risk_score or 0
        row["max_score"] = max(row["max_score"], txn.risk_score or 0)

        if (txn.risk_score or 0) > 7:
            row["high"] += 1
        elif 4 <= (txn.risk_score or 0) <= 7:
            row["medium"] += 1
        else:
            row["low"] += 1

        for name in _rule_names(txn):
            row["indicator_counts"][name] += 1

        row["follow_up_counts"][txn.follow_up_status or "OPEN"] += 1

        if txn.branch_input and txn.branch_input.transaction_date:
            current_date = txn.branch_input.transaction_date
            if row["latest_date"] is None or current_date > row["latest_date"]:
                row["latest_date"] = current_date

    summaries = []
    for row in grouped.values():
        avg_score = (row["score_sum"] / row["total"]) if row["total"] else 0
        indicator_summary = "; ".join(
            f"{name} ({count})" for name, count in row["indicator_counts"].most_common(5)
        ) or "Tidak ada indikator fraud"
        follow_up_summary = "; ".join(
            f"{status} ({count})" for status, count in row["follow_up_counts"].most_common()
        ) or "-"
        if row["high"]:
            risk_label = "Tinggi"
        elif row["medium"]:
            risk_label = "Sedang"
        else:
            risk_label = "Rendah"

        summaries.append(
            {
                "location": row["location"],
                "total": row["total"],
                "high": row["high"],
                "medium": row["medium"],
                "low": row["low"],
                "max_score": row["max_score"],
                "avg_score": round(avg_score, 1),
                "risk_label": risk_label,
                "indicator_summary": indicator_summary,
                "follow_up_summary": follow_up_summary,
                "latest_date": row["latest_date"],
            }
        )

    return sorted(summaries, key=lambda item: (-item["high"], -item["medium"], -item["total"], item["location"]))


def build_excel_report(transactions):
    import pandas as pd

    rows = [
            {
                "Lokasi/Cabang": row["location"],
                "Total Transaksi": row["total"],
                "High Alert": row["high"],
                "Need Review": row["medium"],
                "Normal/Rendah": row["low"],
                "Skor Tertinggi": row["max_score"],
                "Rata-rata Skor": row["avg_score"],
                "Risiko Lokasi": row["risk_label"],
                "Indikator Utama": row["indicator_summary"],
                "Status Tindak Lanjut": row["follow_up_summary"],
                "Tanggal Terakhir": _date_label(row["latest_date"]),
            }
            for row in summarize_by_location(transactions)
    ]
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ringkasan Lokasi")
    return output.getvalue()


def build_pdf_report(transactions):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Laporan FEWS Per Lokasi", styles["Title"]), Spacer(1, 12)]
    table_data = [["Lokasi", "Total", "High", "Review", "Skor Max", "Risiko", "Indikator Utama"]]
    for row in summarize_by_location(transactions)[:25]:
        table_data.append(
            [
                row["location"][:18],
                str(row["total"]),
                str(row["high"]),
                str(row["medium"]),
                str(row["max_score"]),
                row["risk_label"],
                row["indicator_summary"][:36],
            ]
        )
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b5d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eef4f8")]),
    ]))
    elements.append(table)
    doc.build(elements)
    return output.getvalue()
