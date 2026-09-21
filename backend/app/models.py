"""
SQLAlchemy models implementing the schema from spec section 55.

Phase 1-3 (this build) actively uses: User, RmftMaster, CustomerMaster,
AccountMaster, UploadBatch, RawImport, FundingSnapshot,
AccountRmftAssignment, AuditLog.

Pipeline, Realization, CustomerFollowup and RmftTarget tables are created
now (per section 55's full schema) so Phase 4+ can build directly on top
without a migration rewrite, but no business logic reads/writes them yet.
"""
import enum
import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Integer, BigInteger, Numeric, Date, DateTime, Boolean,
    ForeignKey, Text, UniqueConstraint, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"          # ADMIN / SBOH — section 2
    RMFT = "RMFT"


class ReportType(str, enum.Enum):
    TABUNGAN = "TABUNGAN"    # DI319
    GIRO = "GIRO"            # DI321
    DEPOSITO = "DEPOSITO"    # CI324
    EDC = "EDC"               # merchant EDC sales-volume export
    QRIS = "QRIS"             # merchant QRIS sales-volume export


class MerchantChannel(str, enum.Enum):
    EDC = "EDC"
    QRIS = "QRIS"


class ProductivityStatus(str, enum.Enum):
    """Terminal/merchant productivity for the snapshot's period, judged purely
    on transaction/sales volume against an admin-set minimum — never on the
    free-text 'pemrakarsa' name field (PN cross-reference decides ownership;
    see MerchantSnapshot.resolved_pn)."""
    PRODUKTIF = "PRODUKTIF"
    BELUM_PRODUKTIF = "BELUM_PRODUKTIF"          # has SOME volume, below minimum
    TIDAK_ADA_TRANSAKSI = "TIDAK_ADA_TRANSAKSI"  # zero volume this period


class UploadStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class OwnershipSource(str, enum.Enum):
    RM_DANA = "PN RM Dana/Mantri"
    PENGELOLA_SINGLEPN = "PN PENGELOLA SINGLEPN"
    RM_REFERRAL = "PN RM Referral"
    RELATIONSHIP_OFFICER = "PN Relationship Officer/RM Kredit Menengah"
    OTHER = "Kolom PN Lainnya"
    UNASSIGNED = "UNASSIGNED"


# ---------------------------------------------------------------------------
# Section 1: MASTER RMFT
# ---------------------------------------------------------------------------
class RmftMaster(Base):
    __tablename__ = "rmft_master"

    pn = Column(String(8), primary_key=True)          # 8-digit PN, primary key
    rmft_name = Column(String(120), nullable=False)
    active = Column(Boolean, default=True, nullable=False)

    users = relationship("User", back_populates="rmft")


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(80), unique=True, nullable=False, index=True)
    full_name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.RMFT)
    # For RMFT-role users: which PN they own (drives row-level access control)
    pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    rmft = relationship("RmftMaster", back_populates="users")


# ---------------------------------------------------------------------------
# Section 30: customer_master / account_master
# ---------------------------------------------------------------------------
class CustomerMaster(Base):
    __tablename__ = "customer_master"

    cif = Column(String(20), primary_key=True)
    customer_name = Column(String(255), nullable=False)


class AccountMaster(Base):
    __tablename__ = "account_master"

    account_number = Column(String(40), primary_key=True)  # stored as STRING — section 8/62
    cif = Column(String(20), ForeignKey("customer_master.cif"), nullable=True)
    customer_name = Column(String(255), nullable=True)
    product = Column(String(40), nullable=True)


# ---------------------------------------------------------------------------
# Section 55: upload_batch / raw_import
# ---------------------------------------------------------------------------
class UploadBatch(Base):
    __tablename__ = "upload_batch"

    batch_id = Column(String(36), primary_key=True, default=gen_uuid)
    filename = Column(String(255), nullable=False)
    report_type = Column(SAEnum(ReportType), nullable=False)
    product = Column(String(20), nullable=False)  # TABUNGAN/GIRO/DEPOSITO
    snapshot_date = Column(Date, nullable=False)     # from PERIODE, not Date Printed
    date_printed = Column(Date, nullable=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    row_count = Column(Integer, default=0)
    valid_count = Column(Integer, default=0)
    invalid_count = Column(Integer, default=0)
    duplicates_removed = Column(Integer, default=0)
    pn_conflict_count = Column(Integer, default=0)
    unassigned_count = Column(Integer, default=0)
    status = Column(SAEnum(UploadStatus), default=UploadStatus.SUCCESS)
    is_baseline = Column(Boolean, default=False)  # section 17: baseline bulanan flag


class RawImport(Base):
    """Section 54: raw, un-normalized row data exactly as parsed from the file."""
    __tablename__ = "raw_import"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    batch_id = Column(String(36), ForeignKey("upload_batch.batch_id"), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)
    raw_json = Column(Text, nullable=False)  # JSON-encoded original row (dict of raw header -> value)


# ---------------------------------------------------------------------------
# Section 55: funding_snapshot / account_rmft_assignment
# ---------------------------------------------------------------------------
class FundingSnapshot(Base):
    __tablename__ = "funding_snapshot"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    snapshot_date = Column(Date, nullable=False, index=True)
    report_type = Column(SAEnum(ReportType), nullable=False)
    account_number = Column(String(40), nullable=False, index=True)
    fdr_serial = Column(String(40), nullable=True)  # deposito only
    cif = Column(String(20), nullable=True, index=True)
    customer_name = Column(String(255), nullable=True)
    product = Column(String(40), nullable=True)
    product_code = Column(String(40), nullable=True)
    currency = Column(String(10), nullable=True)
    balance_original = Column(Numeric(20, 2), nullable=True)
    balance_idr = Column(Numeric(20, 2), nullable=False)  # calculation field (section 8/9/10)
    resolved_pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True, index=True)
    resolved_rmft = Column(String(120), nullable=True)
    ownership_source = Column(SAEnum(OwnershipSource), default=OwnershipSource.UNASSIGNED)
    conflict_flag = Column(Boolean, default=False)
    upload_batch_id = Column(String(36), ForeignKey("upload_batch.batch_id"), nullable=False)

    # Deposito extras
    maturity_date = Column(Date, nullable=True)
    issue_date = Column(Date, nullable=True)
    interest_rate = Column(Numeric(8, 4), nullable=True)
    tenor = Column(String(40), nullable=True)

    __table_args__ = (
        # Anti double count keys — section 16.
        # TABUNGAN/GIRO: snapshot_date + account_number
        # DEPOSITO: snapshot_date + account_number + fdr_serial
        UniqueConstraint("snapshot_date", "account_number", "report_type", "fdr_serial",
                          name="uq_funding_snapshot_key"),
        Index("ix_funding_snapshot_date_pn", "snapshot_date", "resolved_pn"),
    )


class AccountRmftAssignment(Base):
    """Section 13-15: PN ownership engine output, one row per account per snapshot date."""
    __tablename__ = "account_rmft_assignment"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    snapshot_date = Column(Date, nullable=False, index=True)
    account_number = Column(String(40), nullable=False, index=True)
    primary_pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True)
    secondary_pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True)
    ownership_source = Column(SAEnum(OwnershipSource), default=OwnershipSource.UNASSIGNED)
    conflict_flag = Column(Boolean, default=False)
    conflict_override_pn = Column(String(8), nullable=True)  # admin override — section 15
    overridden_by = Column(String(36), ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "account_number", name="uq_account_rmft_assignment"),
    )


# ---------------------------------------------------------------------------
# EDC / QRIS merchant productivity — upload-driven, same anti-double-count
# and PN-as-primary-key rules as funding_snapshot.
#
# The source files (edc_*.xlsx / qris_*.xlsx) carry a free-text RM name
# column ('NAMA_USER_PEMRAKARSA' / 'PN_PEMRAKASA') that is NOT a reliable PN
# and is never used to assign ownership (it is kept only as raw reference).
# Ownership is instead resolved the same way every other product is: the
# merchant's linked account number (NOREK/NO_REK) is looked up in
# account_rmft_assignment for the closest snapshot date <= this file's
# POSISI date, exactly like every DPK product. An account not found there
# is left UNASSIGNED and surfaced to admin, never guessed from the name.
# ---------------------------------------------------------------------------
class MerchantThreshold(Base):
    """Admin-editable minimum sales-volume (IDR) for a terminal/merchant to
    count as 'produktif' this period, per channel. Seeded from the bank's
    current policy (EDC Rp15.000.000, QRIS Rp50.000) but never hardcoded
    into calculation code, so a policy change is an admin edit, not a
    redeploy."""
    __tablename__ = "merchant_threshold"

    channel = Column(SAEnum(MerchantChannel), primary_key=True)
    min_productive_volume = Column(Numeric(20, 2), nullable=False)
    updated_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MerchantSnapshot(Base):
    __tablename__ = "merchant_snapshot"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    snapshot_date = Column(Date, nullable=False, index=True)
    channel = Column(SAEnum(MerchantChannel), nullable=False)
    terminal_id = Column(String(40), nullable=False)   # TID (EDC) / STOREID (QRIS)
    merchant_ref = Column(String(40), nullable=True)   # MID (EDC) / MERCHANT_PAN (QRIS)
    merchant_name = Column(String(255), nullable=True)
    uker_name = Column(String(120), nullable=True)
    account_number = Column(String(40), nullable=True, index=True)  # NOREK / NO_REK
    sales_volume = Column(Numeric(20, 2), nullable=False, default=0)
    status_raw = Column(String(40), nullable=True)      # QRIS 'STATUS' column (e.g. AKTIF); EDC has none
    pemrakarsa_raw = Column(String(255), nullable=True)  # raw name column — reference only, never matched on

    resolved_pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True, index=True)
    resolved_rmft = Column(String(120), nullable=True)
    ownership_matched = Column(Boolean, default=False)  # True only if account_number resolved via account_rmft_assignment

    productivity_status = Column(SAEnum(ProductivityStatus), nullable=False, default=ProductivityStatus.TIDAK_ADA_TRANSAKSI)
    upload_batch_id = Column(String(36), ForeignKey("upload_batch.batch_id"), nullable=False)

    __table_args__ = (
        # Anti double-count (same principle as funding_snapshot, section 16):
        # one row per terminal per channel per snapshot date.
        UniqueConstraint("snapshot_date", "channel", "terminal_id", name="uq_merchant_snapshot_key"),
        Index("ix_merchant_snapshot_date_pn", "snapshot_date", "resolved_pn"),
    )


# ---------------------------------------------------------------------------
# Baseline registry — section 17 / 71
# ---------------------------------------------------------------------------
class MonthlyBaseline(Base):
    __tablename__ = "monthly_baseline"

    baseline_month = Column(String(7), primary_key=True)  # 'YYYY-MM'
    baseline_date = Column(Date, nullable=False)
    set_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    set_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Future phases (schema created now, logic later) — section 55
# ---------------------------------------------------------------------------
class Pipeline(Base):
    __tablename__ = "pipeline"

    pipeline_id = Column(String(36), primary_key=True, default=gen_uuid)
    pipeline_date = Column(Date, nullable=False, index=True)
    pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=False)
    rmft = Column(String(120), nullable=True)
    cif = Column(String(20), nullable=True)
    customer = Column(String(255), nullable=True)
    account_number = Column(String(40), nullable=True)
    category = Column(String(20), nullable=True)   # FUNDING / TRANSACTION / FBI — section 32
    product = Column(String(60), nullable=True)
    nominal = Column(Numeric(20, 2), default=0)
    fbi = Column(Numeric(20, 2), default=0)
    probability = Column(Integer, default=0)
    target_date = Column(Date, nullable=True)
    status = Column(String(30), default="Prospect")
    activity_today = Column(Text, nullable=True)    # section 33: "Aktivitas Hari Ini"
    next_action = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    carried_from_id = Column(String(36), ForeignKey("pipeline.pipeline_id"), nullable=True)  # Copy Pipeline Kemarin lineage
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Realization(Base):
    __tablename__ = "realization"

    realization_id = Column(String(36), primary_key=True, default=gen_uuid)
    pipeline_id = Column(String(36), ForeignKey("pipeline.pipeline_id"), nullable=False)
    date = Column(Date, nullable=False)
    realization_amount = Column(Numeric(20, 2), default=0)
    status = Column(String(30), default="Realisasi")
    confirmation_source = Column(String(30), nullable=True)  # MANUAL / AUTO_MATCH
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class CustomerFollowup(Base):
    __tablename__ = "customer_followup"

    followup_id = Column(String(36), primary_key=True, default=gen_uuid)
    cif = Column(String(20), nullable=True)
    account_number = Column(String(40), nullable=True)
    pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=True)
    date = Column(Date, nullable=False)
    outflow_amount = Column(Numeric(20, 2), nullable=True)
    status = Column(String(30), default="Belum Dihubungi")
    next_action = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


class RmftTarget(Base):
    __tablename__ = "rmft_target"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    month = Column(String(7), nullable=False)  # 'YYYY-MM'
    pn = Column(String(8), ForeignKey("rmft_master.pn"), nullable=False)
    product = Column(String(40), nullable=False)
    target = Column(Numeric(20, 2), default=0)

    __table_args__ = (
        UniqueConstraint("month", "pn", "product", name="uq_rmft_target"),
    )


class DismissedMatch(Base):
    """Section 41: persisted 'Reject' on a Potential Pipeline Match, keyed by the
    specific pipeline+actual-account pairing shown (not the whole pipeline —
    a different actual account may legitimately match the same pipeline later,
    since the DTD-based candidate inflow recomputes daily)."""
    __tablename__ = "dismissed_match"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    pipeline_id = Column(String(36), ForeignKey("pipeline.pipeline_id"), nullable=False, index=True)
    actual_account_number = Column(String(40), nullable=False)
    dismissed_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    dismissed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("pipeline_id", "actual_account_number", name="uq_dismissed_match"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user = Column(String(120), nullable=True)
    action = Column(String(40), nullable=False)  # CREATE/UPDATE/DELETE/UPLOAD/LOGIN/OVERRIDE
    module = Column(String(60), nullable=False)
    record = Column(String(120), nullable=True)
    before_value = Column(Text, nullable=True)
    after_value = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
