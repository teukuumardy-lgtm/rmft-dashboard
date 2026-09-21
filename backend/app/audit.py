from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(db: Session, user_label: str, action: str, module: str,
                record: str | None = None, before=None, after=None):
    db.add(AuditLog(
        user=user_label, action=action, module=module, record=record,
        before_value=str(before) if before is not None else None,
        after_value=str(after) if after is not None else None,
    ))
    db.commit()
