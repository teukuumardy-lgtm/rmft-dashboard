from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User, UserRole
from app.services import report_export

router = APIRouter(prefix="/reports", tags=["reports"])

MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("/preview")
def preview_report(
    report: str,
    pn: str | None = None,
    month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    date_: date | None = Query(None, alias="date"),
    mode: str = Query("MTD", pattern="^(MTD|DTD)$"),
    limit: int = 20,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Same dispatcher as /export, but returns the report as JSON so the
    frontend can show it inline before the user decides to download it
    (e.g. 'Report per RMFT' on the RMFT profile page)."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn
    params = {
        "pn": scoped_pn, "month": month, "date_from": date_from, "date_to": date_to,
        "date": date_, "mode": mode, "limit": limit, "status": status,
    }
    try:
        return report_export.build_report_rows(db, report, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/export")
def export_report(
    report: str,
    format: str = Query("xlsx", pattern="^(xlsx|pdf)$"),
    pn: str | None = None,
    month: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    date_: date | None = Query(None, alias="date"),
    mode: str = Query("MTD", pattern="^(MTD|DTD)$"),
    limit: int = 20,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Section 57: export any of the 9 report types as Excel or PDF.
    RMFT-role users are always scoped to their own PN (section 2), regardless
    of what `pn` is passed in the query string."""
    scoped_pn = user.pn if user.role == UserRole.RMFT else pn

    params = {
        "pn": scoped_pn, "month": month, "date_from": date_from, "date_to": date_to,
        "date": date_, "mode": mode, "limit": limit, "status": status,
    }
    try:
        result = report_export.build_report_rows(db, report, params)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if format == "xlsx":
        buf = report_export.to_excel(result)
    else:
        buf = report_export.to_pdf(result)

    filename = f"{report}_{date.today().isoformat()}.{format}"
    return StreamingResponse(
        buf, media_type=MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
