from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.services import wa_generator

router = APIRouter(prefix="/wa", tags=["wa"])


@router.get("/pagi")
def wa_pagi(
    target_date: date | None = None,
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 45: COPY WA PAGI."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    text = wa_generator.generate_wa_pagi(db, target_date or date.today(), scoped_pn=scoped_pn)
    return {"text": text}


@router.get("/sore")
def wa_sore(
    target_date: date | None = None,
    pn: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 46-48: COPY WA EOD."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    text = wa_generator.generate_wa_sore(db, target_date or date.today(), scoped_pn=scoped_pn)
    return {"text": text}
