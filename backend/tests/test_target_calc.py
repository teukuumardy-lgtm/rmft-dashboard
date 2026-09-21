"""Covers section 43: Target vs Achievement, including the DPK/Premi/FBI grouped categories."""
from datetime import date

from app.models import Pipeline, Realization, RmftTarget
from app.services import target_calc


def _pipeline_with_realization(db, pn, product, nominal, realized_date):
    p = Pipeline(pipeline_date=realized_date, pn=pn, rmft="Adist Ayudistira", customer="PT Test",
                 product=product, nominal=nominal, status="Realisasi")
    db.add(p)
    db.flush()
    db.add(Realization(pipeline_id=p.pipeline_id, date=realized_date, realization_amount=nominal, status="Realisasi"))


def test_direct_product_achievement(db_session):
    pn = "00380727"
    month = "2026-08"
    d = date(2026, 8, 15)
    _pipeline_with_realization(db_session, pn, "Giro", 400_000_000, d)
    db_session.add(RmftTarget(month=month, pn=pn, product="Giro", target=500_000_000))
    db_session.commit()

    rows = target_calc.compute_achievement(db_session, month, pn=pn)
    giro = next(r for r in rows if r["product"] == "Giro")
    assert giro["realisasi"] == 400_000_000
    assert abs(giro["achievement_pct"] - 80.0) < 1e-6
    assert giro["gap"] == 100_000_000


def test_dpk_target_groups_three_funding_products(db_session):
    pn = "00380727"
    month = "2026-08"
    d = date(2026, 8, 10)
    _pipeline_with_realization(db_session, pn, "Tabungan", 100_000_000, d)
    _pipeline_with_realization(db_session, pn, "Giro", 200_000_000, d)
    _pipeline_with_realization(db_session, pn, "Deposito", 300_000_000, d)
    db_session.add(RmftTarget(month=month, pn=pn, product="DPK", target=1_000_000_000))
    db_session.commit()

    rows = target_calc.compute_achievement(db_session, month, pn=pn)
    dpk = next(r for r in rows if r["product"] == "DPK")
    assert dpk["realisasi"] == 600_000_000  # 100jt + 200jt + 300jt
    assert abs(dpk["achievement_pct"] - 60.0) < 1e-6


def test_premi_target_groups_brilife_and_bancassurance(db_session):
    pn = "00382271"
    month = "2026-08"
    d = date(2026, 8, 5)
    _pipeline_with_realization(db_session, pn, "BRILife", 50_000_000, d)
    _pipeline_with_realization(db_session, pn, "Bancassurance", 30_000_000, d)
    _pipeline_with_realization(db_session, pn, "EDC", 999_000_000, d)  # must NOT be counted in Premi
    db_session.add(RmftTarget(month=month, pn=pn, product="Premi", target=100_000_000))
    db_session.commit()

    rows = target_calc.compute_achievement(db_session, month, pn=pn)
    premi = next(r for r in rows if r["product"] == "Premi")
    assert premi["realisasi"] == 80_000_000
