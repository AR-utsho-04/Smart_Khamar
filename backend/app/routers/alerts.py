from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import false
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_role, accessible_farm_ids, get_animal_checked, get_current_user
from ..models import Alert, Animal, Reminder, User, utcnow
from ..schemas import SnoozeIn, ReminderIn, ReminderPatch
from ..serializers import alert_out, reminder_out
from ..services import reminders as rem
from ..services.common import audit, paginate

router = APIRouter(tags=["alerts"])


def alert_query(db, user):
    q, ids = db.query(Alert), accessible_farm_ids(db, user)
    if ids is not None:
        q = q.filter(Alert.farm_id.in_(ids)) if ids else q.filter(false())
    if user.role == "vet":
        q = q.filter(Alert.severity == "high")
    return q


def _tags(db, rows):
    ids = {r.animal_id for r in rows if r.animal_id}
    return {a.id: a.tag_no for a in db.query(Animal).filter(Animal.id.in_(ids)).all()} if ids else {}


@router.get("/alerts")
def list_alerts(status: str | None = None, severity: str | None = None, farm_id: int | None = None, animal_id: int | None = None,
                page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = alert_query(db, user)
    if status and status != "all":
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    if farm_id:
        q = q.filter(Alert.farm_id == farm_id)
    if animal_id:
        q = q.filter(Alert.animal_id == animal_id)
    items, total, page, page_size = paginate(q.order_by(Alert.created_at.desc(), Alert.id.desc()), page, page_size)
    tags = _tags(db, items)
    return {"items": [alert_out(a, tags.get(a.animal_id)) for a in items], "total": total, "page": page, "page_size": page_size}


@router.get("/alerts/summary")
def alerts_summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = {"high": 0, "medium": 0, "low": 0}
    for a in alert_query(db, user).filter(Alert.status == "open").all():
        out[a.severity] += 1
    return {**out, "total": sum(out.values())}


def _get_alert(db, user, alert_id):
    a = alert_query(db, user).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(404, "not_found")
    return a


@router.patch("/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int, user: User = Depends(require_role("farmer", "vet", "admin")), db: Session = Depends(get_db)):
    a = _get_alert(db, user, alert_id)
    a.status, a.acknowledged_by, a.acknowledged_at, a.snoozed_until = "acknowledged", user.id, utcnow(), None
    db.commit()
    return alert_out(a)


@router.patch("/alerts/{alert_id}/snooze")
def snooze(alert_id: int, body: SnoozeIn, user: User = Depends(require_role("farmer", "vet", "admin")), db: Session = Depends(get_db)):
    a = _get_alert(db, user, alert_id)
    a.status, a.snoozed_until = "snoozed", utcnow() + timedelta(hours=body.hours)
    db.commit()
    return alert_out(a)


@router.patch("/alerts/{alert_id}/resolve")
def resolve(alert_id: int, user: User = Depends(require_role("farmer", "vet", "admin")), db: Session = Depends(get_db)):
    a = _get_alert(db, user, alert_id)
    a.status = "resolved"
    db.commit()
    return alert_out(a)


# ---------------- reminders ----------------
def _reminder_query(db, user):
    ids = accessible_farm_ids(db, user)
    q = db.query(Reminder).join(Animal, Animal.id == Reminder.animal_id).filter(Animal.is_archived.is_(False))
    if ids is not None:
        q = q.filter(Animal.farm_id.in_(ids)) if ids else q.filter(false())
    return q


@router.get("/reminders")
def list_reminders(status: str | None = None, animal_id: int | None = None, farm_id: int | None = None,
                   date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
                   page: int = 1, page_size: int = 50, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _reminder_query(db, user)
    if status:
        q = q.filter(Reminder.status.in_(status.split(",")))
    if animal_id:
        q = q.filter(Reminder.animal_id == animal_id)
    if farm_id:
        q = q.filter(Animal.farm_id == farm_id)
    if date_from:
        q = q.filter(Reminder.due_date >= date_from)
    if date_to:
        q = q.filter(Reminder.due_date <= date_to)
    items, total, page, page_size = paginate(q.order_by(Reminder.due_date), page, page_size)
    tags = {a.id: a.tag_no for a in db.query(Animal).filter(Animal.id.in_({r.animal_id for r in items})).all()} if items else {}
    return {"items": [reminder_out(r, tags.get(r.animal_id)) for r in items], "total": total, "page": page, "page_size": page_size}


@router.post("/animals/{animal_id}/reminders", status_code=201)
def add_reminder(animal_id: int, body: ReminderIn, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    r = Reminder(animal_id=a.id, **body.model_dump())
    db.add(r)
    db.commit()
    return reminder_out(r, a.tag_no)


@router.post("/animals/{animal_id}/reminders/generate")
def generate(animal_id: int, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    created = rem.generate_for_animal(db, a)
    db.commit()
    return {"created": len(created), "items": [reminder_out(r, a.tag_no) for r in created]}


@router.patch("/reminders/{reminder_id}")
def patch_reminder(reminder_id: int, body: ReminderPatch, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    r = db.get(Reminder, reminder_id)
    if not r:
        raise HTTPException(404, "not_found")
    a = get_animal_checked(db, user, r.animal_id)
    if body.due_date:
        r.due_date = body.due_date
        r.status = "pending" if r.status in ("overdue", "pending") and body.due_date >= date.today() else r.status
        r.notified_7d = r.notified_1d = r.notified_overdue = False
    if body.status == "done":
        rem.mark_done(db, r)
    elif body.status:
        r.status = body.status
    audit(db, user, "update", "reminder", r.id)
    db.commit()
    return reminder_out(r, a.tag_no)
