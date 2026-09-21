"""
Section 43: Target RMFT — Achievement = Realisasi ÷ Target × 100%, Gap = Target − Realisasi.

"Realisasi" is computed the same way everywhere else in this app: confirmed
`realization` rows (manual entries or Auto-Match confirmations from Phase 7)
linked through `pipeline.product`. Two of the nine target categories aren't
literal Pipeline product values, so they're computed as a group:

  - DPK        -> sum of Tabungan + Giro + Deposito realisasi
  - Premi      -> sum of BRILife + Bancassurance realisasi
  - FBI        -> FBI Lainnya realisasi

The other six (Tabungan, Giro, Deposito, Payroll, EDC, QRIS) map 1:1 to a
Pipeline product of the same name.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Pipeline, Realization, RmftMaster, RmftTarget

TARGET_PRODUCT_MAP = {
    "Tabungan": ["Tabungan"],
    "Giro": ["Giro"],
    "Deposito": ["Deposito"],
    "DPK": ["Tabungan", "Giro", "Deposito"],
    "Payroll": ["Payroll"],
    "EDC": ["EDC"],
    "QRIS": ["QRIS"],
    "Premi": ["BRILife", "Bancassurance"],
    "FBI": ["FBI Lainnya"],
}


def month_range(month: str) -> tuple[date, date]:
    year, mon = (int(x) for x in month.split("-"))
    date_from = date(year, mon, 1)
    date_to = date(year, mon, calendar.monthrange(year, mon)[1])
    return date_from, date_to


def realisasi_for_target(db: Session, pn: str, product_category: str, date_from: date, date_to: date) -> float:
    products = TARGET_PRODUCT_MAP.get(product_category, [product_category])
    total = (
        db.query(func.coalesce(func.sum(Realization.realization_amount), 0))
        .join(Pipeline, Realization.pipeline_id == Pipeline.pipeline_id)
        .filter(
            Pipeline.pn == pn, Pipeline.product.in_(products),
            Realization.status == "Realisasi", Realization.date >= date_from, Realization.date <= date_to,
        )
        .scalar()
    )
    return float(total or 0)


def compute_achievement(db: Session, month: str, pn: Optional[str] = None) -> list[dict]:
    date_from, date_to = month_range(month)
    q = db.query(RmftTarget).filter(RmftTarget.month == month)
    if pn:
        q = q.filter(RmftTarget.pn == pn)
    targets = q.all()

    pn_to_name = {m.pn: m.rmft_name for m in db.query(RmftMaster).all()}
    results = []
    for t in targets:
        realisasi = realisasi_for_target(db, t.pn, t.product, date_from, date_to)
        target_val = float(t.target or 0)
        achievement_pct = (realisasi / target_val * 100) if target_val else 0.0
        results.append({
            "id": t.id, "pn": t.pn, "rmft_name": pn_to_name.get(t.pn, t.pn), "product": t.product,
            "target": target_val, "realisasi": realisasi,
            "achievement_pct": achievement_pct, "gap": target_val - realisasi,
        })
    results.sort(key=lambda r: (r["rmft_name"], r["product"]))
    return results
