"""
Covers section 35-38 (Nominal & Activity Success Rate, indicators, leaderboard
ranked by conversion) and section 42 (Daily Action Center priorities).

Run with: cd backend && pytest -v  (see README — this sandbox could not
install sqlalchemy/fastapi to execute this suite itself; the pure formula in
compute_success_rate/sr_indicator was desk-checked separately against the
section 36 worked example: 10 pipeline/7 realized -> activity 70%,
Rp2M pipeline/Rp1.6M realisasi -> nominal 80%).
"""
from datetime import date, timedelta

from app.models import CustomerFollowup, Pipeline, Realization
from app.services import pipeline_calc


def _add_pipeline(db, pn, rmft, nominal, status, pipeline_date, probability=50, target_date=None):
    row = Pipeline(
        pipeline_date=pipeline_date, pn=pn, rmft=rmft, customer="PT Test", product="Giro",
        nominal=nominal, probability=probability, status=status,
        target_date=target_date or pipeline_date,
    )
    db.add(row)
    db.flush()
    return row


def test_success_rate_matches_worked_example(db_session):
    """Section 36: 10 pipeline, 7 realized -> activity 70%; Rp2M pipeline / Rp1.6M realisasi -> nominal 80%."""
    pn = "00380727"
    today = date(2026, 8, 20)
    for i in range(10):
        nominal = 200_000_000
        status = "Realisasi" if i < 7 else "Follow Up"
        p = _add_pipeline(db_session, pn, "Adist Ayudistira", nominal, status, today)
        if status == "Realisasi":
            db_session.add(Realization(pipeline_id=p.pipeline_id, date=today, realization_amount=nominal * 0.8, status="Realisasi"))
    db_session.commit()

    stats = pipeline_calc.get_period_stats(db_session, pn=pn, date_from=today, date_to=today)
    assert stats["total_pipeline_count"] == 10
    assert stats["realized_count"] == 7
    assert abs(stats["activity_sr"] - 70.0) < 1e-6
    assert abs(stats["nominal_sr"] - 80.0) < 1e-6
    assert pipeline_calc.sr_indicator(stats["nominal_sr"]) == "🟢"
    assert pipeline_calc.sr_indicator(stats["activity_sr"]) == "🟡"


def test_leaderboard_ranks_by_conversion_not_pipeline_size(db_session):
    """Section 38: a RMFT with a smaller pipeline but higher conversion outranks
    one with a bigger pipeline but poor conversion."""
    today = date(2026, 8, 20)

    # Ahmad Rafiq: big pipeline (Rp1B), low conversion (30%)
    for i in range(4):
        p = _add_pipeline(db_session, "00382271", "Ahmad Rafiq", 250_000_000,
                           "Realisasi" if i == 0 else "Follow Up", today)
        if i == 0:
            db_session.add(Realization(pipeline_id=p.pipeline_id, date=today, realization_amount=250_000_000, status="Realisasi"))

    # Adist: small pipeline (Rp300jt), high conversion (90%)
    for i in range(2):
        p = _add_pipeline(db_session, "00380727", "Adist Ayudistira", 150_000_000, "Realisasi", today)
        db_session.add(Realization(pipeline_id=p.pipeline_id, date=today, realization_amount=150_000_000 * 0.9, status="Realisasi"))

    db_session.commit()

    rows = pipeline_calc.leaderboard(db_session, date_from=today, date_to=today)
    top = rows[0]
    assert top["pn"] == "00380727", f"expected Adist (higher conversion) ranked #1, got {top}"
    assert top["medal"] == "🥇"


def test_daily_action_priorities(db_session):
    today = date.today()
    pn = "00380727"

    # Priority 2: closing today
    _add_pipeline(db_session, pn, "Adist Ayudistira", 100_000_000, "Commit", today, target_date=today)
    # Priority 3: overdue
    _add_pipeline(db_session, pn, "Adist Ayudistira", 50_000_000, "Follow Up", today - timedelta(days=5),
                  target_date=today - timedelta(days=2))
    # Priority 4: high probability
    _add_pipeline(db_session, pn, "Adist Ayudistira", 75_000_000, "Negotiation", today,
                  probability=85, target_date=today + timedelta(days=3))
    # Priority 5: outflow follow-up not yet contacted
    db_session.add(CustomerFollowup(cif="CIF999", pn=pn, date=today, outflow_amount=600_000_000, status="Belum Dihubungi"))
    db_session.commit()

    result = pipeline_calc.daily_action(db_session, pn=pn)
    assert len(result["priority_2_closing_today"]) == 1
    assert len(result["priority_3_overdue"]) == 1
    assert len(result["priority_4_high_probability"]) == 1
    assert len(result["priority_5_follow_up"]) == 1
