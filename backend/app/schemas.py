from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    pn: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RmftOut(BaseModel):
    pn: str
    rmft_name: str
    active: bool

    class Config:
        from_attributes = True


class UploadPreviewProduct(BaseModel):
    detected: bool
    report_type: Optional[str] = None
    periode: Optional[date] = None
    date_printed: Optional[date] = None
    rows: int = 0
    header_row_index: Optional[int] = None
    filename: Optional[str] = None
    error: Optional[str] = None


class UploadPreviewResponse(BaseModel):
    tabungan: UploadPreviewProduct
    giro: UploadPreviewProduct
    deposito: UploadPreviewProduct
    overall_status: str  # COMPLETE / PARTIAL / DATE_MISMATCH


class UploadSummary(BaseModel):
    report_type: str
    periode: Optional[date]
    total_rows: int
    target_rmft_rows: int
    unique_accounts: int
    duplicates_removed: int
    pn_conflict: int
    unassigned: int
    invalid_balance: int
    status: str
    batch_id: str


class ImportResult(BaseModel):
    tabungan: Optional[UploadSummary] = None
    giro: Optional[UploadSummary] = None
    deposito: Optional[UploadSummary] = None


class DataPositionItem(BaseModel):
    product: str
    snapshot_date: Optional[date]
    is_latest: bool


class DataFreshness(BaseModel):
    items: list[DataPositionItem]
    status: str  # COMPLETE / PARTIAL / DATE_MISMATCH / NO_DATA
    as_of: Optional[date]


class FundingFigures(BaseModel):
    tabungan: float = 0
    giro: float = 0
    deposito: float = 0
    casa: float = 0
    dpk: float = 0


class RmftFundingCard(BaseModel):
    pn: str
    rmft_name: str
    current: FundingFigures
    mtd: FundingFigures
    dtd: FundingFigures
    account_count: int = 0


class HomeKpiResponse(BaseModel):
    freshness: DataFreshness
    unit_current: FundingFigures
    unit_mtd: FundingFigures
    unit_dtd: FundingFigures
    unit_mtd_growth_pct: float = 0
    rmft_cards: list[RmftFundingCard]


class TopMoverItem(BaseModel):
    rank: int
    pn: Optional[str]
    rmft_name: Optional[str]
    cif: Optional[str]
    customer: Optional[str]
    account_number: str
    product: Optional[str]
    baseline_or_previous: float
    current_balance: float
    delta: float
    delta_pct: Optional[float]
    status: Optional[str] = None  # NEW_ACCOUNT / ACCOUNT_MISSING / normal


# --- Section 29: Customer Followup -----------------------------------------
class FollowupCreate(BaseModel):
    cif: Optional[str] = None
    account_number: Optional[str] = None
    pn: Optional[str] = None
    date: date
    outflow_amount: Optional[float] = None
    status: str = "Belum Dihubungi"
    next_action: Optional[str] = None
    notes: Optional[str] = None


class FollowupUpdate(BaseModel):
    status: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None


# --- Section 32-34: Pipeline / Realization ----------------------------------
class PipelineCreate(BaseModel):
    pipeline_date: date
    pn: str
    cif: Optional[str] = None
    customer: Optional[str] = None
    account_number: Optional[str] = None
    category: Optional[str] = None       # FUNDING / TRANSACTION / FBI
    product: str
    nominal: float = 0
    fbi: float = 0
    probability: int = 0
    target_date: Optional[date] = None
    status: str = "Prospect"
    activity_today: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None


class PipelineUpdate(BaseModel):
    category: Optional[str] = None
    nominal: Optional[float] = None
    probability: Optional[int] = None
    target_date: Optional[date] = None
    status: Optional[str] = None
    activity_today: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None


class RealizationCreate(BaseModel):
    pipeline_id: str
    date: date
    realization_amount: float
    status: str = "Realisasi"   # Realisasi / Carry Over / Pending / Batal
    notes: Optional[str] = None


# --- Section 43: Target RMFT -------------------------------------------------
TARGET_PRODUCTS = ["Tabungan", "Giro", "Deposito", "DPK", "Payroll", "EDC", "QRIS", "Premi", "FBI"]


class TargetUpsert(BaseModel):
    month: str          # 'YYYY-MM'
    pn: str
    product: str
    target: float


# --- Section 2 / 60: user management ----------------------------------------
class UserCreate(BaseModel):
    username: str
    full_name: str
    password: str
    role: str            # ADMIN / RMFT
    pn: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    pn: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None


# --- Section 15: ownership conflict override --------------------------------
class OwnershipOverride(BaseModel):
    snapshot_date: date
    account_number: str
    override_pn: str


# --- Section 1 / Admin: RMFT master CRUD -------------------------------------
class RmftCreate(BaseModel):
    pn: str
    rmft_name: str
    active: bool = True


class RmftUpdate(BaseModel):
    rmft_name: Optional[str] = None
    active: Optional[bool] = None


# --- EDC/QRIS merchant productivity ------------------------------------------
class MerchantThresholdUpdate(BaseModel):
    channel: str          # EDC / QRIS
    min_productive_volume: float
