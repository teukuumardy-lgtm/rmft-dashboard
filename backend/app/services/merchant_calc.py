"""
EDC / QRIS merchant productivity — upload, PN resolution, and reporting.

Design mirrors import_engine.py's funding-snapshot pipeline so the same
guarantees apply here:

  - Anti double-count (constraint): one row per (snapshot_date, channel,
    terminal_id); re-uploading a corrected file REPLACES that exact key's
    rows rather than accumulating duplicates.
  - PN as primary key, never a name (constraint): ownership is resolved by
    looking up the merchant's linked account number in
    account_rmft_assignment — the SAME table every DPK product already
    populates — at the latest snapshot date on/before this file's POSISI
    date. The free-text 'pemrakarsa' name column is stored for reference
    only and never drives assignment.
  - Incomplete data is never hidden (constraint): a terminal whose account
    number has no match in account_rmft_assignment stays visibly
    UNASSIGNED (ownership_matched=False) rather than falling back to a
    name-based guess.
  - Productivity thresholds are data (merchant_threshold table), not a
    hardcoded number, so a policy change is an admin edit, not code.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AccountRmftAssignment, MerchantChannel, MerchantSnapshot, MerchantThreshold,
    ProductivityStatus, RawImport, ReportType, RmftMaster, UploadBatch, UploadStatus,
)
from app.services import excel_detect as det

CHANNEL_REPORT_TYPE = {"EDC": MerchantChannel.EDC, "QRIS": MerchantChannel.QRIS}

# Fallback used only if merchant_threshold has no row yet for a channel
# (seed.py inserts the real defaults below on first run).
DEFAULT_THRESHOLDS = {
    MerchantChannel.EDC: Decimal("15000000"),   # Rp15.000.000
    MerchantChannel.QRIS: Decimal("50000"),     # Rp50.000
}

TOTAL_ROW_MARKERS = ("TOTAL", "GRANDTOTAL", "SUBTOTAL")


def get_threshold(db: Session, channel: MerchantChannel) -> Decimal:
    row = db.query(MerchantThreshold).filter(MerchantThreshold.channel == channel).first()
    if row:
        return Decimal(row.min_productive_volume)
    return DEFAULT_THRESHOLDS[channel]


def set_threshold(db: Session, channel: MerchantChannel, value: Decimal, updated_by: Optional[str]) -> MerchantThreshold:
    row = db.query(MerchantThreshold).filter(MerchantThreshold.channel == channel).first()
    if row:
        row.min_productive_volume = value
        row.updated_by = updated_by
    else:
        row = MerchantThreshold(channel=channel, min_productive_volume=value, updated_by=updated_by)
        db.add(row)
    db.commit()
    return row


def classify_productivity(sales_volume: Optional[Decimal], threshold: Decimal) -> ProductivityStatus:
    v = sales_volume or Decimal(0)
    if v <= 0:
        return ProductivityStatus.TIDAK_ADA_TRANSAKSI
    if v < threshold:
        return ProductivityStatus.BELUM_PRODUKTIF
    return ProductivityStatus.PRODUKTIF


@dataclass
class ParsedMerchantRow:
    terminal_id: str
    merchant_ref: Optional[str]
    merchant_name: Optional[str]
    uker_name: Optional[str]
    account_number: Optional[str]
    sales_volume: Optional[float]
    status_raw: Optional[str]
    pemrakarsa_raw: Optional[str]
    raw: dict


def preview_merchant_file(file_path: str, filename: str) -> dict:
    detected = det.detect_report(file_path)
    if detected.report_type not in ("EDC", "QRIS"):
        return {
            "detected": False, "report_type": None, "periode": None, "rows": 0,
            "filename": filename,
            "error": detected.error or "File bukan format EDC/QRIS yang dikenali.",
        }

    periode_raw = None
    for r in range(detected.header_row_index + 1, len(detected.grid)):
        val = detected.grid[r][detected.field_columns["snapshot_date"]]
        if val is not None:
            periode_raw = val
            break

    row_count = 0
    tid_col = detected.field_columns.get("terminal_id")
    for r in range(detected.header_row_index + 1, len(detected.grid)):
        row = detected.grid[r]
        if tid_col is None or tid_col >= len(row):
            continue
        val = row[tid_col]
        if val is None or str(val).strip() == "":
            continue
        if str(val).strip().upper() in TOTAL_ROW_MARKERS:
            continue
        row_count += 1

    return {
        "detected": True,
        "report_type": detected.report_type,
        "periode": det.to_date(periode_raw),
        "rows": row_count,
        "filename": filename,
        "error": None,
    }


def _parse_rows(detected: det.DetectedSheet) -> list[ParsedMerchantRow]:
    fc = detected.field_columns
    tid_col = fc.get("terminal_id")
    parsed: list[ParsedMerchantRow] = []

    for r in range(detected.header_row_index + 1, len(detected.grid)):
        row = detected.grid[r]
        if tid_col is None or tid_col >= len(row):
            continue
        tid_raw = row[tid_col]
        if tid_raw is None or str(tid_raw).strip() == "":
            continue
        if str(tid_raw).strip().upper() in TOTAL_ROW_MARKERS:
            continue

        def get(field_name):
            col = fc.get(field_name)
            if col is None or col >= len(row):
                return None
            return row[col]

        raw_dict = {detected.all_headers.get(c, f"col_{c}"): (str(v) if v is not None else None)
                    for c, v in enumerate(row) if c in detected.all_headers}

        parsed.append(ParsedMerchantRow(
            terminal_id=det.to_str(tid_raw) or "",
            merchant_ref=det.to_str(get("merchant_ref")),
            merchant_name=det.to_str(get("merchant_name")),
            uker_name=det.to_str(get("uker_name")),
            account_number=det.to_str(get("account_number")),
            sales_volume=det.to_decimal(get("sales_volume")),
            status_raw=det.to_str(get("status")),
            pemrakarsa_raw=det.to_str(get("pemrakarsa")),
            raw=raw_dict,
        ))
    return parsed


def _resolve_pn_by_account(db: Session, account_number: Optional[str], as_of: date) -> Optional[str]:
    """The only ownership path for merchant rows: look up the linked account
    number in account_rmft_assignment (populated by every DPK upload) at the
    latest snapshot on/before `as_of`. No name matching, ever."""
    if not account_number:
        return None
    row = (
        db.query(AccountRmftAssignment)
        .filter(AccountRmftAssignment.account_number == account_number, AccountRmftAssignment.snapshot_date <= as_of)
        .order_by(AccountRmftAssignment.snapshot_date.desc())
        .first()
    )
    return row.primary_pn if row else None


def import_merchant_report(db: Session, file_path: str, filename: str, uploaded_by: Optional[str]) -> dict:
    detected = det.detect_report(file_path)
    if detected.report_type not in ("EDC", "QRIS"):
        return {"error": detected.error or "File bukan format EDC/QRIS yang dikenali.", "report_type": None}

    channel = CHANNEL_REPORT_TYPE[detected.report_type]

    periode_raw = None
    for r in range(detected.header_row_index + 1, len(detected.grid)):
        val = detected.grid[r][detected.field_columns["snapshot_date"]]
        if val is not None:
            periode_raw = val
            break
    snapshot_date_val = det.to_date(periode_raw)
    if snapshot_date_val is None:
        return {"error": "Tidak dapat menentukan PERIODE (tanggal posisi) dari file ini.", "report_type": detected.report_type}

    parsed_rows = _parse_rows(detected)

    # Dedupe within-file by terminal_id (constraint: never count one terminal twice)
    dedup: dict[str, ParsedMerchantRow] = {}
    duplicates_removed = 0
    for pr in parsed_rows:
        if pr.terminal_id in dedup:
            duplicates_removed += 1
        dedup[pr.terminal_id] = pr
    final_rows = list(dedup.values())

    threshold = get_threshold(db, channel)
    pn_to_name = {m.pn: m.rmft_name for m in db.query(RmftMaster).filter(RmftMaster.active.is_(True)).all()}

    resolved_count = 0
    unassigned_count = 0
    productive_count = 0

    batch = UploadBatch(
        filename=filename,
        report_type=ReportType(detected.report_type),
        product=detected.report_type,
        snapshot_date=snapshot_date_val,
        uploaded_by=uploaded_by,
        row_count=len(parsed_rows),
        valid_count=len(final_rows),
        duplicates_removed=duplicates_removed,
        status=UploadStatus.SUCCESS,
    )
    db.add(batch)
    db.flush()

    for idx, pr in enumerate(parsed_rows):
        db.add(RawImport(batch_id=batch.batch_id, row_index=idx, raw_json=json.dumps(pr.raw, default=str)))

    # REPLACE SNAPSHOT: delete any prior snapshot for this exact (channel, snapshot_date)
    db.query(MerchantSnapshot).filter(
        MerchantSnapshot.channel == channel, MerchantSnapshot.snapshot_date == snapshot_date_val,
    ).delete(synchronize_session=False)

    for pr in final_rows:
        resolved_pn = _resolve_pn_by_account(db, pr.account_number, snapshot_date_val)
        if resolved_pn:
            resolved_count += 1
        else:
            unassigned_count += 1

        productivity = classify_productivity(
            Decimal(str(pr.sales_volume)) if pr.sales_volume is not None else None, threshold,
        )
        if productivity == ProductivityStatus.PRODUKTIF:
            productive_count += 1

        db.add(MerchantSnapshot(
            snapshot_date=snapshot_date_val,
            channel=channel,
            terminal_id=pr.terminal_id,
            merchant_ref=pr.merchant_ref,
            merchant_name=pr.merchant_name,
            uker_name=pr.uker_name,
            account_number=pr.account_number,
            sales_volume=pr.sales_volume or 0,
            status_raw=pr.status_raw,
            pemrakarsa_raw=pr.pemrakarsa_raw,
            resolved_pn=resolved_pn,
            resolved_rmft=pn_to_name.get(resolved_pn) if resolved_pn else None,
            ownership_matched=resolved_pn is not None,
            productivity_status=productivity,
            upload_batch_id=batch.batch_id,
        ))

    batch.unassigned_count = unassigned_count
    db.commit()

    return {
        "error": None,
        "report_type": detected.report_type,
        "periode": snapshot_date_val,
        "total_rows": len(parsed_rows),
        "unique_terminals": len(final_rows),
        "duplicates_removed": duplicates_removed,
        "resolved": resolved_count,
        "unassigned": unassigned_count,
        "produktif": productive_count,
        "threshold": float(threshold),
        "batch_id": batch.batch_id,
        "status": batch.status.value,
    }


def get_latest_snapshot_date(db: Session, channel: MerchantChannel) -> Optional[date]:
    return db.query(func.max(MerchantSnapshot.snapshot_date)).filter(MerchantSnapshot.channel == channel).scalar()


def merchant_summary(db: Session, channel: Optional[MerchantChannel] = None, pn: Optional[str] = None) -> list[dict]:
    """Per-RMFT productivity counts, for the latest snapshot of each requested
    channel — the basis for the Admin productivity view and for the
    per-RMFT report's 'EDC/QRIS pending' section."""
    channels = [channel] if channel else [MerchantChannel.EDC, MerchantChannel.QRIS]
    out = []
    for ch in channels:
        latest = get_latest_snapshot_date(db, ch)
        if latest is None:
            continue
        q = db.query(MerchantSnapshot).filter(MerchantSnapshot.channel == ch, MerchantSnapshot.snapshot_date == latest)
        if pn:
            q = q.filter(MerchantSnapshot.resolved_pn == pn)
        rows = q.all()
        threshold = get_threshold(db, ch)
        produktif = sum(1 for r in rows if r.productivity_status == ProductivityStatus.PRODUKTIF)
        belum = sum(1 for r in rows if r.productivity_status == ProductivityStatus.BELUM_PRODUKTIF)
        nihil = sum(1 for r in rows if r.productivity_status == ProductivityStatus.TIDAK_ADA_TRANSAKSI)
        unassigned = sum(1 for r in rows if not r.ownership_matched)
        out.append({
            "channel": ch.value,
            "snapshot_date": latest,
            "threshold": float(threshold),
            "total_terminal": len(rows),
            "produktif": produktif,
            "belum_produktif": belum,
            "tidak_ada_transaksi": nihil,
            "pending": belum + nihil,  # section: "pendingan EDC/QRIS" — needs follow-up
            "unassigned": unassigned,
            "total_volume": float(sum(r.sales_volume or 0 for r in rows)),
        })
    return out


def top_terminals_by_volume(db: Session, channel: MerchantChannel, pn: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Top N terminals by sales volume, at the latest snapshot for the
    channel — the basis for the 'Top 10 EDC/QRIS by SV' section of the
    per-RMFT scorecard."""
    latest = get_latest_snapshot_date(db, channel)
    if latest is None:
        return []
    q = db.query(MerchantSnapshot).filter(MerchantSnapshot.channel == channel, MerchantSnapshot.snapshot_date == latest)
    if pn:
        q = q.filter(MerchantSnapshot.resolved_pn == pn)
    rows = q.order_by(MerchantSnapshot.sales_volume.desc()).limit(limit).all()
    return [{
        "terminal_id": r.terminal_id,
        "merchant_name": r.merchant_name,
        "account_number": r.account_number,
        "sales_volume": float(r.sales_volume or 0),
        "productivity_status": r.productivity_status.value,
    } for r in rows]


def merchant_list(
    db: Session, channel: Optional[MerchantChannel] = None, pn: Optional[str] = None,
    productivity_status: Optional[ProductivityStatus] = None, unassigned_only: bool = False,
) -> list[dict]:
    channels = [channel] if channel else [MerchantChannel.EDC, MerchantChannel.QRIS]
    out = []
    for ch in channels:
        latest = get_latest_snapshot_date(db, ch)
        if latest is None:
            continue
        q = db.query(MerchantSnapshot).filter(MerchantSnapshot.channel == ch, MerchantSnapshot.snapshot_date == latest)
        if pn:
            q = q.filter(MerchantSnapshot.resolved_pn == pn)
        if productivity_status:
            q = q.filter(MerchantSnapshot.productivity_status == productivity_status)
        if unassigned_only:
            q = q.filter(MerchantSnapshot.ownership_matched.is_(False))
        for r in q.order_by(MerchantSnapshot.sales_volume.asc()).all():
            out.append({
                "channel": ch.value,
                "snapshot_date": r.snapshot_date,
                "terminal_id": r.terminal_id,
                "merchant_name": r.merchant_name,
                "uker_name": r.uker_name,
                "account_number": r.account_number,
                "sales_volume": float(r.sales_volume or 0),
                "pn": r.resolved_pn,
                "rmft_name": r.resolved_rmft,
                "ownership_matched": r.ownership_matched,
                "productivity_status": r.productivity_status.value,
            })
    return out
