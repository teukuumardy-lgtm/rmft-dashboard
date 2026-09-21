from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import RmftMaster, User
from app.schemas import RmftOut

router = APIRouter(prefix="/rmft", tags=["rmft"])


@router.get("", response_model=list[RmftOut])
def list_rmft(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(RmftMaster).filter(RmftMaster.active.is_(True)).order_by(RmftMaster.rmft_name)
    return q.all()
