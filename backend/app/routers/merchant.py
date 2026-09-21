from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import MerchantChannel, ProductivityStatus, User, UserRole
from app.services import merchant_calc

router = APIRouter(prefix="/merchant", tags=["merchant"])


def _parse_channel(channel: str | None) -> MerchantChannel | None:
    if not channel:
        return None
    try:
        return MerchantChannel(channel.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Channel harus EDC atau QRIS")


@router.get("/summary")
def summary(
    channel: str | None = Query(None),
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section: produktif/belum produktif/tidak ada transaksi per channel —
    RMFT-role users are scoped to their own PN (mirrors funding endpoints)."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    return merchant_calc.merchant_summary(db, channel=_parse_channel(channel), pn=scoped_pn)


@router.get("/list")
def merchant_list(
    channel: str | None = Query(None),
    pn: str | None = None,
    productivity_status: str | None = Query(None, alias="status"),
    unassigned_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    status_enum = None
    if productivity_status:
        try:
            status_enum = ProductivityStatus(productivity_status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail="status harus PRODUKTIF/BELUM_PRODUKTIF/TIDAK_ADA_TRANSAKSI")
    return merchant_calc.merchant_list(
        db, channel=_parse_channel(channel), pn=scoped_pn,
        productivity_status=status_enum, unassigned_only=unassigned_only,
    )
