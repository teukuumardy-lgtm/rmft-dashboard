"""
Section 45-48: WhatsApp report generators. Output uses WhatsApp's real
formatting syntax (single-asterisk *bold*, single-underscore _italic_) so
the text can be pasted straight into a chat and render correctly — the
spec's `**double asterisk**` in the template mockups is just markdown-style
emphasis in the document, not literal WhatsApp syntax.

Every number is regenerated live from the current day's pipeline/realisasi/
funding data — nothing here is a static template (section 49's "jangan
menggunakan insight statis" principle applies to these reports too).
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Pipeline, ReportType, RmftMaster
from app.services import funding_calc, id_format, pipeline_calc

fmt = id_format.format_short
pct = id_format.format_percent
dt = id_format.format_date_id


def _rmft_list(db: Session, scoped_pn: Optional[str]):
    q = db.query(RmftMaster).filter(RmftMaster.active.is_(True))
    if scoped_pn:
        q = q.filter(RmftMaster.pn == scoped_pn)
    return q.order_by(RmftMaster.rmft_name).all()


def generate_wa_pagi(db: Session, target_date: date, scoped_pn: Optional[str] = None) -> str:
    """Section 45: COPY WA PAGI."""
    rmft_list = _rmft_list(db, scoped_pn)
    lines = [f"📊 *PIPELINE PLAN RMFT — {dt(target_date)}*", ""]

    unit_total = 0.0
    all_pn = [m.pn for m in rmft_list]
    for m in rmft_list:
        pipelines = (
            db.query(Pipeline)
            .filter(Pipeline.pn == m.pn, Pipeline.pipeline_date == target_date)
            .order_by(Pipeline.nominal.desc())
            .all()
        )
        lines.append(f"*{m.rmft_name.upper()}*")
        if not pipelines:
            lines.append("_Belum ada pipeline hari ini._")
        else:
            for i, p in enumerate(pipelines, 1):
                lines.append(f"{i}. {p.customer or '-'}")
                lines.append(f"   Produk: {p.product or '-'}")
                lines.append(f"   Pipeline: {fmt(p.nominal)}")
                lines.append(f"   Target Closing: {dt(p.target_date) if p.target_date else '-'}")
                lines.append(f"   Aktivitas Hari Ini: {p.activity_today or '-'}")
        rmft_total = sum(float(p.nominal or 0) for p in pipelines)
        unit_total += rmft_total
        first_name = m.rmft_name.split()[0]
        lines.append(f"Total Pipeline {first_name}: *{fmt(rmft_total)}*")
        lines.append("---")

    lines.append("*📌 TOTAL PIPELINE UNIT*")
    lines.append(f"*{fmt(unit_total)}*")
    lines.append("")
    lines.append("*Fokus Hari Ini:*")

    top3 = []
    if all_pn:
        top3 = (
            db.query(Pipeline)
            .filter(Pipeline.pn.in_(all_pn), Pipeline.pipeline_date == target_date)
            .order_by(Pipeline.nominal.desc())
            .limit(3)
            .all()
        )
    if top3:
        for i, p in enumerate(top3, 1):
            lines.append(f"{i}. {p.customer} — {p.product} ({fmt(p.nominal)})")
    else:
        lines.extend(["1.", "2.", "3."])

    return "\n".join(lines)


def generate_wa_sore(db: Session, target_date: date, scoped_pn: Optional[str] = None) -> str:
    """Section 46-48: COPY WA EOD, with Funding Position and Top Fund Outflow appended."""
    rmft_list = _rmft_list(db, scoped_pn)
    lines = [f"📊 *EOD REALISASI RMFT — {dt(target_date)}*", ""]

    unit = {"pipeline_nominal": 0.0, "realisasi_nominal": 0.0, "outstanding": 0.0,
            "total_pipeline_count": 0, "realized_count": 0}
    best = None  # (rmft_name, nominal_sr)

    for m in rmft_list:
        stats = pipeline_calc.get_period_stats(db, pn=m.pn, date_from=target_date, date_to=target_date)
        lines.append(f"*{m.rmft_name.upper()}*")
        lines.append(f"Pipeline: {fmt(stats['pipeline_nominal'])}")
        lines.append(f"Realisasi: {fmt(stats['realisasi_nominal'])}")
        lines.append(f"Nominal Success Rate: *{pct(stats['nominal_sr'])}*")
        lines.append(f"Activity Success Rate: *{pct(stats['activity_sr'])}*")
        lines.append(f"Outstanding: {fmt(stats['outstanding'])}")
        lines.append("---")

        for key in ("pipeline_nominal", "realisasi_nominal", "outstanding", "total_pipeline_count", "realized_count"):
            unit[key] += stats[key]
        if stats["pipeline_nominal"] > 0 and (best is None or stats["nominal_sr"] > best[1]):
            best = (m.rmft_name, stats["nominal_sr"])

    unit_sr = pipeline_calc.compute_success_rate(
        unit["pipeline_nominal"], unit["realisasi_nominal"], unit["total_pipeline_count"], unit["realized_count"]
    )
    lines.append("*📌 SUMMARY UNIT*")
    lines.append(f"Pipeline Hari Ini: *{fmt(unit['pipeline_nominal'])}*")
    lines.append(f"Realisasi: *{fmt(unit['realisasi_nominal'])}*")
    lines.append(f"Outstanding: *{fmt(unit['outstanding'])}*")
    lines.append(f"Nominal Success Rate: *{pct(unit_sr['nominal_sr'])}*")
    lines.append(f"Activity Success Rate: *{pct(unit_sr['activity_sr'])}*")
    if best:
        lines.append(f"🏆 RMFT Conversion terbaik: *{best[0]} — {pct(best[1])}*")
    lines.append("")

    # Section 47: FUNDING POSITION
    kpis = funding_calc.compute_home_kpis(db)
    if scoped_pn:
        card = next((c for c in kpis["rmft_cards"] if c["pn"] == scoped_pn), None)
        current, mtd, dtd = (card["current"], card["mtd"], card["dtd"]) if card else (
            {"tabungan": 0, "giro": 0, "deposito": 0, "dpk": 0},
            {"dpk": 0}, {"dpk": 0},
        )
    else:
        current, mtd, dtd = kpis["unit_current"], kpis["unit_mtd"], kpis["unit_dtd"]

    def signed(v):
        return f"+{fmt(v)}" if v >= 0 else fmt(v)

    lines.append("*💰 FUNDING POSITION*")
    lines.append(f"Tabungan: {fmt(current['tabungan'])}")
    lines.append(f"Giro: {fmt(current['giro'])}")
    lines.append(f"Deposito: {fmt(current['deposito'])}")
    lines.append(f"DPK: *{fmt(current['dpk'])}*")
    lines.append(f"MTD: *{signed(mtd['dpk'])}*")
    lines.append(f"DTD: *{signed(dtd['dpk'])}*")

    # Section 48: TOP FUND OUTFLOW — max 5
    outflow = funding_calc.top_movers(db, mode="DTD", direction="outflow", pn=scoped_pn, limit=5)
    if outflow:
        lines.append("")
        lines.append("*🚨 TOP FUND OUTFLOW*")
        for i, o in enumerate(outflow, 1):
            lines.append(f"{i}. {o['customer'] or o['account_number']} — {fmt(o['delta'])}")
            lines.append(f"   RMFT: {o['rmft_name'] or '-'}")

    return "\n".join(lines)
