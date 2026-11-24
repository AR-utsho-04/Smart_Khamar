"""Load the trained model, predict disease probabilities and explain the result."""
import json
import joblib
import pandas as pd
from ..config import settings
from .features import (FEATURE_COLS, SYMPTOMS, SYMPTOM_NAMES, SPECIES_DISEASES, TEMP_NORMAL, make_row)

_model = None
_loaded_from = None


def model_path():
    return settings.MODEL_DIR / "model.joblib"


def load_model(force=False):
    global _model, _loaded_from
    p = model_path()
    if (_model is None or force or _loaded_from != str(p)) and p.exists():
        _model = joblib.load(p)
        _loaded_from = str(p)
    return _model


def model_available() -> bool:
    return load_model() is not None


def model_metrics():
    p = settings.MODEL_DIR / "metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _probs(m, rows):
    df = pd.DataFrame(rows)[FEATURE_COLS]
    return m["pipeline"].predict_proba(df), m["classes"]


def _apply_species_filter(probs, classes, species, sex=None):
    allowed = set(SPECIES_DISEASES.get(species, classes))
    if sex == "male":
        allowed.discard("mastitis")  # udder disease: not possible in males
    p = {c: (float(pr) if c in allowed else 0.0) for c, pr in zip(classes, probs)}
    total = sum(p.values()) or 1.0
    return {c: v / total for c, v in p.items()}


def predict(species, sex, age_months, temperature_c, weight_change, feed_change, symptoms, temp_max=None):
    """Returns dict(top_predictions, probabilities, top_factors, model_version) or None if no model."""
    m = load_model()
    if m is None:
        return None
    base = make_row(species, sex, age_months, temperature_c, weight_change, feed_change, set(symptoms), temp_max)
    variants, names = [base], [None]  # occlusion variants: neutralise one active factor at a time
    for s in symptoms:
        if s in SYMPTOMS:
            v = dict(base); v[s] = 0.0
            variants.append(v); names.append(("symptom", s))
    if base["temp_above_max"] > 0:
        v = dict(base); v["temp_above_max"] = 0.0; v["temperature_c"] = TEMP_NORMAL.get(species, 39.0)
        variants.append(v); names.append(("temperature_c", None))
    if base["feed_change_pct"] < -10:
        v = dict(base); v["feed_change_pct"] = 0.0
        variants.append(v); names.append(("feed_change_pct", None))
    if base["weight_change_pct_7d"] < -1:
        v = dict(base); v["weight_change_pct_7d"] = 0.0
        variants.append(v); names.append(("weight_change_pct_7d", None))

    P, classes = _probs(m, variants)
    probs = _apply_species_filter(P[0], classes, species, sex)
    ranked = sorted(probs.items(), key=lambda kv: kv[1], reverse=True)
    top3 = [{"disease_key": k, "probability": round(v, 2)} for k, v in ranked[:3]]

    # explain the strongest non-healthy candidate
    cand = next((k for k, _ in ranked if k != "healthy"), None)
    factors = []
    if cand:
        ci = classes.index(cand)
        base_p = _apply_species_filter(P[0], classes, species, sex)[cand]
        for i in range(1, len(variants)):
            drop = base_p - _apply_species_filter(P[i], classes, species, sex)[cand]
            kind, key = names[i]
            if drop <= 0.005:
                continue
            if kind == "symptom":
                en, bn = SYMPTOM_NAMES[key]
                feat = key
            else:
                feat = kind
                en, bn = {"temperature_c": ("High temperature", "উচ্চ তাপমাত্রা"),
                          "feed_change_pct": ("Reduced feed intake", "খাবার গ্রহণ কমে যাওয়া"),
                          "weight_change_pct_7d": ("Weight loss", "ওজন কমে যাওয়া")}[kind]
            factors.append({"feature": feat, "label_en": en, "label_bn": bn, "impact": round(float(drop), 3)})
        factors = sorted(factors, key=lambda f: f["impact"], reverse=True)[:3]
    return {"top_predictions": top3, "probabilities": probs, "top_factors": factors,
            "model_version": m.get("version", "v1")}
