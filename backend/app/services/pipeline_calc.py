"""
Section 35-42: Nominal & Activity Success Rate, RMFT Leaderboard (ranked by
conversion, not raw pipeline size), and the Daily Action Center.

The success-rate formulas are kept as pure functions (no DB access) so they
can be unit tested in isolation from SQLAlchemy/FastAPI.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CustomerFollowup, Pipeline, Realization, RmftMaster

ACTIVE_STATUSES = ("Prospect", "Follow Up", "Negotiation", "Commit", "Pending", "Carry Over")


def compute_success_rate(pipeline_nominal: float, realisasi_nominal: float,
                          total_pipeline_count: int, realized_count: int) -> dict:
    """Section 35-36: two independent success-rate measures."""
    nominal_sr = (realisasi_nominal / pipeline_nominal * 100) if pipeline_nominal else 0.0
    activity_sr = (realized_count / total_pipeline_count * 100) if total_pipeline_count else 0.0
    return {"nominal_sr": nominal_sr, "activity_sr": activity_sr}


def sr_indicator(pct: float) -> str:
    """Section 37."""
    if pct >= 80:
        return "🟢"
    if pct >= 60:
        return "🟡"
    return "🔴"


def get_period_stats(db: Session, pn: Optional[str] = None,
                      date_from: Optional[date] = None, date_to: Optional[date] = None) -> dict:
    q = db.query(Pipeline)
    if pn:
        q = q.filter(Pipeline.pn == pn)
    if date_from:
        q = q.filter(Pipeline.pipeline_date >= date_from)
    if date_to:
        q = q.filter(Pipeline.pipeline_date <= date_to)
    rows = q.all()

    pipeline_nominal = float(sum(r.nominal or 0 for r in rows))
    total_count = len(rows)
    realized_count = sum(1 for r in rows if r.status == "Realisasi")
    batal_count = sum(1 for r in rows if r.status == "Batal")

    pipeline_ids = [r.pipeline_id for r in rows]
    realisasi_nominal = 0.0
    if pipeline_ids:
        real_rows = db.query(Realization).filter(
            Realization.pipeline_id.in_(pipeline_ids), Realization.status == "Realisasi",
        ).all()
        realisasi_nominal = float(sum(r.realization_amount or 0 for r in real_rows))

    outstanding = max(pipeline_nominal - realisasi_nominal, 0.0)
    sr = compute_success_rate(pipeline_nominal, realisasi_nominal, total_count, realized_count)

    return {
        "pipeline_nominal": pipeline_nominal,
        "realisasi_nominal": realisasi_nominal,
        "outstanding": outstanding,
        "total_pipeline_count": total_count,
        "realized_count": realized_count,
        "batal_count": batal_count,
        **sr,
    }


def leaderboard(db: Session, date_from: Optional[date] = None, date_to: Optional[date] = None) -> list[dict]:
    """Section 38: ranked by conversion/success rate, not raw pipeline size."""
    rows = []
    for m in db.query(RmftMaster).filter(RmftMaster.active.is_(True)).order_by(RmftMaster.rmft_name).all():
        stats = get_period_stats(db, pn=m.pn, date_from=date_from, date_to=date_to)
        rows.append({"pn": m.pn, "rmft_name": m.rmft_name, **stats})

    rows.sort(key=lambda r: (r["nominal_sr"], r["activity_sr"]), reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows):
        row["rank"] = i + 1
        row["medal"] = medals[i] if i < len(medals) else None
    return rows


def daily_action(db: Session, pn: Optional[str] = None) -> dict:
    """Section 42: TODAY'S ACTION, priority 1-5."""
    from app.services import funding_calc  # local import avoids a circular import at module load time

    today = date.today()

    outflow = funding_calc.top_movers(db, mode="DTD", direction="outflow", pn=pn, limit=10)

    def pipeline_query():
        q = db.query(Pipeline)
        if pn:
            q = q.filter(Pipeline.pn == pn)
        return q

    closing_today = pipeline_query().filter(
        Pipeline.target_date == today, Pipeline.status.in_(ACTIVE_STATUSES)
    ).order_by(Pipeline.nominal.desc()).all()

    overdue = pipeline_query().filter(
        Pipeline.target_date < today, Pipeline.status.in_(ACTIVE_STATUSES)
    ).order_by(Pipeline.target_date.asc()).all()

    high_probability = pipeline_query().filter(
        Pipeline.probability >= 80, Pipeline.status.in_(ACTIVE_STATUSES)
    ).order_by(Pipeline.probability.desc()).all()

    fu_q = db.query(CustomerFollowup).filter(CustomerFollowup.status == "Belum Dihubungi")
    if pn:
        fu_q = fu_q.filter(CustomerFollowup.pn == pn)
    followup_needed = fu_q.order_by(CustomerFollowup.date.desc()).all()

    return {
        "priority_1_fund_outflow": outflow,
        "priority_2_closing_today": closing_today,
        "priority_3_overdue": overdue,
        "priority_4_high_probability": high_probability,
        "priority_5_follow_up": followup_needed,
    }
