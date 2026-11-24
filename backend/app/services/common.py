from datetime import datetime, date, timezone
from fastapi import HTTPException
from ..models import AuditLog, utcnow


class ValidationFail(Exception):
    def __init__(self, errors):
        self.errors = errors


def audit(db, user, action, entity, entity_id=None, detail=None):
    db.add(AuditLog(user_id=user.id if user else None, action=action, entity=entity, entity_id=entity_id, detail=detail))


def iso(dt):
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat() + "Z"
    return dt.isoformat()


def to_naive_utc(dt: datetime | None) -> datetime:
    if dt is None:
        return utcnow()
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def animal_age_months(a) -> int | None:
    if a.dob:
        t = date.today()
        return max(0, (t.year - a.dob.year) * 12 + (t.month - a.dob.month))
    return a.age_months


def paginate(query, page: int, page_size: int):
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, page, page_size


def not_found():
    return HTTPException(404, "not_found")
