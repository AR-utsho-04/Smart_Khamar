import math
from datetime import timedelta
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import false
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import accessible_farm_ids, get_animal_checked, get_current_user, get_farm_checked, require_role
from ..models import Alert, Animal, Device, SensorReading, User, utcnow
from ..schemas import DeviceIn, DevicePatch, TelemetryIn
from ..services import iot
from ..services.common import ValidationFail, audit, iso

router = APIRouter(tags=["iot"])


def device_out(db, d, api_key=None):
    a = db.get(Animal, d.animal_id) if d.animal_id else None
    out = {"id": d.id, "farm_id": d.farm_id, "name": d.name, "device_uid": d.device_uid, "animal_id": d.animal_id,
           "animal_tag": a.tag_no if a else None, "is_active": d.is_active, "status": iot.device_status(db, d),
           "last_seen_at": iso(d.last_seen_at), "battery_pct": d.battery_pct, "created_at": iso(d.created_at)}
    if api_key:
        out["api_key"] = api_key  # shown only once
    return out


def _device(db, user, device_id):
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "not_found")
    get_farm_checked(db, user, d.farm_id)
    return d


def _check_animal(db, farm_id, animal_id, device_id=None):
    a = db.get(Animal, animal_id)
    if not a or a.farm_id != farm_id or a.is_archived:
        raise HTTPException(404, "not_found")
    other = db.query(Device).filter(Device.animal_id == animal_id, Device.is_active.is_(True), Device.id != (device_id or 0)).first()
    if other:
        raise HTTPException(409, "animal_has_device")


@router.post("/iot/devices", status_code=201)
def create_device(body: DeviceIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    farm = get_farm_checked(db, user, body.farm_id)
    if farm.owner_id != user.id:
        raise HTTPException(404, "not_found")
    if body.animal_id:
        _check_animal(db, farm.id, body.animal_id)
    key = iot.new_key()
    d = Device(farm_id=farm.id, animal_id=body.animal_id, name=body.name.strip(), device_uid=iot.new_uid(db), key_hash=iot.hash_key(key))
    db.add(d)
    db.flush()
    audit(db, user, "create", "device", d.id)
    db.commit()
    return device_out(db, d, api_key=key)


@router.get("/iot/devices")
def list_devices(farm_id: int | None = None, animal_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = accessible_farm_ids(db, user)
    q = db.query(Device)
    if ids is not None:
        q = q.filter(Device.farm_id.in_(ids)) if ids else q.filter(false())
    if farm_id:
        q = q.filter(Device.farm_id == farm_id)
    if animal_id:
        q = q.filter(Device.animal_id == animal_id)
    return [device_out(db, d) for d in q.order_by(Device.id).all()]


@router.patch("/iot/devices/{device_id}")
def update_device(device_id: int, body: DevicePatch, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    d = _device(db, user, device_id)
    data = body.model_dump(exclude_unset=True)
    if "animal_id" in data:
        if data["animal_id"] is not None:
            _check_animal(db, d.farm_id, data["animal_id"], d.id)
        d.animal_id = data["animal_id"]
    if data.get("name"):
        d.name = data["name"].strip()
    if "is_active" in data and data["is_active"] is not None:
        d.is_active = data["is_active"]
    audit(db, user, "update", "device", d.id)
    db.commit()
    return device_out(db, d)


@router.post("/iot/devices/{device_id}/rotate-key")
def rotate_key(device_id: int, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    d = _device(db, user, device_id)
    key = iot.new_key()
    d.key_hash = iot.hash_key(key)
    audit(db, user, "rotate_key", "device", d.id)
    db.commit()
    return device_out(db, d, api_key=key)


@router.get("/iot/summary")
def summary(farm_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = accessible_farm_ids(db, user)
    q = db.query(Device).filter(Device.is_active.is_(True))
    if ids is not None:
        q = q.filter(Device.farm_id.in_(ids)) if ids else q.filter(false())
    if farm_id:
        get_farm_checked(db, user, farm_id)
        q = q.filter(Device.farm_id == farm_id)
    devs = q.all()
    counts = {"online": 0, "offline": 0, "never_seen": 0, "unassigned": 0}
    for d in devs:
        counts[iot.device_status(db, d)] += 1
    aids = [d.animal_id for d in devs if d.animal_id]
    since = utcnow() - timedelta(hours=24)
    anomalous = len({r[0] for r in db.query(SensorReading.animal_id).filter(SensorReading.animal_id.in_(aids), SensorReading.recorded_at >= since,
                                                                           SensorReading.is_anomaly.is_(True)).all()}) if aids else 0
    open_alerts = db.query(Alert).filter(Alert.animal_id.in_(aids), Alert.type.in_(["iot_anomaly", "device_offline", "device_low_battery"]),
                                         Alert.status == "open").count() if aids else 0
    return {"devices": len(devs), **counts, "low_battery": sum(1 for d in devs if d.battery_pct is not None and d.battery_pct <= 15),
            "anomalous_animals_24h": anomalous, "open_iot_alerts": open_alerts}


@router.get("/iot/animals/{animal_id}/readings")
def readings(animal_id: int, hours: int = 24, max_points: int = 240, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    hours, max_points = min(max(hours, 1), 168), min(max(max_points, 20), 1000)
    rows = (db.query(SensorReading).filter(SensorReading.animal_id == a.id, SensorReading.recorded_at >= utcnow() - timedelta(hours=hours))
            .order_by(SensorReading.recorded_at).all())
    size = max(1, math.ceil(len(rows) / max_points))  # average neighbouring readings so charts stay light
    points = []
    for i in range(0, len(rows), size):
        g = rows[i:i + size]
        avg = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
        points.append({"t": iso(g[-1].recorded_at), "temperature_c": avg([r.temperature_c for r in g if r.temperature_c is not None]),
                       "heart_rate_bpm": avg([r.heart_rate_bpm for r in g if r.heart_rate_bpm is not None]),
                       "activity_index": avg([r.activity_index for r in g if r.activity_index is not None]),
                       "anomaly": any(r.is_anomaly for r in g)})
    devs = db.query(Device).filter(Device.animal_id == a.id, Device.is_active.is_(True)).all()
    last = rows[-1] if rows else None
    return {"points": points, "total_readings": len(rows), "anomalies": sum(1 for r in rows if r.is_anomaly),
            "devices": [device_out(db, d) for d in devs],
            "latest": {"t": iso(last.recorded_at), "temperature_c": last.temperature_c, "heart_rate_bpm": last.heart_rate_bpm,
                       "activity_index": last.activity_index, "anomaly": last.is_anomaly} if last else None}


@router.post("/iot/telemetry", status_code=201)
def telemetry(body: TelemetryIn, x_device_key: str | None = Header(default=None), db: Session = Depends(get_db)):
    """Called by the IoT device. Header: X-Device-Key. Body: one reading, or {"readings": [...]}."""
    if not x_device_key:
        raise HTTPException(401, "invalid_device_key")
    d = db.query(Device).filter(Device.key_hash == iot.hash_key(x_device_key)).first()
    if not d or not d.is_active:
        raise HTTPException(401, "invalid_device_key")
    items = [r.model_dump() for r in body.readings] if body.readings else [body.model_dump(exclude={"readings"})]
    result = iot.ingest(db, d, items)
    if result["accepted"] == 0:
        db.commit()
        raise ValidationFail([{"field": f"readings[{r['index']}]", "message": r["reason"]} for r in result["rejected"][:10]])
    db.commit()
    return result
