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


def build_ranked_excel_report(location_rows, filters):
    from datetime import datetime
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ranking Lokasi"
    sheet.append(["Laporan Ranking FEWS"])
    sheet["A1"].font = Font(size=16, bold=True, color="FFFFFF")
    sheet["A1"].fill = PatternFill("solid", fgColor="0B2B4C")
    sheet.merge_cells("A1:N1")
    sheet.append(["Dibuat", datetime.now().strftime("%d/%m/%Y %H:%M")])
    sheet.append([
        "Filter",
        "; ".join(
            f"{label}: {filters.get(key) or 'Semua'}"
            for key, label in [
                ("region", "Wilayah"), ("area", "Area"), ("location", "Lokasi"), ("month", "Bulan"),
                ("indicator", "Kesalahan"), ("verification", "Verifikasi"),
            ]
        ),
    ])
    sheet.append([])
    headers = [
        "Peringkat", "Wilayah", "Area", "Lokasi", "Total Temuan", "High Alert", "Need Review",
        "Risiko Rendah", "Total Skor", "Skor Tertinggi", "Rata-rata Skor", "Tingkat Risiko",
        "Sudah Diverifikasi", "Belum Diverifikasi",
    ]
    sheet.append(headers)
    for row in location_rows:
        sheet.append([
            row["rank"], row["region"], row["area"], row["name"], row["total"], row["high"], row["medium"],
            row["low"], row["score_total"], row["max_score"], row["avg_score"], row["risk_label"],
            row["verified"], row["unverified"],
        ])

    header_row = 5
    if location_rows:
        table = Table(displayName="RankingLokasiFEWS", ref=f"A{header_row}:N{sheet.max_row}")
        table.tableStyleInfo = TableStyleInfo(
            name="TableStyleMedium2", showFirstColumn=False, showLastColumn=False,
            showRowStripes=True, showColumnStripes=False,
        )
        sheet.add_table(table)
    for cell in sheet[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="145DA0")
        cell.alignment = Alignment(horizontal="center", vertical="center")
    sheet.freeze_panes = "A6"
    sheet.auto_filter.ref = f"A{header_row}:N{max(header_row, sheet.max_row)}"
    widths = [12, 22, 24, 22, 15, 12, 14, 14, 13, 15, 16, 16, 20, 22]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width
    sheet.sheet_view.showGridLines = False
    sheet.auto_filter.ref = f"A{header_row}:N{max(header_row, sheet.max_row)}"
    output = BytesIO()
    workbook.save(output)
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
