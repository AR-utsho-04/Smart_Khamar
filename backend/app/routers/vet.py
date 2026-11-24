from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_role, accessible_farm_ids, get_animal_checked, get_current_user
from ..models import (Alert, Animal, Consultation, ConsultationComment, Farm, HealthRecord, Prediction, Reminder, User)
from ..schemas import ConsultationIn, CommentIn
from ..serializers import animal_out, consultation_out
from ..services.common import audit, paginate, iso

router = APIRouter(tags=["vet"])


@router.get("/consultations/queue")
def queue(user: User = Depends(require_role("vet")), db: Session = Depends(get_db)):
    ids = accessible_farm_ids(db, user)
    if not ids:
        return []
    out = []
    for a in db.query(Animal).filter(Animal.farm_id.in_(ids), Animal.is_archived.is_(False)).all():
        high = db.query(Alert).filter(Alert.animal_id == a.id, Alert.severity == "high", Alert.status == "open").count()
        if a.status not in ("sick", "under_observation") and not high:
            continue
        pred = db.query(Prediction).filter(Prediction.animal_id == a.id).order_by(Prediction.created_at.desc(), Prediction.id.desc()).first()
        rec = db.query(HealthRecord).filter(HealthRecord.animal_id == a.id).order_by(HealthRecord.recorded_at.desc()).first()
        farm = db.get(Farm, a.farm_id)
        out.append(animal_out(a, farm_name=farm.name, latest_risk=pred.risk_level if pred else None,
                              last_record_at=iso(rec.recorded_at) if rec else None, open_high_alerts=high))
    rank = {"high": 0, "medium": 1, "low": 2, None: 3}
    out.sort(key=lambda x: (-x["open_high_alerts"], rank[x["latest_risk"]], x["status"] != "sick"))
    return out


@router.get("/consultations")
def list_consultations(animal_id: int | None = None, farm_id: int | None = None, page: int = 1, page_size: int = 20,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = db.query(Consultation).join(Animal, Animal.id == Consultation.animal_id)
    if user.role == "vet":
        q = q.filter(Consultation.vet_id == user.id)
    elif user.role == "farmer":
        ids = accessible_farm_ids(db, user)
        q = q.filter(Animal.farm_id.in_(ids)) if ids else q.filter(false())
    if animal_id:
        q = q.filter(Consultation.animal_id == animal_id)
    if farm_id:
        q = q.filter(Animal.farm_id == farm_id)
    items, total, page, page_size = paginate(q.order_by(Consultation.created_at.desc()), page, page_size)
    vets = {u.id: u.name for u in db.query(User).filter(User.id.in_({c.vet_id for c in items})).all()} if items else {}
    tags = {a.id: a.tag_no for a in db.query(Animal).filter(Animal.id.in_({c.animal_id for c in items})).all()} if items else {}
    return {"items": [consultation_out(c, vets.get(c.vet_id), tags.get(c.animal_id)) for c in items],
            "total": total, "page": page, "page_size": page_size}


@router.post("/animals/{animal_id}/consultations", status_code=201)
def create_consultation(animal_id: int, body: ConsultationIn, user: User = Depends(require_role("vet")), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    if body.prediction_id:
        p = db.get(Prediction, body.prediction_id)
        if not p or p.animal_id != a.id:
            raise HTTPException(422, "invalid_prediction")
    c = Consultation(animal_id=a.id, vet_id=user.id, **body.model_dump())
    db.add(c)
    db.flush()
    if body.follow_up_date:
        db.add(Reminder(animal_id=a.id, type="follow_up", title=f"Follow-up: {body.diagnosis[:60]}", due_date=body.follow_up_date))
    audit(db, user, "create", "consultation", c.id)
    db.commit()
    return consultation_out(c, user.name, a.tag_no)


@router.get("/consultations/{cid}")
def get_consultation(cid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    c = db.get(Consultation, cid)
    if not c:
        raise HTTPException(404, "not_found")
    a = get_animal_checked(db, user, c.animal_id)
    vet = db.get(User, c.vet_id)
    comments = []
    for m in db.query(ConsultationComment).filter(ConsultationComment.consultation_id == c.id).order_by(ConsultationComment.created_at).all():
        u = db.get(User, m.user_id)
        comments.append({"id": m.id, "user_name": u.name, "role": u.role, "body": m.body, "created_at": iso(m.created_at)})
    return {**consultation_out(c, vet.name, a.tag_no), "comments": comments}


@router.post("/consultations/{cid}/comments", status_code=201)
def add_comment(cid: int, body: CommentIn, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    c = db.get(Consultation, cid)
    if not c:
        raise HTTPException(404, "not_found")
    get_animal_checked(db, user, c.animal_id)
    m = ConsultationComment(consultation_id=c.id, user_id=user.id, body=body.body.strip())
    db.add(m)
    db.commit()
    return {"id": m.id, "user_name": user.name, "role": user.role, "body": m.body, "created_at": iso(m.created_at)}
