"""Seed lookup data (symptoms, diseases, thresholds, schedules). Safe to run many times."""
from ..models import Symptom, Disease, Threshold, VaccineSchedule
from ..ml.features import SYMPTOMS, SYMPTOM_NAMES, DISEASES, DISEASE_NAMES

# Approximate starting values. REVIEW WITH A VETERINARIAN before real use.
DEFAULT_THRESHOLDS = [
    ("cattle", "temperature_c", 38.0, 39.5), ("goat", "temperature_c", 38.5, 40.0), ("sheep", "temperature_c", 38.5, 40.0),
    ("all", "weight_drop_pct_7d", None, 5), ("all", "feed_drop_pct", None, 30),
    ("all", "risk_medium_cutoff", 0.30, None), ("all", "risk_high_cutoff", 0.60, None),
    ("all", "missed_entry_days", None, 2), ("all", "escalation_hours", None, 6),
    ("all", "fever_high_margin_c", None, 1.0),
    ("all", "iot_offline_minutes", None, 30), ("all", "iot_low_battery_pct", None, 15), ("all", "iot_retention_days", None, 14),
]
# Placeholder schedules. VERIFY intervals with a veterinarian / local livestock department.
DEFAULT_SCHEDULES = [
    ("all", "FMD vaccination", "vaccination", 180), ("cattle", "LSD vaccination", "vaccination", 365),
    ("goat", "PPR vaccination", "vaccination", 365), ("sheep", "PPR vaccination", "vaccination", 365),
    ("all", "Deworming", "deworming", 90), ("all", "General checkup", "checkup", 30),
]


def ensure_lookups(db):
    have = {s.key for s in db.query(Symptom).all()}
    for k in SYMPTOMS:
        if k not in have:
            db.add(Symptom(key=k, name_en=SYMPTOM_NAMES[k][0], name_bn=SYMPTOM_NAMES[k][1]))
    have = {d.key for d in db.query(Disease).all()}
    for k in DISEASES:
        if k not in have:
            en, bn, sp = DISEASE_NAMES[k]
            db.add(Disease(key=k, name_en=en, name_bn=bn, species_applicable=sp))
    have = {(t.species, t.parameter) for t in db.query(Threshold).all()}
    for sp, par, mn, mx in DEFAULT_THRESHOLDS:
        if (sp, par) not in have:
            db.add(Threshold(species=sp, parameter=par, min_value=mn, max_value=mx))
    if db.query(VaccineSchedule).count() == 0:
        for sp, name, kind, days in DEFAULT_SCHEDULES:
            db.add(VaccineSchedule(species=sp, name=name, kind=kind, interval_days=days))
    db.commit()


def disease_map(db):
    return {d.key: (d.name_en, d.name_bn) for d in db.query(Disease).all()}
