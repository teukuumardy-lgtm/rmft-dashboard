"""
Section 40-41: Pipeline vs Actual Funding automatic match suggestion.

This NEVER auto-converts a pipeline to a realization — it only surfaces a
ranked confidence score so a human can hit "Confirm as Realization" (section
40: "Jangan langsung mengubah menjadi realisasi").

Matching signal (section 41): CIF, Account, Customer Name, Product, Nominal,
Date. Candidates are pre-filtered to the same RMFT's own book (a pipeline's
`pn` must equal the funding row's `resolved_pn`) since cross-RMFT matches
are operationally meaningless even if the numbers happen to line up.
"""
from __future__ import annotations

import difflib
from typing import Optional

from sqlalchemy.orm import Session

from app.models import DismissedMatch, Pipeline

FUNDING_PRODUCTS = {"TABUNGAN", "GIRO", "DEPOSITO"}
ACTIVE_STATUSES = ("Prospect", "Follow Up", "Negotiation", "Commit", "Pending", "Carry Over")


def _name_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.strip().upper(), b.strip().upper()).ratio()


def _nominal_score(pipeline_nominal: float, actual: float) -> float:
    if pipeline_nominal <= 0:
        return 0.0
    diff_ratio = abs(actual - pipeline_nominal) / pipeline_nominal
    if diff_ratio >= 0.30:
        return 0.0
    return 15.0 * (1 - diff_ratio / 0.30)


def confidence_score(pipeline: Pipeline, funding_row: dict) -> float:
    score = 0.0
    if pipeline.cif and funding_row.get("cif") and pipeline.cif == funding_row["cif"]:
        score += 40.0
    if pipeline.account_number and funding_row.get("account_number") and pipeline.account_number == funding_row["account_number"]:
        score += 30.0
    score += _name_similarity(pipeline.customer, funding_row.get("customer")) * 15.0
    if (pipeline.product or "").strip().upper() == (funding_row.get("product") or "").strip().upper():
        score += 10.0
    score += _nominal_score(float(pipeline.nominal or 0), float(funding_row.get("delta") or 0))
    return min(round(score, 1), 100.0)


def find_potential_matches(db: Session, pn: Optional[str] = None, min_confidence: float = 50.0, limit: int = 20) -> list[dict]:
    from app.services import funding_calc  # local import avoids a circular import at module load time

    q = db.query(Pipeline).filter(Pipeline.status.in_(ACTIVE_STATUSES))
    if pn:
        q = q.filter(Pipeline.pn == pn)
    pipelines = [p for p in q.all() if (p.product or "").strip().upper() in FUNDING_PRODUCTS]
    if not pipelines:
        return []

    inflow = funding_calc.top_movers(db, mode="DTD", direction="inflow", pn=pn, limit=100)
    by_pn: dict[str, list[dict]] = {}
    for row in inflow:
        by_pn.setdefault(row.get("pn"), []).append(row)

    pipeline_ids = [p.pipeline_id for p in pipelines]
    dismissed = {
        (d.pipeline_id, d.actual_account_number)
        for d in db.query(DismissedMatch).filter(DismissedMatch.pipeline_id.in_(pipeline_ids)).all()
    } if pipeline_ids else set()

    matches = []
    for p in pipelines:
        candidates = by_pn.get(p.pn, [])
        best_row, best_score = None, 0.0
        for row in candidates:
            if (p.pipeline_id, row.get("account_number")) in dismissed:
                continue
            score = confidence_score(p, row)
            if score > best_score:
                best_row, best_score = row, score
        if best_row is not None and best_score >= min_confidence:
            matches.append({
                "pipeline_id": p.pipeline_id,
                "pn": p.pn,
                "rmft": p.rmft,
                "pipeline_customer": p.customer,
                "pipeline_cif": p.cif,
                "pipeline_account_number": p.account_number,
                "product": p.product,
                "pipeline_nominal": float(p.nominal or 0),
                "actual_customer": best_row.get("customer"),
                "actual_cif": best_row.get("cif"),
                "actual_account_number": best_row.get("account_number"),
                "actual_inflow": best_row.get("delta"),
                "confidence": best_score,
            })

    matches.sort(key=lambda m: -m["confidence"])
    return matches[:limit]
