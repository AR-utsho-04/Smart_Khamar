from .services.common import iso, animal_age_months


def user_out(u):
    return {"id": u.id, "name": u.name, "email": u.email, "phone": u.phone, "role": u.role,
            "language": u.language, "is_approved": u.is_approved, "is_active": u.is_active, "license_no": u.license_no}


def farm_out(f):
    return {"id": f.id, "owner_id": f.owner_id, "name": f.name, "district": f.district,
            "address": f.address, "species_kept": f.species_kept}


def animal_out(a, **extra):
    d = {"id": a.id, "farm_id": a.farm_id, "tag_no": a.tag_no, "name": a.name, "species": a.species,
         "breed": a.breed, "sex": a.sex, "dob": a.dob.isoformat() if a.dob else None,
         "age_months": animal_age_months(a), "weight_kg": a.weight_kg, "status": a.status,
         "photo_url": a.photo_url, "is_archived": a.is_archived, "created_at": iso(a.created_at)}
    d.update(extra)
    return d


def record_out(r):
    return {"id": r.id, "animal_id": r.animal_id, "recorded_by": r.recorded_by, "recorded_at": iso(r.recorded_at),
            "temperature_c": r.temperature_c, "weight_kg": r.weight_kg, "feed_intake_kg": r.feed_intake_kg,
            "milk_yield_l": r.milk_yield_l, "notes": r.notes, "source": r.source,
            "symptoms": [s.key for s in r.symptoms]}


def prediction_out(p, dmap, feedback=None):
    top = []
    for t in p.top_predictions:
        en, bn = dmap.get(t["disease_key"], (t["disease_key"], t["disease_key"]))
        top.append({**t, "name_en": en, "name_bn": bn})
    d = {"id": p.id, "record_id": p.record_id, "animal_id": p.animal_id, "model_version": p.model_version,
         "risk_level": p.risk_level, "top_predictions": top, "top_factors": p.top_factors,
         "safety_net_triggered": p.safety_net_triggered, "created_at": iso(p.created_at)}
    if feedback is not None:
        d["feedback"] = {"confirmed": feedback.confirmed, "comment": feedback.comment} if feedback else None
    return d


def alert_out(a, tag=None):
    return {"id": a.id, "farm_id": a.farm_id, "animal_id": a.animal_id, "animal_tag": tag, "type": a.type,
            "severity": a.severity, "message_en": a.message_en, "message_bn": a.message_bn, "status": a.status,
            "snoozed_until": iso(a.snoozed_until), "created_at": iso(a.created_at), "escalated": a.escalated}


def reminder_out(r, tag=None):
    return {"id": r.id, "animal_id": r.animal_id, "animal_tag": tag, "type": r.type, "title": r.title,
            "due_date": r.due_date.isoformat(), "status": r.status, "completed_at": iso(r.completed_at)}


def consultation_out(c, vet_name=None, tag=None):
    return {"id": c.id, "animal_id": c.animal_id, "animal_tag": tag, "vet_id": c.vet_id, "vet_name": vet_name,
            "prediction_id": c.prediction_id, "diagnosis": c.diagnosis, "treatment": c.treatment,
            "medicine": c.medicine, "dosage": c.dosage,
            "follow_up_date": c.follow_up_date.isoformat() if c.follow_up_date else None,
            "created_at": iso(c.created_at)}
