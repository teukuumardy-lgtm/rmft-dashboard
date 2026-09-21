"""Covers section 39: Monthly Pipeline History (RMFT Terbaik, Customer Terbesar, Produk Terbesar)."""
from datetime import date

from app.models import Pipeline, Realization
from app.services import monthly_report


def test_monthly_summary_identifies_best_rmft_and_biggest_customer_and_product(db_session):
    month = "2026-08"

    # Adist: small pipeline, fully realized (100% conversion)
    p1 = Pipeline(pipeline_date=date(2026, 8, 3), pn="00380727", rmft="Adist Ayudistira",
                  customer="PT Kecil", product="Giro", nominal=100_000_000, status="Realisasi")
    db_session.add(p1)
    db_session.flush()
    db_session.add(Realization(pipeline_id=p1.pipeline_id, date=date(2026, 8, 3), realization_amount=100_000_000, status="Realisasi"))

    # Ahmad Rafiq: big pipeline (biggest single customer), poor conversion
    p2 = Pipeline(pipeline_date=date(2026, 8, 10), pn="00382271", rmft="Ahmad Rafiq",
                  customer="PT Besar Sekali", product="Deposito", nominal=900_000_000, status="Follow Up")
    db_session.add(p2)
    db_session.commit()

    summary = monthly_report.monthly_summary(db_session, month)
    assert summary["rmft_terbaik"] == "Adist Ayudistira"
    assert summary["customer_terbesar"]["customer"] == "PT Besar Sekali"
    assert summary["produk_terbesar"]["product"] == "Giro"  # only Giro has a confirmed realisasi
    assert summary["produk_terbesar"]["realisasi"] == 100_000_000


def test_conversion_trend_only_includes_active_days(db_session):
    month = "2026-08"
    p = Pipeline(pipeline_date=date(2026, 8, 5), pn="00380727", rmft="Adist Ayudistira",
                 customer="PT X", product="Giro", nominal=50_000_000, status="Prospect")
    db_session.add(p)
    db_session.commit()

    trend = monthly_report.daily_conversion_trend(db_session, month)
    assert len(trend) == 1
    assert trend[0]["date"] == date(2026, 8, 5)
    assert trend[0]["pipeline_nominal"] == 50_000_000
