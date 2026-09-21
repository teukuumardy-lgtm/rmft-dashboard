"""
Section 57: Export Laporan — Excel & PDF for the 9 report types listed in the
spec (WhatsApp export lives separately in wa_generator.py, since it targets
chat text rather than a file).

Design: a single `build_report_rows()` dispatcher normalizes every report
into a common shape —

    {"title": str, "subtitle": str, "columns": [(key, label, fmt)], "rows": [dict]}

`fmt` is one of "text" | "number" | "currency" | "percent" | "date" and
drives both the Excel cell number_format and the PDF's Indonesian-style
text formatting (section 58), so a single builder feeds both renderers
without 18 separate endpoint implementations.

Excel cells keep raw numeric values (so the sheet is usable for further
analysis/pivoting in Excel) with a matching number_format applied. The PDF
renders section-58 Indonesian-formatted strings (Rp1,25 M / 84,5%), since a
PDF is a presentation artifact, not a raw-data one.
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models import MerchantChannel, Pipeline, Realization, ReportType, RmftMaster
from app.services import funding_calc, id_format, merchant_calc, monthly_report, pipeline_calc, target_calc

REPORT_TITLES = {
    "funding": "Posisi Funding per RMFT",
    "rmft_performance": "RMFT Performance Leaderboard",
    "pipeline": "Data Pipeline",
    "pipeline_conversion": "Tren Konversi Pipeline Harian",
    "customer_outflow": "Top Customer Outflow",
    "customer_inflow": "Top Customer Inflow",
    "target_achievement": "Target vs Achievement",
    "daily_performance": "Performance Harian RMFT",
    "monthly_performance": "Monthly Performance Summary",
    "rmft_profile": "Report per RMFT (Kekuatan & Kelemahan)",
}


def _today_month() -> str:
    return date.today().strftime("%Y-%m")


# ---------------------------------------------------------------------------
# Per-report builders — each returns the common {title, subtitle, columns, rows} shape.
# ---------------------------------------------------------------------------
def _funding(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    data = funding_calc.compute_home_kpis(db)
    cards = data["rmft_cards"]
    if pn:
        cards = [c for c in cards if c["pn"] == pn]

    rows = [{
        "pn": c["pn"], "rmft_name": c["rmft_name"],
        "tabungan": c["current"]["tabungan"], "giro": c["current"]["giro"], "deposito": c["current"]["deposito"],
        "casa": c["current"]["casa"], "dpk": c["current"]["dpk"],
        "mtd_dpk": c["mtd"]["dpk"], "dtd_dpk": c["dtd"]["dpk"], "account_count": c["account_count"],
    } for c in cards]

    freshness = data["freshness"]
    as_of = id_format.format_date_id(freshness["as_of"]) if freshness["as_of"] else "-"
    return {
        "title": REPORT_TITLES["funding"],
        "subtitle": f"Data per {as_of} ({freshness['status']})",
        "columns": [
            ("pn", "PN", "text"), ("rmft_name", "RMFT", "text"),
            ("tabungan", "Tabungan", "currency"), ("giro", "Giro", "currency"), ("deposito", "Deposito", "currency"),
            ("casa", "CASA", "currency"), ("dpk", "Total DPK", "currency"),
            ("mtd_dpk", "MTD DPK", "currency"), ("dtd_dpk", "DTD DPK", "currency"),
            ("account_count", "Jumlah Rekening", "number"),
        ],
        "rows": rows,
    }


def _rmft_performance(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    # date_from/date_to (from the frontend's Daily/MTD/YTD leaderboard scope selector)
    # take priority; otherwise fall back to a plain calendar month.
    if params.get("date_from") and params.get("date_to"):
        date_from, date_to = params["date_from"], params["date_to"]
        subtitle = f"Periode {id_format.format_date_id(date_from)} — {id_format.format_date_id(date_to)}"
    else:
        month = params.get("month") or _today_month()
        date_from, date_to = target_calc.month_range(month)
        subtitle = f"Periode {month}"
    rows = pipeline_calc.leaderboard(db, date_from=date_from, date_to=date_to)
    if pn:
        rows = [r for r in rows if r["pn"] == pn]
    return {
        "title": REPORT_TITLES["rmft_performance"],
        "subtitle": subtitle,
        "columns": [
            ("rank", "Rank", "number"), ("medal", "Medali", "text"),
            ("rmft_name", "RMFT", "text"), ("pn", "PN", "text"),
            ("pipeline_nominal", "Pipeline Nominal", "currency"), ("realisasi_nominal", "Realisasi Nominal", "currency"),
            ("outstanding", "Outstanding", "currency"),
            ("nominal_sr", "Success Rate Nominal", "percent"), ("activity_sr", "Success Rate Activity", "percent"),
            ("total_pipeline_count", "Jumlah Pipeline", "number"), ("realized_count", "Terealisasi", "number"),
            ("batal_count", "Batal", "number"),
        ],
        "rows": rows,
    }


def _daily_performance(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    target_date: date = params.get("date") or date.today()
    rows = pipeline_calc.leaderboard(db, date_from=target_date, date_to=target_date)
    if pn:
        rows = [r for r in rows if r["pn"] == pn]
    return {
        "title": REPORT_TITLES["daily_performance"],
        "subtitle": f"Tanggal {id_format.format_date_id(target_date)}",
        "columns": [
            ("rank", "Rank", "number"), ("rmft_name", "RMFT", "text"), ("pn", "PN", "text"),
            ("pipeline_nominal", "Pipeline Nominal", "currency"), ("realisasi_nominal", "Realisasi Nominal", "currency"),
            ("nominal_sr", "Success Rate Nominal", "percent"), ("activity_sr", "Success Rate Activity", "percent"),
            ("total_pipeline_count", "Jumlah Pipeline", "number"), ("realized_count", "Terealisasi", "number"),
        ],
        "rows": rows,
    }


def _pipeline(db: Session, params: dict) -> dict:
    q = db.query(Pipeline)
    pn = params.get("pn")
    if pn:
        q = q.filter(Pipeline.pn == pn)
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if date_from:
        q = q.filter(Pipeline.pipeline_date >= date_from)
    if date_to:
        q = q.filter(Pipeline.pipeline_date <= date_to)
    status = params.get("status")
    if status:
        q = q.filter(Pipeline.status == status)

    rows = q.order_by(Pipeline.pipeline_date.desc()).limit(5000).all()
    row_dicts = [{
        "pipeline_date": r.pipeline_date, "pn": r.pn, "rmft": r.rmft, "customer": r.customer,
        "category": r.category, "product": r.product, "nominal": float(r.nominal or 0),
        "probability": r.probability, "target_date": r.target_date, "status": r.status,
    } for r in rows]

    return {
        "title": REPORT_TITLES["pipeline"],
        "subtitle": f"{len(row_dicts)} baris" + (f" — PN {pn}" if pn else ""),
        "columns": [
            ("pipeline_date", "Tanggal", "date"), ("pn", "PN", "text"), ("rmft", "RMFT", "text"),
            ("customer", "Customer", "text"), ("category", "Kategori", "text"), ("product", "Produk", "text"),
            ("nominal", "Nominal", "currency"), ("probability", "Probability (%)", "number"),
            ("target_date", "Target Tanggal", "date"), ("status", "Status", "text"),
        ],
        "rows": row_dicts,
    }


def _pipeline_conversion(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    month = params.get("month") or _today_month()
    trend = monthly_report.daily_conversion_trend(db, month, pn=pn)
    return {
        "title": REPORT_TITLES["pipeline_conversion"],
        "subtitle": f"Periode {month}" + (f" — PN {pn}" if pn else ""),
        "columns": [
            ("date", "Tanggal", "date"), ("pipeline_nominal", "Pipeline Nominal", "currency"),
            ("realisasi_nominal", "Realisasi Nominal", "currency"),
            ("nominal_sr", "Success Rate Nominal", "percent"), ("activity_sr", "Success Rate Activity", "percent"),
        ],
        "rows": trend,
    }


def _customer_movers(db: Session, params: dict, direction: str) -> dict:
    pn = params.get("pn")
    mode = params.get("mode") or "MTD"
    limit = int(params.get("limit") or 20)
    rows = funding_calc.top_movers(db, mode=mode, direction=direction, pn=pn, limit=limit)
    key = "customer_outflow" if direction == "outflow" else "customer_inflow"
    return {
        "title": REPORT_TITLES[key],
        "subtitle": f"Mode {mode}" + (f" — PN {pn}" if pn else ""),
        "columns": [
            ("rank", "Rank", "number"), ("customer", "Customer", "text"), ("account_number", "No. Rekening", "text"),
            ("product", "Produk", "text"), ("rmft_name", "RMFT", "text"), ("pn", "PN", "text"),
            ("baseline_or_previous", "Saldo Referensi", "currency"), ("current_balance", "Saldo Saat Ini", "currency"),
            ("delta", "Delta", "currency"), ("delta_pct", "Delta (%)", "percent"), ("status", "Status", "text"),
        ],
        "rows": rows,
    }


def _target_achievement(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    month = params.get("month") or _today_month()
    rows = target_calc.compute_achievement(db, month, pn=pn)
    return {
        "title": REPORT_TITLES["target_achievement"],
        "subtitle": f"Periode {month}",
        "columns": [
            ("rmft_name", "RMFT", "text"), ("pn", "PN", "text"), ("product", "Produk", "text"),
            ("target", "Target", "currency"), ("realisasi", "Realisasi", "currency"),
            ("achievement_pct", "Achievement (%)", "percent"), ("gap", "Gap", "currency"),
        ],
        "rows": rows,
    }


def _monthly_performance(db: Session, params: dict) -> dict:
    pn = params.get("pn")
    month = params.get("month") or _today_month()
    summary = monthly_report.monthly_summary(db, month, pn=pn)

    top_customer = summary.get("customer_terbesar") or {}
    top_product = summary.get("produk_terbesar") or {}
    rows = [
        {"metric": "Total Pipeline Nominal", "value": summary["pipeline_nominal"], "fmt": "currency"},
        {"metric": "Total Realisasi Nominal", "value": summary["realisasi_nominal"], "fmt": "currency"},
        {"metric": "Outstanding", "value": summary["outstanding"], "fmt": "currency"},
        {"metric": "Jumlah Pipeline", "value": summary["total_pipeline_count"], "fmt": "number"},
        {"metric": "Terealisasi", "value": summary["realized_count"], "fmt": "number"},
        {"metric": "Batal", "value": summary["batal_count"], "fmt": "number"},
        {"metric": "Success Rate Nominal", "value": summary["nominal_sr"], "fmt": "percent"},
        {"metric": "Success Rate Activity", "value": summary["activity_sr"], "fmt": "percent"},
        {"metric": "RMFT Terbaik", "value": summary.get("rmft_terbaik") or "-", "fmt": "text"},
        {"metric": "Customer Terbesar", "value": top_customer.get("customer") or "-", "fmt": "text"},
        {"metric": "Nominal Customer Terbesar", "value": top_customer.get("nominal") or 0, "fmt": "currency"},
        {"metric": "Produk Terbesar (Realisasi)", "value": top_product.get("product") or "-", "fmt": "text"},
        {"metric": "Realisasi Produk Terbesar", "value": top_product.get("realisasi") or 0, "fmt": "currency"},
    ]
    return {
        "title": REPORT_TITLES["monthly_performance"],
        "subtitle": f"Periode {month}" + (f" — PN {pn}" if pn else " — Seluruh Unit"),
        "columns": [("metric", "Metrik", "text"), ("value", "Nilai", "mixed")],
        "rows": rows,
    }


def _pct_gap_note(label: str, own: float, unit: float, higher_is_better: bool = True, unit_fmt: str = "percent") -> dict:
    """A single dynamically-computed strength/weakness line: compares the RM's own
    number against the live unit figure and states the gap in real terms, computed
    fresh from current data every time this report is pulled (never a fixed/static
    sentence — constraint: 'Jangan menggunakan insight statis')."""
    gap = own - unit
    better = gap > 0 if higher_is_better else gap < 0
    if abs(gap) < 1e-9:
        tag = "SETARA"
    else:
        tag = "KEKUATAN" if better else "KELEMAHAN"

    if unit_fmt == "currency":
        own_txt, unit_txt = id_format.format_short(own), id_format.format_short(unit)
        gap_txt = f"{'+' if gap >= 0 else '-'}{id_format.format_short(abs(gap))}"
    else:
        own_txt, unit_txt = id_format.format_percent(own), id_format.format_percent(unit)
        gap_txt = f"{gap:+.1f}".replace(".", ",") + " poin"

    return {
        "metric": f"[{tag}] {label}",
        "value": f"RM: {own_txt} vs Unit: {unit_txt} (selisih {gap_txt})",
        "fmt": "text",
    }


def _rmft_profile(db: Session, params: dict) -> dict:
    """'Report per RMFT' — section requested directly by the user: kekuatan/
    kelemahan, top pipeline & realisasi, pendingan EDC/QRIS, dan posisi
    simpanan berdasarkan PN, semuanya dari data yang sudah di-upload admin.
    Every comparison figure here is recomputed from live data at export time
    (constraint: no static/templated insight text)."""
    pn = params.get("pn")
    if not pn:
        raise ValueError("Parameter pn wajib diisi untuk Report per RMFT (pilih satu RMFT).")
    master = db.query(RmftMaster).filter(RmftMaster.pn == pn).first()
    if not master:
        raise ValueError(f"PN {pn} tidak ditemukan di master RMFT.")

    if params.get("date_from") and params.get("date_to"):
        date_from, date_to = params["date_from"], params["date_to"]
        period_label = f"{id_format.format_date_id(date_from)} — {id_format.format_date_id(date_to)}"
    else:
        month = params.get("month") or _today_month()
        date_from, date_to = target_calc.month_range(month)
        period_label = f"Periode {month}"

    rows: list[dict] = []

    def section(title: str):
        rows.append({"metric": f"— {title} —", "value": "", "fmt": "text"})

    # --- Posisi simpanan (funding) berdasarkan PN --------------------------
    kpis = funding_calc.compute_home_kpis(db)
    freshness = kpis["freshness"]
    card = next((c for c in kpis["rmft_cards"] if c["pn"] == pn), None)
    active_rmft_count = len(kpis["rmft_cards"]) or 1

    as_of_dates = {
        ReportType.TABUNGAN: funding_calc.get_latest_snapshot_date(db, ReportType.TABUNGAN),
        ReportType.GIRO: funding_calc.get_latest_snapshot_date(db, ReportType.GIRO),
        ReportType.DEPOSITO: funding_calc.get_latest_snapshot_date(db, ReportType.DEPOSITO),
    }

    section("Posisi Simpanan (PN)")
    as_of_txt = id_format.format_date_id(freshness["as_of"]) if freshness["as_of"] else "-"
    rows.append({"metric": "Data per tanggal", "value": f"{as_of_txt} ({freshness['status']})", "fmt": "text"})
    if card is None:
        rows.append({"metric": "Catatan", "value": "Belum ada data simpanan yang teridentifikasi untuk PN ini.", "fmt": "text"})
        own_current = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0, "casa": 0.0, "dpk": 0.0}
        acct_count = 0
    else:
        own_current = card["current"]
        acct_count = card["account_count"]
        rows.append({"metric": "Tabungan", "value": own_current["tabungan"], "fmt": "currency"})
        rows.append({"metric": "Giro", "value": own_current["giro"], "fmt": "currency"})
        rows.append({"metric": "Deposito", "value": own_current["deposito"], "fmt": "currency"})
        rows.append({"metric": "CASA", "value": own_current["casa"], "fmt": "currency"})
        rows.append({"metric": "Total DPK", "value": own_current["dpk"], "fmt": "currency"})
        rows.append({"metric": "Jumlah Rekening", "value": acct_count, "fmt": "number"})

    unit_avg_dpk = kpis["unit_current"]["dpk"] / active_rmft_count

    # --- Pertumbuhan MTD & YTD, per produk -----------------------------------
    section("Pertumbuhan Simpanan — MTD")
    if card is not None:
        for label, key in [("Tabungan", "tabungan"), ("Giro", "giro"), ("Deposito", "deposito"), ("Total DPK", "dpk")]:
            rows.append({"metric": f"{label} — MTD", "value": card["mtd"][key], "fmt": "currency"})
        rows.append({"metric": "Total DPK — DTD", "value": card["dtd"]["dpk"], "fmt": "currency"})
    else:
        rows.append({"metric": "Catatan", "value": "Belum ada data simpanan untuk menghitung MTD.", "fmt": "text"})

    section("Pertumbuhan Simpanan — YTD (dibanding posisi akhir tahun lalu)")
    ytd_dates = funding_calc.ytd_reference_dates(db, as_of_dates)
    missing_ytd = [rt.value for rt, d in ytd_dates.items() if d is None and as_of_dates.get(rt) is not None]
    if missing_ytd:
        rows.append({
            "metric": "Catatan YTD",
            "value": f"Belum ada data posisi akhir tahun sebelumnya untuk: {', '.join(missing_ytd)} — "
                     f"pertumbuhan YTD produk ini belum bisa dihitung sampai data itu diupload.",
            "fmt": "text",
        })
    ytd_baseline_dates_txt = ", ".join(
        f"{rt.value}: {id_format.format_date_id(d) if d else 'belum ada'}" for rt, d in ytd_dates.items()
    )
    rows.append({"metric": "Baseline YTD per produk", "value": ytd_baseline_dates_txt, "fmt": "text"})
    if card is not None:
        ytd_baseline = funding_calc.aggregate_figures(db, ytd_dates, pn=pn)
        own_ytd_growth = {k: own_current[k] - ytd_baseline[k] for k in ("tabungan", "giro", "deposito", "dpk")}
        for label, key in [("Tabungan", "tabungan"), ("Giro", "giro"), ("Deposito", "deposito"), ("Total DPK", "dpk")]:
            rows.append({"metric": f"{label} — YTD", "value": own_ytd_growth[key], "fmt": "currency"})
    else:
        own_ytd_growth = {"tabungan": 0.0, "giro": 0.0, "deposito": 0.0, "dpk": 0.0}

    # --- Top 10 nasabah (posisi kelolaan terbesar) ---------------------------
    section("Top 10 Nasabah (Posisi Kelolaan Terbesar)")
    top_customers = funding_calc.top_customers_by_balance(db, pn, as_of_dates, limit=10)
    if not top_customers:
        rows.append({"metric": "Catatan", "value": "Belum ada data nasabah untuk PN ini.", "fmt": "text"})
    for i, c in enumerate(top_customers, start=1):
        rows.append({
            "metric": f"#{i} {c['customer'] or '-'} ({c['product']}, {c['account_number']})",
            "value": c["balance_idr"], "fmt": "currency",
        })

    # --- Pipeline & Realisasi ------------------------------------------------
    section(f"Pipeline & Realisasi ({period_label})")
    own_stats = pipeline_calc.get_period_stats(db, pn=pn, date_from=date_from, date_to=date_to)
    unit_stats = pipeline_calc.get_period_stats(db, pn=None, date_from=date_from, date_to=date_to)
    board = pipeline_calc.leaderboard(db, date_from=date_from, date_to=date_to)
    own_rank_row = next((r for r in board if r["pn"] == pn), None)

    rows.append({"metric": "Pipeline Nominal", "value": own_stats["pipeline_nominal"], "fmt": "currency"})
    rows.append({"metric": "Realisasi Nominal", "value": own_stats["realisasi_nominal"], "fmt": "currency"})
    rows.append({"metric": "Outstanding", "value": own_stats["outstanding"], "fmt": "currency"})
    rows.append({"metric": "Jumlah Pipeline", "value": own_stats["total_pipeline_count"], "fmt": "number"})
    rows.append({"metric": "Terealisasi", "value": own_stats["realized_count"], "fmt": "number"})
    rows.append({"metric": "Batal", "value": own_stats["batal_count"], "fmt": "number"})
    rows.append({"metric": "Success Rate Nominal", "value": own_stats["nominal_sr"], "fmt": "percent"})
    rows.append({"metric": "Success Rate Activity", "value": own_stats["activity_sr"], "fmt": "percent"})
    if own_rank_row:
        rows.append({
            "metric": "Rank di Unit (periode ini)",
            "value": f"#{own_rank_row['rank']} dari {len(board)} RMFT",
            "fmt": "text",
        })

    # --- Top pipeline & top realisasi (individual entries) ------------------
    section("Top Pipeline (Nominal Terbesar)")
    top_pipeline = (
        db.query(Pipeline)
        .filter(Pipeline.pn == pn, Pipeline.pipeline_date >= date_from, Pipeline.pipeline_date <= date_to)
        .order_by(Pipeline.nominal.desc())
        .limit(5)
        .all()
    )
    if not top_pipeline:
        rows.append({"metric": "Catatan", "value": "Tidak ada data pipeline pada periode ini.", "fmt": "text"})
    for i, p in enumerate(top_pipeline, start=1):
        rows.append({
            "metric": f"#{i} {p.customer or '-'} ({p.product or '-'})",
            "value": f"Rp{float(p.nominal or 0):,.0f} — status {p.status}".replace(",", "."),
            "fmt": "text",
        })

    section("Top Realisasi (Nominal Terbesar)")
    top_realisasi = (
        db.query(Realization, Pipeline)
        .join(Pipeline, Realization.pipeline_id == Pipeline.pipeline_id)
        .filter(Pipeline.pn == pn, Realization.status == "Realisasi",
                Realization.date >= date_from, Realization.date <= date_to)
        .order_by(Realization.realization_amount.desc())
        .limit(5)
        .all()
    )
    if not top_realisasi:
        rows.append({"metric": "Catatan", "value": "Tidak ada realisasi pada periode ini.", "fmt": "text"})
    for i, (real, p) in enumerate(top_realisasi, start=1):
        rows.append({
            "metric": f"#{i} {p.customer or '-'} ({p.product or '-'})",
            "value": f"Rp{float(real.realization_amount or 0):,.0f}".replace(",", "."),
            "fmt": "text",
        })

    # --- EDC / QRIS pending ---------------------------------------------------
    section("EDC / QRIS — Produktivitas & Pending")
    own_merchant = {s["channel"]: s for s in merchant_calc.merchant_summary(db, pn=pn)}
    unit_merchant = {s["channel"]: s for s in merchant_calc.merchant_summary(db, pn=None)}
    if not own_merchant:
        rows.append({"metric": "Catatan", "value": "Belum ada data EDC/QRIS yang diupload.", "fmt": "text"})
    for ch in (MerchantChannel.EDC.value, MerchantChannel.QRIS.value):
        s = own_merchant.get(ch)
        if not s:
            rows.append({"metric": f"{ch} — data", "value": "Belum ada data.", "fmt": "text"})
            continue
        rows.append({"metric": f"{ch} — Total Terminal", "value": s["total_terminal"], "fmt": "number"})
        rows.append({"metric": f"{ch} — Produktif (≥ threshold)", "value": s["produktif"], "fmt": "number"})
        rows.append({"metric": f"{ch} — Belum Produktif", "value": s["belum_produktif"], "fmt": "number"})
        rows.append({"metric": f"{ch} — Belum Ada Transaksi Sama Sekali", "value": s["tidak_ada_transaksi"], "fmt": "number"})
        rows.append({"metric": f"{ch} — Total Pending (perlu tindak lanjut)", "value": s["pending"], "fmt": "number"})
        if s["unassigned"]:
            rows.append({
                "metric": f"{ch} — Belum Teridentifikasi PN-nya",
                "value": f"{s['unassigned']} terminal (rekening belum cocok dengan data simpanan manapun)",
                "fmt": "text",
            })

    # --- Top 10 EDC & Top 10 QRIS (Sales Volume tertinggi) -------------------
    for ch_enum, ch_label in ((MerchantChannel.EDC, "EDC"), (MerchantChannel.QRIS, "QRIS")):
        section(f"Top 10 Terminal {ch_label} (Sales Volume Tertinggi)")
        top_terminals = merchant_calc.top_terminals_by_volume(db, ch_enum, pn=pn, limit=10)
        if not top_terminals:
            rows.append({"metric": "Catatan", "value": f"Belum ada data {ch_label} untuk PN ini.", "fmt": "text"})
        for i, t in enumerate(top_terminals, start=1):
            rows.append({
                "metric": f"#{i} {t['merchant_name'] or '-'} (TID {t['terminal_id']})",
                "value": t["sales_volume"], "fmt": "currency",
            })

    # --- Terminal belum produktif / belum ada transaksi (perlu tindak lanjut) ---
    section("Terminal Belum Produktif / Belum Ada Transaksi (Perlu Tindak Lanjut)")
    any_pending_listed = False
    for ch_enum, ch_label in ((MerchantChannel.EDC, "EDC"), (MerchantChannel.QRIS, "QRIS")):
        pending_list = sorted(
            (r for r in merchant_calc.merchant_list(db, channel=ch_enum, pn=pn) if r["productivity_status"] != "PRODUKTIF"),
            key=lambda r: r["sales_volume"],
        )
        if not pending_list:
            continue
        any_pending_listed = True
        for r in pending_list[:5]:
            status_label = "Belum Produktif" if r["productivity_status"] == "BELUM_PRODUKTIF" else "Belum Ada Transaksi"
            rows.append({
                "metric": f"{ch_label} — {r['merchant_name'] or '-'} (TID {r['terminal_id']})",
                "value": f"{status_label} — {id_format.format_short(r['sales_volume'])}",
                "fmt": "text",
            })
        if len(pending_list) > 5:
            rows.append({
                "metric": f"{ch_label} — dan {len(pending_list) - 5} terminal lainnya",
                "value": "Lihat daftar lengkap di menu EDC/QRIS",
                "fmt": "text",
            })
    if not any_pending_listed:
        rows.append({"metric": "Catatan", "value": "Tidak ada terminal belum produktif untuk PN ini.", "fmt": "text"})

    # --- Kekuatan & Kelemahan (computed live, never static) -------------------
    section("Kekuatan & Kelemahan (dihitung dari data saat ini)")
    rows.append(_pct_gap_note("Success Rate Nominal (%)", own_stats["nominal_sr"], unit_stats["nominal_sr"]))
    rows.append(_pct_gap_note("Success Rate Activity (%)", own_stats["activity_sr"], unit_stats["activity_sr"]))
    if card is not None:
        rows.append(_pct_gap_note("Total DPK (dibanding rata-rata unit)", own_current["dpk"], unit_avg_dpk, unit_fmt="currency"))
        if not missing_ytd:
            unit_ytd_baseline = funding_calc.aggregate_figures(db, ytd_dates)
            unit_ytd_growth_dpk = kpis["unit_current"]["dpk"] - unit_ytd_baseline["dpk"]
            unit_avg_ytd_growth_dpk = unit_ytd_growth_dpk / active_rmft_count
            rows.append(_pct_gap_note(
                "Pertumbuhan DPK YTD (dibanding rata-rata unit)",
                own_ytd_growth["dpk"], unit_avg_ytd_growth_dpk, unit_fmt="currency",
            ))
    for ch in (MerchantChannel.EDC.value, MerchantChannel.QRIS.value):
        s_own, s_unit = own_merchant.get(ch), unit_merchant.get(ch)
        if s_own and s_unit and s_own["total_terminal"] and s_unit["total_terminal"]:
            own_rate = s_own["produktif"] / s_own["total_terminal"] * 100
            unit_rate = s_unit["produktif"] / s_unit["total_terminal"] * 100
            rows.append(_pct_gap_note(f"{ch} — % Terminal Produktif", own_rate, unit_rate))

    return {
        "title": REPORT_TITLES["rmft_profile"],
        "subtitle": f"{master.rmft_name} (PN {pn}) — {period_label}",
        "columns": [("metric", "Metrik", "text"), ("value", "Nilai", "mixed")],
        "rows": rows,
    }


DISPATCH = {
    "funding": _funding,
    "rmft_performance": _rmft_performance,
    "daily_performance": _daily_performance,
    "pipeline": _pipeline,
    "pipeline_conversion": _pipeline_conversion,
    "customer_outflow": lambda db, p: _customer_movers(db, p, "outflow"),
    "customer_inflow": lambda db, p: _customer_movers(db, p, "inflow"),
    "target_achievement": _target_achievement,
    "monthly_performance": _monthly_performance,
    "rmft_profile": _rmft_profile,
}


def build_report_rows(db: Session, report: str, params: dict) -> dict:
    builder = DISPATCH.get(report)
    if not builder:
        raise ValueError(f"Tipe laporan tidak dikenal: {report}. Pilihan: {', '.join(DISPATCH.keys())}")
    return builder(db, params)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------
_EXCEL_NUMBER_FORMATS = {
    "currency": "#,##0",
    "number": "#,##0",
    "percent": '0.0"%"',
    "date": "dd/mm/yyyy",
    "text": "@",
}


def to_excel(result: dict) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = result["title"][:31] or "Report"

    columns = result["columns"]
    ws.append([result["title"]])
    ws.append([result["subtitle"]])
    ws.append([f"Diekspor: {datetime.now().strftime('%d/%m/%Y %H:%M')}"])
    ws.append([])
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"].font = Font(italic=True, color="666666")
    ws["A3"].font = Font(italic=True, size=9, color="999999")

    header_row_idx = 5
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0B2545", end_color="0B2545", fill_type="solid")
    for col_idx, (key, label, fmt) in enumerate(columns, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=label)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    for row_offset, row in enumerate(result["rows"], start=1):
        excel_row = header_row_idx + row_offset
        for col_idx, (key, label, fmt) in enumerate(columns, start=1):
            # "monthly_performance" rows carry a per-row fmt override (mixed metric list)
            cell_fmt = row.get("fmt", fmt) if fmt == "mixed" else fmt
            value = row.get(key)
            cell = ws.cell(row=excel_row, column=col_idx)
            if value is None:
                cell.value = "-"
            elif cell_fmt in ("currency", "number", "percent"):
                try:
                    cell.value = float(value)
                except (TypeError, ValueError):
                    cell.value = str(value)
                else:
                    cell.number_format = _EXCEL_NUMBER_FORMATS.get(cell_fmt, "General")
            elif cell_fmt == "date":
                cell.value = value
                cell.number_format = _EXCEL_NUMBER_FORMATS["date"]
            else:
                cell.value = str(value)

    for col_idx in range(1, len(columns) + 1):
        letter = get_column_letter(col_idx)
        max_len = max(
            [len(str(result["rows"][i].get(columns[col_idx - 1][0], "")) or "") for i in range(len(result["rows"]))]
            + [len(columns[col_idx - 1][1])]
        )
        ws.column_dimensions[letter].width = min(max(max_len + 2, 12), 40)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _pdf_format(value, fmt: str) -> str:
    if value is None:
        return "-"
    if fmt == "currency":
        return id_format.format_short(value)
    if fmt == "percent":
        return id_format.format_percent(value)
    if fmt == "number":
        try:
            return f"{int(value):,}".replace(",", ".")
        except (TypeError, ValueError):
            return str(value)
    if fmt == "date":
        return id_format.format_date_id(value)
    return str(value)


def to_pdf(result: dict) -> io.BytesIO:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buf = io.BytesIO()
    columns = result["columns"]
    page_size = landscape(A4) if len(columns) > 6 else A4
    doc = SimpleDocTemplate(buf, pagesize=page_size, topMargin=14 * mm, bottomMargin=14 * mm)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(result["title"], styles["Title"]),
        Paragraph(result["subtitle"], styles["Normal"]),
        Paragraph(f"Diekspor: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles["Normal"]),
        Spacer(1, 10),
    ]

    header = [label for _, label, _ in columns]
    table_data = [header]
    for row in result["rows"]:
        line = []
        for key, label, fmt in columns:
            cell_fmt = row.get("fmt", fmt) if fmt == "mixed" else fmt
            line.append(_pdf_format(row.get(key), cell_fmt))
        table_data.append(line)

    if len(table_data) == 1:
        elements.append(Paragraph("Tidak ada data untuk kriteria ini.", styles["Normal"]))
    else:
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2545")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f5f9")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(table)

    doc.build(elements)
    buf.seek(0)
    return buf
