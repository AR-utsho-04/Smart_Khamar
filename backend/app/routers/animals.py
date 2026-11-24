from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_role, accessible_farm_ids, get_farm_checked, get_animal_checked, get_current_user
from ..models import (Animal, HealthRecord, Prediction, Reminder, Consultation, Alert, PredictionFeedback, User, utcnow)
from ..schemas import AnimalIn, AnimalUpdate, StatusIn, RecordIn
from ..serializers import animal_out, record_out, prediction_out, reminder_out, consultation_out
from ..services import pipeline
from ..services.common import audit, paginate, iso
from ..services.lookups import disease_map

router = APIRouter(tags=["animals"])
STATUSES = {"healthy", "under_observation", "sick", "recovered", "sold", "deceased"}


def _latest(db, animal_id):
    rec = db.query(HealthRecord).filter(HealthRecord.animal_id == animal_id).order_by(HealthRecord.recorded_at.desc()).first()
    pred = db.query(Prediction).filter(Prediction.animal_id == animal_id).order_by(Prediction.created_at.desc(), Prediction.id.desc()).first()
    return rec, pred


@router.get("/animals")
def list_animals(farm_id: int | None = None, species: str | None = None, status: str | None = None, q: str | None = None,
                 include_archived: bool = False, page: int = 1, page_size: int = 20,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = accessible_farm_ids(db, user)
    query = db.query(Animal)
    if ids is not None:
        query = query.filter(Animal.farm_id.in_(ids))
    if farm_id:
        query = query.filter(Animal.farm_id == farm_id)
    if species:
        query = query.filter(Animal.species == species)
    if status:
        query = query.filter(Animal.status == status)
    if not include_archived:
        query = query.filter(Animal.is_archived.is_(False))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Animal.tag_no.ilike(like), Animal.name.ilike(like)))
    items, total, page, page_size = paginate(query.order_by(Animal.tag_no), page, page_size)
    out = []
    for a in items:
        rec, pred = _latest(db, a.id)
        out.append(animal_out(a, latest_risk=pred.risk_level if pred else None,
                              last_record_at=iso(rec.recorded_at) if rec else None))
    return {"items": out, "total": total, "page": page, "page_size": page_size}


@router.post("/animals", status_code=201)
def create_animal(body: AnimalIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    farm = get_farm_checked(db, user, body.farm_id)
    if farm.owner_id != user.id:
        raise HTTPException(404, "not_found")
    if db.query(Animal).filter(Animal.farm_id == farm.id, Animal.tag_no == body.tag_no.strip()).first():
        raise HTTPException(409, "tag_exists")
    data = body.model_dump()
    data["tag_no"] = data["tag_no"].strip()
    a = Animal(**data)
    db.add(a)
    db.flush()
    audit(db, user, "create", "animal", a.id)
    db.commit()
    return animal_out(a)


@router.get("/animals/{animal_id}")
def get_animal(animal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    rec, pred = _latest(db, a.id)
    return animal_out(a, latest_record=record_out(rec) if rec else None,
                      latest_prediction=prediction_out(pred, disease_map(db)) if pred else None)


@router.put("/animals/{animal_id}")
def update_animal(animal_id: int, body: AnimalUpdate, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    data = body.model_dump(exclude_unset=True)
    if "tag_no" in data and data["tag_no"] != a.tag_no:
        if db.query(Animal).filter(Animal.farm_id == a.farm_id, Animal.tag_no == data["tag_no"]).first():
            raise HTTPException(409, "tag_exists")
    for k, v in data.items():
        setattr(a, k, v)
    audit(db, user, "update", "animal", a.id)
    db.commit()
    return animal_out(a)


@router.delete("/animals/{animal_id}")
def archive_animal(animal_id: int, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    a.is_archived = True
    audit(db, user, "archive", "animal", a.id)
    db.commit()
    return {"ok": True}


@router.patch("/animals/{animal_id}/status")
def set_status(animal_id: int, body: StatusIn, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    if body.status not in STATUSES:
        raise HTTPException(422, "invalid_status")
    a.status = body.status
    audit(db, user, "status", "animal", a.id, {"status": body.status})
    db.commit()
    return animal_out(a)


@router.post("/animals/{animal_id}/records", status_code=201)
def add_record(animal_id: int, body: RecordIn, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    out = pipeline.save_record(db, a, user, body.model_dump())
    audit(db, user, "create", "health_record", out["record"].id)
    db.commit()
    p = out["prediction"]
    return {"record": record_out(out["record"]),
            "prediction": prediction_out(p, disease_map(db)) if p else None,
            "alerts": [{"id": x.id, "type": x.type, "severity": x.severity} for x in out["alerts"]],
            "derived": out["derived"]}


@router.get("/animals/{animal_id}/records")
def list_records(animal_id: int, date_from: datetime | None = Query(None, alias="from"), date_to: datetime | None = Query(None, alias="to"),
                 page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    q = db.query(HealthRecord).filter(HealthRecord.animal_id == a.id)
    if date_from:
        q = q.filter(HealthRecord.recorded_at >= date_from.replace(tzinfo=None))
    if date_to:
        q = q.filter(HealthRecord.recorded_at <= date_to.replace(tzinfo=None))
    items, total, page, page_size = paginate(q.order_by(HealthRecord.recorded_at.desc()), page, page_size)
    return {"items": [record_out(r) for r in items], "total": total, "page": page, "page_size": page_size}


@router.get("/animals/{animal_id}/predictions")
def list_predictions(animal_id: int, page: int = 1, page_size: int = 20, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    items, total, page, page_size = paginate(db.query(Prediction).filter(Prediction.animal_id == a.id)
                                             .order_by(Prediction.created_at.desc(), Prediction.id.desc()), page, page_size)
    dm = disease_map(db)
    out = []
    for p in items:
        fb = db.query(PredictionFeedback).filter(PredictionFeedback.prediction_id == p.id).first()
        out.append(prediction_out(p, dm, feedback=fb))
    return {"items": out, "total": total, "page": page, "page_size": page_size}


@router.get("/animals/{animal_id}/timeline")
def timeline(animal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    dm, items = disease_map(db), []
    for r in db.query(HealthRecord).filter(HealthRecord.animal_id == a.id).order_by(HealthRecord.recorded_at.desc()).limit(40):
        bits = []
        if r.temperature_c is not None: bits.append(f"{r.temperature_c}°C")
        if r.weight_kg is not None: bits.append(f"{r.weight_kg} kg")
        if r.symptoms: bits.append(", ".join(s.name_en for s in r.symptoms))
        items.append({"type": "record", "at": iso(r.recorded_at), "summary": " | ".join(bits) or "Health record", "ref_id": r.id})
    for p in db.query(Prediction).filter(Prediction.animal_id == a.id).order_by(Prediction.created_at.desc()).limit(40):
        t = p.top_predictions[0] if p.top_predictions else None
        name = dm.get(t["disease_key"], (t["disease_key"],))[0] if t else "-"
        items.append({"type": "prediction", "at": iso(p.created_at), "summary": f"Risk {p.risk_level}: {name} ({round(t['probability']*100) if t else 0}%)", "ref_id": p.id})
    for c in db.query(Consultation).filter(Consultation.animal_id == a.id).order_by(Consultation.created_at.desc()).limit(20):
        items.append({"type": "consultation", "at": iso(c.created_at), "summary": f"Diagnosis: {c.diagnosis[:80]}", "ref_id": c.id})
    for r in db.query(Reminder).filter(Reminder.animal_id == a.id, Reminder.status == "done").order_by(Reminder.completed_at.desc()).limit(20):
        items.append({"type": "reminder", "at": iso(r.completed_at), "summary": f"Done: {r.title}", "ref_id": r.id})
    for al in db.query(Alert).filter(Alert.animal_id == a.id).order_by(Alert.created_at.desc()).limit(20):
        items.append({"type": "alert", "at": iso(al.created_at), "summary": al.message_en, "ref_id": al.id})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return items[:80]
