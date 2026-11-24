import csv
import io
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..deps import require_role, get_farm_checked, get_animal_checked, get_current_user
from ..ml import predict as ml
from ..models import Animal, Disease, Farm, HealthRecord, Prediction, PredictionFeedback, User, utcnow
from ..schemas import FeedbackIn, SensorIn
from ..serializers import record_out, prediction_out
from ..services import pipeline
from ..services.common import ValidationFail, audit, to_naive_utc
from ..services.lookups import disease_map

router = APIRouter(tags=["records"])
MAX_ROWS, MAX_BYTES = 5000, 2 * 1024 * 1024


def _num(v):
    v = (v or "").strip()
    return float(v) if v else None


@router.post("/records/import")
async def import_csv(file: UploadFile = File(...), farm_id: int = Form(...),
                     user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    farm = get_farm_checked(db, user, farm_id)
    raw = await file.read()
    if len(raw) > MAX_BYTES:
        raise HTTPException(413, "file_too_large")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        rows = list(reader)
    except Exception:
        raise HTTPException(422, "invalid_csv")
    if not reader.fieldnames or "tag_no" not in reader.fieldnames:
        raise HTTPException(422, "missing_header_tag_no")
    if len(rows) > MAX_ROWS:
        raise HTTPException(422, "too_many_rows")
    animals = {a.tag_no: a for a in db.query(Animal).filter(Animal.farm_id == farm.id, Animal.is_archived.is_(False)).all()}
    errors, parsed = [], []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        try:
            tag = (row.get("tag_no") or "").strip()
            if tag not in animals:
                errors.append({"row": i, "field": "tag_no", "message": "animal not found"}); continue
            rt = (row.get("recorded_at") or "").strip()
            when = to_naive_utc(datetime.fromisoformat(rt.replace("Z", "+00:00"))) if rt else utcnow()
            data = {"recorded_at": when, "temperature_c": _num(row.get("temperature_c")), "weight_kg": _num(row.get("weight_kg")),
                    "feed_intake_kg": _num(row.get("feed_intake_kg")), "milk_yield_l": _num(row.get("milk_yield_l")),
                    "symptoms": [s.strip() for s in (row.get("symptoms") or "").split(";") if s.strip()],
                    "notes": (row.get("notes") or "").strip() or None}
            parsed.append((i, animals[tag], data))
        except ValueError:
            errors.append({"row": i, "field": "value", "message": "invalid date or number"})
    parsed.sort(key=lambda x: x[2]["recorded_at"])  # oldest first so 7-day trends are right
    imported = 0
    for i, animal, data in parsed:
        try:
            with db.begin_nested():
                pipeline.save_record(db, animal, user, data, source="csv", notify=data["recorded_at"] >= utcnow() - timedelta(days=1))
            imported += 1
        except ValidationFail as e:
            errors += [{"row": i, **x} for x in e.errors]
    audit(db, user, "import_csv", "health_record", None, {"imported": imported, "failed": len(rows) - imported})
    db.commit()
    errors.sort(key=lambda e: e["row"])
    return {"total_rows": len(rows), "imported": imported, "failed": len(rows) - imported, "errors": errors}


@router.get("/records/{record_id}")
def get_record(record_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.get(HealthRecord, record_id)
    if not r:
        raise HTTPException(404, "not_found")
    get_animal_checked(db, user, r.animal_id)
    return record_out(r)


@router.post("/records/{record_id}/predict")
def repredict(record_id: int, user: User = Depends(require_role("farmer", "vet")), db: Session = Depends(get_db)):
    r = db.get(HealthRecord, record_id)
    if not r:
        raise HTTPException(404, "not_found")
    a = get_animal_checked(db, user, r.animal_id)
    if not ml.model_available():
        raise HTTPException(503, "model_not_trained")
    out = pipeline.process_record(db, a, r)
    db.commit()
    return {"prediction": prediction_out(out["prediction"], disease_map(db)),
            "alerts": [{"id": x.id, "type": x.type, "severity": x.severity} for x in out["alerts"]]}


@router.get("/predictions/{pred_id}")
def get_prediction(pred_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    p = db.get(Prediction, pred_id)
    if not p:
        raise HTTPException(404, "not_found")
    get_animal_checked(db, user, p.animal_id)
    fb = db.query(PredictionFeedback).filter(PredictionFeedback.prediction_id == p.id).first()
    return prediction_out(p, disease_map(db), feedback=fb)


@router.post("/predictions/{pred_id}/feedback")
def feedback(pred_id: int, body: FeedbackIn, user: User = Depends(require_role("vet")), db: Session = Depends(get_db)):
    p = db.get(Prediction, pred_id)
    if not p:
        raise HTTPException(404, "not_found")
    get_animal_checked(db, user, p.animal_id)
    actual = None
    if body.actual_disease_key:
        d = db.query(Disease).filter(Disease.key == body.actual_disease_key).first()
        if not d:
            raise HTTPException(422, "unknown_disease")
        actual = d.id
    fb = db.query(PredictionFeedback).filter(PredictionFeedback.prediction_id == p.id).first()
    if fb:
        fb.confirmed, fb.actual_disease_id, fb.comment, fb.vet_id = body.confirmed, actual, body.comment, user.id
    else:
        db.add(PredictionFeedback(prediction_id=p.id, vet_id=user.id, confirmed=body.confirmed, actual_disease_id=actual, comment=body.comment))
    audit(db, user, "feedback", "prediction", p.id, {"confirmed": body.confirmed})
    db.commit()
    return {"ok": True, "confirmed": body.confirmed}


@router.post("/readings", status_code=201)
def sensor_reading(body: SensorIn, x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Sensor-ready endpoint (no hardware needed). Send header X-API-Key."""
    if x_api_key != settings.SENSOR_API_KEY:
        raise HTTPException(401, "invalid_api_key")
    farm = db.get(Farm, body.farm_id)
    animal = db.query(Animal).filter(Animal.farm_id == body.farm_id, Animal.tag_no == body.tag_no).first() if farm else None
    if not animal:
        raise HTTPException(404, "not_found")
    owner = db.get(User, farm.owner_id)
    data = body.model_dump(exclude={"farm_id", "tag_no"})
    data["symptoms"] = []
    out = pipeline.save_record(db, animal, owner, data, source="sensor")
    db.commit()
    return {"record_id": out["record"].id, "risk_level": out["prediction"].risk_level if out["prediction"] else None}
