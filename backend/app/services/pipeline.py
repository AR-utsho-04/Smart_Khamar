"""The record pipeline: validate -> derive -> rules -> predict -> risk -> alerts -> status -> notify."""
from datetime import timedelta
from ..config import settings
from ..ml import predict as ml
from ..models import (Alert, Animal, Farm, FarmVet, HealthRecord, Prediction, Symptom, Threshold, User, utcnow)
from . import messages
from .common import ValidationFail, animal_age_months, to_naive_utc
from .emailer import send_email

FALLBACK = {  # (species, parameter) -> (min, max)
    ("cattle", "temperature_c"): (38.0, 39.5), ("goat", "temperature_c"): (38.5, 40.0), ("sheep", "temperature_c"): (38.5, 40.0),
    ("all", "weight_drop_pct_7d"): (None, 5), ("all", "feed_drop_pct"): (None, 30),
    ("all", "risk_medium_cutoff"): (0.30, None), ("all", "risk_high_cutoff"): (0.60, None),
    ("all", "missed_entry_days"): (None, 2), ("all", "escalation_hours"): (None, 6), ("all", "fever_high_margin_c"): (None, 1.0),
}
WEIGHT_RANGE = {"cattle": (20, 1200), "goat": (2, 120), "sheep": (2, 150)}
KEY_SYMPTOMS = {"mouth_lesions", "skin_nodules", "nasal_discharge", "lameness", "diarrhea", "swollen_udder"}
PREDICTION_ALERTS = {"high_risk_prediction", "critical_safety_net"}


def thr(db, species, param, which="max"):
    row = db.query(Threshold).filter(Threshold.species == species, Threshold.parameter == param).first() \
        or db.query(Threshold).filter(Threshold.species == "all", Threshold.parameter == param).first()
    if row:
        return row.max_value if which == "max" else row.min_value
    fb = FALLBACK.get((species, param)) or FALLBACK.get(("all", param))
    return None if not fb else (fb[1] if which == "max" else fb[0])


def validate_record(db, animal, data, known_symptoms):
    errs = []
    def rng(field, lo, hi):
        v = data.get(field)
        if v is not None and not (lo <= v <= hi):
            errs.append({"field": field, "message": f"must be between {lo} and {hi}"})
    rng("temperature_c", 35.0, 43.0)
    lo, hi = WEIGHT_RANGE[animal.species]
    rng("weight_kg", lo, hi)
    rng("feed_intake_kg", 0, 60)
    rng("milk_yield_l", 0, 60)
    for s in data.get("symptoms", []):
        if s not in known_symptoms:
            errs.append({"field": "symptoms", "message": f"unknown symptom '{s}'"})
    if data.get("recorded_at") and to_naive_utc(data["recorded_at"]) > utcnow() + timedelta(minutes=5):
        errs.append({"field": "recorded_at", "message": "cannot be in the future"})
    has = any(data.get(f) is not None for f in ("temperature_c", "weight_kg", "feed_intake_kg", "milk_yield_l")) or data.get("symptoms")
    if not has:
        errs.append({"field": "record", "message": "enter at least one measurement or symptom"})
    if errs:
        raise ValidationFail(errs)


def derive(db, animal, record):
    wc = fc = 0.0
    if record.weight_kg:
        prev = db.query(HealthRecord).filter(
            HealthRecord.animal_id == animal.id, HealthRecord.id != record.id, HealthRecord.weight_kg.isnot(None),
            HealthRecord.recorded_at >= record.recorded_at - timedelta(days=9),
            HealthRecord.recorded_at <= record.recorded_at - timedelta(days=5)).order_by(HealthRecord.recorded_at.desc()).first()
        if prev and prev.weight_kg:
            wc = (record.weight_kg - prev.weight_kg) / prev.weight_kg * 100
    if record.feed_intake_kg is not None:
        rows = db.query(HealthRecord.feed_intake_kg).filter(
            HealthRecord.animal_id == animal.id, HealthRecord.id != record.id, HealthRecord.feed_intake_kg.isnot(None),
            HealthRecord.recorded_at >= record.recorded_at - timedelta(days=7),
            HealthRecord.recorded_at < record.recorded_at).all()
        vals = [r[0] for r in rows]
        if vals and sum(vals) > 0:
            avg = sum(vals) / len(vals)
            fc = (record.feed_intake_kg - avg) / avg * 100
    return round(wc, 2), round(fc, 2)


def notify_alert(db, alert, animal):
    farm = db.get(Farm, alert.farm_id)
    users = [db.get(User, farm.owner_id)]
    if alert.severity == "high":
        for fv in db.query(FarmVet).filter(FarmVet.farm_id == farm.id, FarmVet.status == "approved").all():
            v = db.get(User, fv.vet_id)
            if v and v.is_active and v.is_approved:
                users.append(v)
    for u in users:
        lang = u.language if u.language in ("en", "bn") else "en"
        msg = alert.message_bn if lang == "bn" else alert.message_en
        body = f"{msg}\n\nFarm: {farm.name}\nAnimal: {animal.tag_no}\n{settings.FRONTEND_URL}/animals/{animal.id}\n"
        if alert.type in PREDICTION_ALERTS:
            body += f"\n{messages.DISCLAIMER[lang]}\n"
        send_email(db, u, f"[Livestock {alert.severity.upper()}] {animal.tag_no}", body, alert.id)


def create_alert(db, animal, type_, severity, params, record_id=None, pred_id=None, dedupe=True, notify=True, dedupe_hours=24):
    if dedupe:
        dup = db.query(Alert).filter(Alert.animal_id == animal.id, Alert.type == type_,
                                     Alert.status.in_(["open", "acknowledged"]),
                                     Alert.created_at >= utcnow() - timedelta(hours=dedupe_hours)).first()
        if dup:
            return None
    en, bn = messages.render(type_, {**params, "tag": animal.tag_no})
    a = Alert(farm_id=animal.farm_id, animal_id=animal.id, type=type_, severity=severity, message_en=en, message_bn=bn,
              related_record_id=record_id, related_prediction_id=pred_id)
    db.add(a)
    db.flush()
    if notify:
        notify_alert(db, a, animal)
    return a


def risk_from(db, species, p_disease, temp, symptoms):
    """Risk level + safety net (rules from the spec, section 9.6)."""
    hi, med = thr(db, species, "risk_high_cutoff", "min"), thr(db, species, "risk_medium_cutoff", "min")
    level = "high" if p_disease >= hi else "medium" if p_disease >= med else "low"
    margin = thr(db, species, "fever_high_margin_c") or 1.0
    tmax = thr(db, species, "temperature_c")
    safety = bool(temp is not None and tmax is not None and temp > tmax + margin and len(KEY_SYMPTOMS & set(symptoms)) >= 2)
    return ("high" if safety else level), safety


def process_record(db, animal, record, notify=True):
    """Runs the whole pipeline for a saved record. Caller commits."""
    symptoms = [s.key for s in record.symptoms]
    wc, fc = derive(db, animal, record)
    if record.weight_kg:
        animal.weight_kg = record.weight_kg
    alerts, tmax = [], thr(db, animal.species, "temperature_c")

    if record.temperature_c is not None and tmax is not None and record.temperature_c > tmax:
        margin = thr(db, animal.species, "fever_high_margin_c") or 1.0
        sev = "high" if record.temperature_c > tmax + margin else "medium"
        alerts.append(create_alert(db, animal, "fever", sev, {"value": round(record.temperature_c, 1), "max": tmax}, record.id, notify=notify))
    wd = thr(db, animal.species, "weight_drop_pct_7d")
    if wd is not None and record.weight_kg and wc <= -wd:
        alerts.append(create_alert(db, animal, "weight_loss", "medium", {"value": abs(round(wc, 1))}, record.id, notify=notify))
    fd = thr(db, animal.species, "feed_drop_pct")
    if fd is not None and record.feed_intake_kg is not None and fc <= -fd:
        alerts.append(create_alert(db, animal, "appetite_drop", "medium", {"value": abs(round(fc, 1))}, record.id, notify=notify))

    pred, res = None, ml.predict(animal.species, animal.sex, animal_age_months(animal), record.temperature_c, wc, fc, symptoms, tmax)
    p_disease, top_disease, top_p = 0.0, None, 0.0
    if res:
        non_healthy = [(k, v) for k, v in res["probabilities"].items() if k != "healthy"]
        top_disease, top_p = max(non_healthy, key=lambda kv: kv[1])
        p_disease = top_p
    risk, safety = risk_from(db, animal.species, p_disease, record.temperature_c, symptoms)
    if res:
        pred = Prediction(record_id=record.id, animal_id=animal.id, model_version=res["model_version"],
                          top_predictions=res["top_predictions"], risk_level=risk, top_factors=res["top_factors"],
                          safety_net_triggered=safety, created_at=record.recorded_at)
        db.add(pred)
        db.flush()
    pid = pred.id if pred else None
    if res and risk == "high" and top_disease:
        from .lookups import disease_map
        en, bn = disease_map(db).get(top_disease, (top_disease, top_disease))
        alerts.append(create_alert(db, animal, "high_risk_prediction", "high",
                                   {"disease_en": en, "disease_bn": bn, "prob": round(top_p * 100)}, record.id, pid, notify=notify))
    if safety:
        alerts.append(create_alert(db, animal, "critical_safety_net", "high", {}, record.id, pid, notify=notify))

    if risk == "high" and animal.status in ("healthy", "recovered", "under_observation"):
        animal.status = "sick"
    elif risk == "medium" and animal.status in ("healthy", "recovered"):
        animal.status = "under_observation"
    return {"prediction": pred, "alerts": [a for a in alerts if a], "derived": {"weight_change_pct_7d": wc, "feed_change_pct": fc}}


def save_record(db, animal, user, data, source="manual", notify=True):
    """Validate, save and run the pipeline. `data` is a dict (see RecordIn)."""
    known = {s.key: s for s in db.query(Symptom).all()}
    validate_record(db, animal, data, known)
    rec = HealthRecord(animal_id=animal.id, recorded_by=user.id, recorded_at=to_naive_utc(data.get("recorded_at")),
                       temperature_c=data.get("temperature_c"), weight_kg=data.get("weight_kg"),
                       feed_intake_kg=data.get("feed_intake_kg"), milk_yield_l=data.get("milk_yield_l"),
                       notes=data.get("notes"), source=source)
    rec.symptoms = [known[s] for s in dict.fromkeys(data.get("symptoms", []))]
    db.add(rec)
    db.flush()
    out = process_record(db, animal, rec, notify=notify)
    out["record"] = rec
    return out
