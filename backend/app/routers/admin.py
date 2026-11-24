from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_role, get_current_user
from ..ml import predict as ml, anomaly
from ..models import AuditLog, Disease, Symptom, Threshold, User, VaccineSchedule
from ..schemas import LookupIn, ScheduleIn, ThresholdIn
from ..scheduler.jobs import JOBS, run_job
from ..serializers import user_out
from ..services.common import audit, iso, paginate

router = APIRouter(tags=["admin"])
admin_only = require_role("admin")


@router.get("/lookups")
def lookups(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"symptoms": [{"id": s.id, "key": s.key, "name_en": s.name_en, "name_bn": s.name_bn} for s in db.query(Symptom).order_by(Symptom.id)],
            "diseases": [{"id": d.id, "key": d.key, "name_en": d.name_en, "name_bn": d.name_bn, "species_applicable": d.species_applicable} for d in db.query(Disease).order_by(Disease.id)],
            "schedules": [{"id": s.id, "species": s.species, "name": s.name, "kind": s.kind, "interval_days": s.interval_days} for s in db.query(VaccineSchedule).filter(VaccineSchedule.is_active.is_(True))]}


@router.get("/admin/users")
def users(role: str | None = None, is_approved: bool | None = None, q: str | None = None, page: int = 1, page_size: int = 50,
          user: User = Depends(admin_only), db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_approved is not None:
        query = query.filter(User.is_approved.is_(is_approved))
    if q:
        query = query.filter(User.name.ilike(f"%{q}%") | User.email.ilike(f"%{q}%"))
    items, total, page, page_size = paginate(query.order_by(User.id), page, page_size)
    return {"items": [user_out(u) for u in items], "total": total, "page": page, "page_size": page_size}


@router.patch("/admin/users/{uid}")
def patch_user(uid: int, body: dict, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "not_found")
    if "is_active" in body:
        if u.id == user.id:
            raise HTTPException(400, "cannot_deactivate_self")
        u.is_active = bool(body["is_active"])
    audit(db, user, "update", "user", u.id, {k: body[k] for k in body if k == "is_active"})
    db.commit()
    return user_out(u)


@router.patch("/admin/vets/{uid}/approve")
def approve_vet(uid: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u or u.role != "vet":
        raise HTTPException(404, "not_found")
    u.is_approved = True
    audit(db, user, "approve_vet", "user", u.id)
    db.commit()
    return user_out(u)


@router.get("/admin/thresholds")
def get_thresholds(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return [{"id": t.id, "species": t.species, "parameter": t.parameter, "min_value": t.min_value, "max_value": t.max_value}
            for t in db.query(Threshold).order_by(Threshold.parameter, Threshold.species)]


@router.put("/admin/thresholds")
def put_thresholds(body: list[ThresholdIn], user: User = Depends(admin_only), db: Session = Depends(get_db)):
    for t in body:
        row = db.query(Threshold).filter(Threshold.species == t.species, Threshold.parameter == t.parameter).first()
        if row:
            row.min_value, row.max_value = t.min_value, t.max_value
        else:
            db.add(Threshold(**t.model_dump()))
    audit(db, user, "update", "thresholds", None, {"count": len(body)})
    db.commit()
    return get_thresholds(user, db)


def _sched(s):
    return {"id": s.id, "species": s.species, "name": s.name, "kind": s.kind, "interval_days": s.interval_days,
            "first_dose_age_days": s.first_dose_age_days, "is_active": s.is_active}


@router.get("/admin/schedules")
def list_schedules(user: User = Depends(admin_only), db: Session = Depends(get_db)):
    return [_sched(s) for s in db.query(VaccineSchedule).order_by(VaccineSchedule.id)]


@router.post("/admin/schedules", status_code=201)
def create_schedule(body: ScheduleIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = VaccineSchedule(**body.model_dump())
    db.add(s); db.flush(); audit(db, user, "create", "schedule", s.id); db.commit()
    return _sched(s)


@router.put("/admin/schedules/{sid}")
def update_schedule(sid: int, body: ScheduleIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = db.get(VaccineSchedule, sid)
    if not s:
        raise HTTPException(404, "not_found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    audit(db, user, "update", "schedule", s.id); db.commit()
    return _sched(s)


@router.delete("/admin/schedules/{sid}")
def delete_schedule(sid: int, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = db.get(VaccineSchedule, sid)
    if not s:
        raise HTTPException(404, "not_found")
    s.is_active = False  # keep history: deactivate instead of deleting
    audit(db, user, "deactivate", "schedule", s.id); db.commit()
    return {"ok": True}


@router.post("/admin/symptoms", status_code=201)
def add_symptom(body: LookupIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.query(Symptom).filter(Symptom.key == body.key).first():
        raise HTTPException(409, "key_exists")
    s = Symptom(key=body.key, name_en=body.name_en, name_bn=body.name_bn)
    db.add(s); audit(db, user, "create", "symptom"); db.commit()
    return {"id": s.id, "key": s.key}


@router.put("/admin/symptoms/{sid}")
def edit_symptom(sid: int, body: LookupIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    s = db.get(Symptom, sid)
    if not s:
        raise HTTPException(404, "not_found")
    s.name_en, s.name_bn = body.name_en, body.name_bn
    db.commit()
    return {"id": s.id}


@router.post("/admin/diseases", status_code=201)
def add_disease(body: LookupIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    if db.query(Disease).filter(Disease.key == body.key).first():
        raise HTTPException(409, "key_exists")
    d = Disease(key=body.key, name_en=body.name_en, name_bn=body.name_bn, species_applicable=body.species_applicable or "cattle,goat,sheep")
    db.add(d); audit(db, user, "create", "disease"); db.commit()
    return {"id": d.id, "key": d.key}


@router.put("/admin/diseases/{did}")
def edit_disease(did: int, body: LookupIn, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    d = db.get(Disease, did)
    if not d:
        raise HTTPException(404, "not_found")
    d.name_en, d.name_bn = body.name_en, body.name_bn
    if body.species_applicable:
        d.species_applicable = body.species_applicable
    db.commit()
    return {"id": d.id}


@router.get("/admin/audit-log")
def audit_log(page: int = 1, page_size: int = 50, user: User = Depends(admin_only), db: Session = Depends(get_db)):
    items, total, page, page_size = paginate(db.query(AuditLog).order_by(AuditLog.id.desc()), page, page_size)
    names = {u.id: u.name for u in db.query(User).all()}
    return {"items": [{"id": a.id, "user": names.get(a.user_id), "action": a.action, "entity": a.entity, "entity_id": a.entity_id,
                       "detail": a.detail, "created_at": iso(a.created_at)} for a in items], "total": total, "page": page, "page_size": page_size}


@router.get("/admin/model")
def model_info(user: User = Depends(admin_only)):
    return {"available": ml.model_available(), "metrics": ml.model_metrics(),
            "anomaly_available": anomaly.available(), "anomaly_metrics": anomaly.metrics()}


@router.post("/admin/jobs/run")
def run(name: str, user: User = Depends(admin_only)):
    if name not in JOBS:
        raise HTTPException(404, "unknown_job")
    return {"job": name, "result": run_job(name)}
