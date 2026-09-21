"""
Covers EDC/QRIS merchant productivity: detection, PN resolution via account
number cross-reference against account_rmft_assignment (never by name),
productivity classification at the real business thresholds (QRIS >= Rp50rb,
EDC >= Rp15jt), anti-double-count on re-upload, and the admin-editable
threshold override.
"""
from datetime import date
from decimal import Decimal

from app.models import MerchantChannel, MerchantSnapshot, ProductivityStatus
from app.services import import_engine, merchant_calc
from tests.helpers import build_di319, build_di321, build_edc, build_qris


def _seed_dpk(db_session):
    """Populate account_rmft_assignment the same way a real admin would —
    by uploading DI319 (Tabungan) and DI321 (Giro) first."""
    di319_path = "/tmp/_di319_for_merchant_test.xlsx"
    build_di319(di319_path)
    import_engine.import_report(db_session, di319_path, "di319.xlsx", uploaded_by=None)

    di321_path = "/tmp/_di321_for_merchant_test.xlsx"
    build_di321(di321_path)
    import_engine.import_report(db_session, di321_path, "di321.xlsx", uploaded_by=None)


def test_edc_detected_and_pn_resolved_by_account_not_by_name(tmp_path, db_session):
    _seed_dpk(db_session)
    path = tmp_path / "edc.xlsx"
    build_edc(str(path))

    result = merchant_calc.import_merchant_report(db_session, str(path), "edc.xlsx", uploaded_by=None)
    assert result["error"] is None
    assert result["report_type"] == "EDC"
    assert result["periode"] == date(2026, 8, 31)
    assert result["unique_terminals"] == 3
    assert result["resolved"] == 2
    assert result["unassigned"] == 1

    row = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID001").first()
    # Free-text pemrakarsa on this row says "Adist Ayudistira", but the linked
    # account 1234567890 is actually owned by Ahmad Rafiq (RM Dana wins per
    # DI319's tier rules) — the account-number cross-reference must win, not the name.
    assert row.resolved_pn == "00382271"
    assert row.resolved_rmft == "Ahmad Rafiq"
    assert row.ownership_matched is True

    unassigned_row = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID003").first()
    assert unassigned_row.resolved_pn is None
    assert unassigned_row.ownership_matched is False


def test_qris_pn_resolved_by_account_ignores_conflicting_pemrakarsa_name(tmp_path, db_session):
    _seed_dpk(db_session)
    path = tmp_path / "qris.xlsx"
    build_qris(str(path))

    result = merchant_calc.import_merchant_report(db_session, str(path), "qris.xlsx", uploaded_by=None)
    assert result["error"] is None
    assert result["report_type"] == "QRIS"

    row = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "ST001").first()
    # PN_PEMRAKASA free text says "Ahmad Rafiq", but account 9988776655 is
    # actually owned by Dia Silopa per the DI321 upload — account wins.
    assert row.resolved_pn == "00274689"
    assert row.resolved_rmft == "Dia Silopa"


def test_productivity_classification_matches_real_thresholds(tmp_path, db_session):
    """EDC >= Rp15.000.000 = produktif; QRIS >= Rp50.000 = produktif (user's
    explicit business rule)."""
    _seed_dpk(db_session)
    edc_path = tmp_path / "edc.xlsx"
    build_edc(str(edc_path))
    merchant_calc.import_merchant_report(db_session, str(edc_path), "edc.xlsx", uploaded_by=None)

    tid001 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID001").first()
    assert tid001.productivity_status == ProductivityStatus.PRODUKTIF  # 20jt >= 15jt
    tid002 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID002").first()
    assert tid002.productivity_status == ProductivityStatus.BELUM_PRODUKTIF  # 5jt < 15jt, > 0
    tid003 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID003").first()
    assert tid003.productivity_status == ProductivityStatus.TIDAK_ADA_TRANSAKSI  # 0

    qris_path = tmp_path / "qris.xlsx"
    build_qris(str(qris_path))
    merchant_calc.import_merchant_report(db_session, str(qris_path), "qris.xlsx", uploaded_by=None)
    st001 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "ST001").first()
    assert st001.productivity_status == ProductivityStatus.PRODUKTIF  # 80rb >= 50rb
    st002 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "ST002").first()
    assert st002.productivity_status == ProductivityStatus.BELUM_PRODUKTIF  # 10rb < 50rb


def test_admin_can_override_threshold_and_it_is_used_on_next_import(tmp_path, db_session):
    _seed_dpk(db_session)
    merchant_calc.set_threshold(db_session, MerchantChannel.EDC, Decimal("3000000"), updated_by="admin-id")
    assert merchant_calc.get_threshold(db_session, MerchantChannel.EDC) == Decimal("3000000")

    path = tmp_path / "edc.xlsx"
    build_edc(str(path))
    merchant_calc.import_merchant_report(db_session, str(path), "edc.xlsx", uploaded_by=None)
    tid002 = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID002").first()
    # 5jt was BELUM_PRODUKTIF at the default 15jt threshold, but is now PRODUKTIF at 3jt.
    assert tid002.productivity_status == ProductivityStatus.PRODUKTIF


def test_no_double_count_on_edc_reupload(tmp_path, db_session):
    _seed_dpk(db_session)
    path = tmp_path / "edc.xlsx"
    build_edc(str(path))
    merchant_calc.import_merchant_report(db_session, str(path), "edc.xlsx", uploaded_by=None)
    merchant_calc.import_merchant_report(db_session, str(path), "edc_reupload.xlsx", uploaded_by=None)

    rows = db_session.query(MerchantSnapshot).filter(
        MerchantSnapshot.channel == MerchantChannel.EDC,
        MerchantSnapshot.snapshot_date == date(2026, 8, 31),
        MerchantSnapshot.terminal_id == "TID001",
    ).all()
    assert len(rows) == 1, "re-uploading the same EDC snapshot must replace, not duplicate"


def test_duplicate_terminal_within_same_file_is_deduped(tmp_path, db_session):
    _seed_dpk(db_session)
    dup_rows = [
        [2026, "31/08/2026", "31/08/2026", "KC JAKARTA", "TID001", "MID001", "TOKO MAJU", "EDC",
         "Adist Ayudistira", "Jl. Sudirman", 20_000_000, "1234567890"],
        [2026, "31/08/2026", "31/08/2026", "KC JAKARTA", "TID001", "MID001", "TOKO MAJU (koreksi)", "EDC",
         "Adist Ayudistira", "Jl. Sudirman", 25_000_000, "1234567890"],
    ]
    path = tmp_path / "edc_dup.xlsx"
    build_edc(str(path), rows=dup_rows)
    result = merchant_calc.import_merchant_report(db_session, str(path), "edc_dup.xlsx", uploaded_by=None)
    assert result["duplicates_removed"] == 1

    row = db_session.query(MerchantSnapshot).filter(MerchantSnapshot.terminal_id == "TID001").first()
    assert float(row.sales_volume) == 25_000_000.0, "last occurrence in file should win"


def test_merchant_summary_counts_pending_correctly(tmp_path, db_session):
    _seed_dpk(db_session)
    path = tmp_path / "edc.xlsx"
    build_edc(str(path))
    merchant_calc.import_merchant_report(db_session, str(path), "edc.xlsx", uploaded_by=None)

    summary = merchant_calc.merchant_summary(db_session, channel=MerchantChannel.EDC)
    assert len(summary) == 1
    s = summary[0]
    assert s["total_terminal"] == 3
    assert s["produktif"] == 1
    assert s["belum_produktif"] == 1
    assert s["tidak_ada_transaksi"] == 1
    assert s["pending"] == 2  # belum_produktif + tidak_ada_transaksi
    assert s["unassigned"] == 1


def test_merchant_summary_scoped_by_pn(tmp_path, db_session):
    _seed_dpk(db_session)
    path = tmp_path / "edc.xlsx"
    build_edc(str(path))
    merchant_calc.import_merchant_report(db_session, str(path), "edc.xlsx", uploaded_by=None)

    summary = merchant_calc.merchant_summary(db_session, channel=MerchantChannel.EDC, pn="00382271")
    assert len(summary) == 1
    assert summary[0]["total_terminal"] == 1  # only TID001, owned by Ahmad Rafiq
    assert summary[0]["produktif"] == 1
