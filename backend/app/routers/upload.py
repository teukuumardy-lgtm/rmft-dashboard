import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.audit import log_action
from app.database import get_db
from app.deps import require_admin
from app.models import User
from app.services import import_engine

router = APIRouter(prefix="/upload", tags=["upload"])


def _save_temp(upload: UploadFile) -> str:
    suffix = Path(upload.filename).suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    shutil.copyfileobj(upload.file, tmp)
    tmp.close()
    return tmp.name


@router.post("/preview")
def preview(
    tabungan: UploadFile | None = File(None),
    giro: UploadFile | None = File(None),
    deposito: UploadFile | None = File(None),
    user: User = Depends(require_admin),
):
    """Section 18: preview detected report type / periode / row count for up to 3 files
    before committing an import. RMFT-role users see only their own data elsewhere in the
    app, but uploading daily positions is an Admin/SBOH action (section 2)."""
    result = {}
    for key, upload in [("tabungan", tabungan), ("giro", giro), ("deposito", deposito)]:
        if upload is None:
            result[key] = {"detected": False, "report_type": None, "periode": None,
                            "date_printed": None, "rows": 0, "header_row_index": None,
                            "filename": None, "error": None}
            continue
        path = _save_temp(upload)
        try:
            result[key] = import_engine.preview_file(path, upload.filename)
        finally:
            Path(path).unlink(missing_ok=True)

    dates = [v["periode"] for v in result.values() if v.get("periode")]
    detected_count = sum(1 for v in result.values() if v.get("detected"))
    if detected_count == 0:
        overall = "NO_DATA"
    elif detected_count < 3:
        overall = "PARTIAL"
    elif len(set(dates)) == 1:
        overall = "COMPLETE"
    else:
        overall = "DATE_MISMATCH"

    result["overall_status"] = overall
    return result


@router.post("/import")
def import_daily_position(
    tabungan: UploadFile | None = File(None),
    giro: UploadFile | None = File(None),
    deposito: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Section 18: IMPORT DAILY POSITION button."""
    output = {}
    for key, upload in [("tabungan", tabungan), ("giro", giro), ("deposito", deposito)]:
        if upload is None:
            continue
        path = _save_temp(upload)
        try:
            summary = import_engine.import_report(db, path, upload.filename, uploaded_by=user.id)
        finally:
            Path(path).unlink(missing_ok=True)
        output[key] = summary
        if not summary.get("error"):
            log_action(
                db, user.username, "UPLOAD", "funding_snapshot",
                record=summary.get("batch_id"),
                after=f"{summary.get('report_type')} periode={summary.get('periode')} rows={summary.get('valid_count' if 'valid_count' in summary else 'target_rmft_rows')} file={upload.filename}",
            )
    return output
