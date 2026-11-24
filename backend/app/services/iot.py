"""IoT pipeline: validate readings -> AI anomaly check -> persistence rule -> alert (+ email)."""
import hashlib
import secrets
from datetime import timedelta
from statistics import median
from ..ml import anomaly, telemetry as tm
from ..models import Animal, Device, SensorReading, utcnow
from .common import to_naive_utc
from .pipeline import create_alert, thr

MAX_BATCH = 200


def new_key() -> str:
    return "dev_" + secrets.token_urlsafe(24)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def new_uid(db) -> str:
    while True:
        uid = "DEV-" + secrets.token_hex(3).upper()
        if not db.query(Device).filter(Device.device_uid == uid).first():
            return uid


def device_status(db, d) -> str:
    if not d.animal_id:
        return "unassigned"
    if not d.last_seen_at:
        return "never_seen"
    minutes = thr(db, "all", "iot_offline_minutes") or 30
    return "online" if d.last_seen_at >= utcnow() - timedelta(minutes=minutes) else "offline"


def check_reading(r: dict):
    """Returns a reason text if the reading is invalid, else None."""
    t, hr, a, b = r.get("temperature_c"), r.get("heart_rate_bpm"), r.get("activity_index"), r.get("battery_pct")
    if t is None and hr is None and a is None:
        return "no measurement"
    if t is not None and not 25 <= t <= 45:
        return "temperature_c out of range (25-45)"
    if hr is not None and not 15 <= hr <= 260:
        return "heart_rate_bpm out of range (15-260)"
    if a is not None and not 0 <= a <= 100:
        return "activity_index out of range (0-100)"
    if b is not None and not 0 <= b <= 100:
        return "battery_pct out of range (0-100)"
    when = to_naive_utc(r.get("recorded_at"))
    if when > utcnow() + timedelta(minutes=5):
        return "recorded_at is in the future"
    if when < utcnow() - timedelta(days=7):
        return "recorded_at is older than 7 days"
    return None


def personal_baseline(db, animal):
    """Median temperature and heart rate of the animal's recent NORMAL readings (needs 12+ readings)."""
    rows = (db.query(SensorReading).filter(SensorReading.animal_id == animal.id, SensorReading.is_anomaly.is_(False))
            .order_by(SensorReading.recorded_at.desc()).limit(300).all())
    if len(rows) < 12:
        return None, None
    temps = [r.temperature_c for r in rows if r.temperature_c is not None]
    hrs = [r.heart_rate_bpm for r in rows if r.heart_rate_bpm is not None]
    return (median(temps) if len(temps) >= 12 else None), (median(hrs) if len(hrs) >= 12 else None)


def _trigger(last):
    """Alert rule on the newest readings (oldest first): 3 of last 5 flagged, or 2 of last 3 critical."""
    flags = [r.is_anomaly for r in last]
    crit = [r.is_critical for r in last]
    if len(flags) >= 3 and sum(flags[-5:]) >= 3:
        return True, any(crit[-3:])
    if len(crit) >= 2 and sum(crit[-3:]) >= 2:
        return True, True
    return False, False


def ingest(db, device: Device, readings: list, notify=True) -> dict:
    """readings: list of dicts (temperature_c, heart_rate_bpm, activity_index, battery_pct, recorded_at)."""
    accepted, rejected = [], []
    for i, r in enumerate(readings[:MAX_BATCH]):
        why = check_reading(r)
        (rejected.append({"index": i, "reason": why}) if why else accepted.append(r))
    for i in range(MAX_BATCH, len(readings)):
        rejected.append({"index": i, "reason": f"batch too large (max {MAX_BATCH})"})
    if not accepted:
        return {"accepted": 0, "rejected": rejected, "anomalies": 0, "alert_id": None, "analyzed": False}

    for r in accepted:
        r["recorded_at"] = to_naive_utc(r.get("recorded_at"))
    accepted.sort(key=lambda r: r["recorded_at"])
    device.last_seen_at = utcnow()
    batt = [r["battery_pct"] for r in accepted if r.get("battery_pct") is not None]
    if batt:
        device.battery_pct = batt[-1]

    animal = db.get(Animal, device.animal_id) if device.animal_id else None
    if not animal:  # stored, but nothing to analyse until the device is assigned to an animal
        for r in accepted:
            db.add(SensorReading(device_id=device.id, animal_id=None, recorded_at=r["recorded_at"], temperature_c=r.get("temperature_c"),
                                 heart_rate_bpm=r.get("heart_rate_bpm"), activity_index=r.get("activity_index")))
        return {"accepted": len(accepted), "rejected": rejected, "anomalies": 0, "alert_id": None, "analyzed": False}

    bt, bh = personal_baseline(db, animal)
    rows = [(r["recorded_at"].hour + r["recorded_at"].minute / 60.0, r.get("temperature_c"), r.get("heart_rate_bpm"), r.get("activity_index")) for r in accepted]
    results = anomaly.score_batch(animal.species, rows, bt, bh)
    reasons_seen = []
    for r, res in zip(accepted, results):
        db.add(SensorReading(device_id=device.id, animal_id=animal.id, recorded_at=r["recorded_at"], temperature_c=r.get("temperature_c"),
                             heart_rate_bpm=r.get("heart_rate_bpm"), activity_index=r.get("activity_index"),
                             anomaly_score=res["score"], is_anomaly=res["flag"], is_critical=res["critical"]))
        if res["flag"]:
            reasons_seen += res["reasons"]
    db.flush()
    last = (db.query(SensorReading).filter(SensorReading.animal_id == animal.id)
            .order_by(SensorReading.recorded_at.desc(), SensorReading.id.desc()).limit(5).all())[::-1]
    fire, critical = _trigger(last)
    alert = None
    if fire:
        keys = list(dict.fromkeys(reasons_seen)) or ["high_temp"]
        recent = [x for x in last if x.is_anomaly]
        if recent:  # recompute reasons from the stored flagged readings so the text matches what triggered the alert
            fr = [tm.feature_row(animal.species, x.recorded_at.hour + x.recorded_at.minute / 60.0, x.temperature_c, x.heart_rate_bpm, x.activity_index, bt, bh) for x in recent]
            keys = list(dict.fromkeys(k for f in fr for k in tm.reasons_for(f))) or keys
        params = {"device": device.name, "reasons_en": ", ".join(tm.REASONS[k][0] for k in keys), "reasons_bn": ", ".join(tm.REASONS[k][1] for k in keys)}
        severity = "high" if (critical or len(keys) >= 2) else "medium"
        alert = create_alert(db, animal, "iot_anomaly", severity, params, dedupe_hours=3, notify=notify)
        if alert and animal.status in ("healthy", "recovered"):
            animal.status = "under_observation"
    return {"accepted": len(accepted), "rejected": rejected, "anomalies": int(sum(r.is_anomaly for r in last[-len(accepted):])) if accepted else 0,
            "alert_id": alert.id if alert else None, "analyzed": True}


def offline_check(db):
    """Alert when a device stopped sending data, or its battery is low."""
    now, n = utcnow(), 0
    for d in db.query(Device).filter(Device.is_active.is_(True), Device.animal_id.isnot(None)).all():
        a = db.get(Animal, d.animal_id)
        if not a or a.is_archived:
            continue
        limit = int(thr(db, "all", "iot_offline_minutes") or 30)
        if d.last_seen_at and d.last_seen_at < now - timedelta(minutes=limit):
            mins = int((now - d.last_seen_at).total_seconds() // 60)
            n += bool(create_alert(db, a, "device_offline", "medium", {"device": d.name, "minutes": mins}, dedupe_hours=12))
        low = thr(db, "all", "iot_low_battery_pct") or 15
        if d.battery_pct is not None and d.battery_pct <= low:
            n += bool(create_alert(db, a, "device_low_battery", "low", {"device": d.name, "value": round(d.battery_pct)}, dedupe_hours=24))
    db.commit()
    return f"{n} device alerts"


def cleanup(db):
    days = int(thr(db, "all", "iot_retention_days") or 14)
    n = db.query(SensorReading).filter(SensorReading.recorded_at < utcnow() - timedelta(days=days)).delete()
    db.commit()
    return f"{n} old readings deleted"
