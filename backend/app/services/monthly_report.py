"""
Section 39: MONTHLY PIPELINE HISTORY. Computed live from `pipeline`/`realization`
for the requested month rather than a pre-aggregated snapshot table — always
accurate, and avoids needing a formal "close the month" step to see history
for a month that's still in progress.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Pipeline, Realization
from app.services import pipeline_calc, target_calc


def monthly_summary(db: Session, month: str, pn: Optional[str] = None) -> dict:
    date_from, date_to = target_calc.month_range(month)
    stats = pipeline_calc.get_period_stats(db, pn=pn, date_from=date_from, date_to=date_to)

    best_rmft = None
    if pn is None:
        leaderboard_rows = pipeline_calc.leaderboard(db, date_from=date_from, date_to=date_to)
        candidates = [r for r in leaderboard_rows if r["pipeline_nominal"] > 0]
        if candidates:
            best_rmft = candidates[0]["rmft_name"]

    q = db.query(Pipeline).filter(Pipeline.pipeline_date >= date_from, Pipeline.pipeline_date <= date_to)
    if pn:
        q = q.filter(Pipeline.pn == pn)
    rows = q.all()

    top_customer = None
    if rows:
        top_row = max(rows, key=lambda r: float(r.nominal or 0))
        top_customer = {"customer": top_row.customer, "nominal": float(top_row.nominal or 0), "rmft": top_row.rmft}

    top_product = None
    ids_by_product: dict[str, list[str]] = {}
    for r in rows:
        ids_by_product.setdefault(r.product or "Lainnya", []).append(r.pipeline_id)
    if ids_by_product:
        best_val = -1.0
        for product, ids in ids_by_product.items():
            total = float(
                db.query(func.coalesce(func.sum(Realization.realization_amount), 0))
                .filter(Realization.pipeline_id.in_(ids), Realization.status == "Realisasi")
                .scalar() or 0
            )
            if total > best_val:
                best_val = total
                top_product = {"product": product, "realisasi": total}

    return {
        "month": month, **stats,
        "rmft_terbaik": best_rmft,
        "customer_terbesar": top_customer,
        "produk_terbesar": top_product,
    }


def daily_conversion_trend(db: Session, month: str, pn: Optional[str] = None) -> list[dict]:
    """Section 50-ish: a day-by-day Nominal/Activity SR trend within the month,
    for the Pipeline Conversion report/chart."""
    date_from, date_to = target_calc.month_range(month)
    q = db.query(Pipeline.pipeline_date).filter(Pipeline.pipeline_date >= date_from, Pipeline.pipeline_date <= date_to)
    if pn:
        q = q.filter(Pipeline.pn == pn)
    active_dates = sorted({row[0] for row in q.distinct().all()})

    trend = []
    for d in active_dates:
        stats = pipeline_calc.get_period_stats(db, pn=pn, date_from=d, date_to=d)
        trend.append({
            "date": d,
            "pipeline_nominal": stats["pipeline_nominal"],
            "realisasi_nominal": stats["realisasi_nominal"],
            "nominal_sr": stats["nominal_sr"],
            "activity_sr": stats["activity_sr"],
        })
    return trend
