"""Shared feature definitions. Used by data generation, training and prediction."""
import math
import numpy as np

SYMPTOMS = ["fever", "loss_of_appetite", "nasal_discharge", "mouth_lesions", "lameness", "skin_nodules",
            "diarrhea", "cough", "swollen_udder", "eye_discharge", "weakness", "reduced_milk_yield"]

SYMPTOM_NAMES = {
    "fever": ("Fever", "জ্বর"),
    "loss_of_appetite": ("Loss of appetite", "খাওয়া কমে যাওয়া"),
    "nasal_discharge": ("Nasal discharge", "নাক দিয়ে স্রাব পড়া"),
    "mouth_lesions": ("Mouth lesions or drooling", "মুখে ঘা বা লালা পড়া"),
    "lameness": ("Lameness", "খোঁড়ানো"),
    "skin_nodules": ("Skin nodules", "চামড়ায় গুটি"),
    "diarrhea": ("Diarrhea", "পাতলা পায়খানা"),
    "cough": ("Cough", "কাশি"),
    "swollen_udder": ("Swollen udder", "ওলান ফোলা"),
    "eye_discharge": ("Eye discharge", "চোখ দিয়ে পানি পড়া"),
    "weakness": ("Weakness", "দুর্বলতা"),
    "reduced_milk_yield": ("Reduced milk yield", "দুধ কমে যাওয়া"),
}

DISEASES = ["healthy", "fmd", "lsd", "mastitis", "bef", "ppr", "pox", "parasites"]

DISEASE_NAMES = {  # key: (name_en, name_bn, species_applicable)
    "healthy": ("Healthy", "সুস্থ", "cattle,goat,sheep"),
    "fmd": ("Foot-and-Mouth Disease", "ক্ষুরা রোগ", "cattle,goat,sheep"),
    "lsd": ("Lumpy Skin Disease", "লাম্পি স্কিন ডিজিজ", "cattle"),
    "mastitis": ("Mastitis", "ওলান প্রদাহ", "cattle,goat,sheep"),
    "bef": ("Bovine Ephemeral Fever", "তিন দিনের জ্বর", "cattle"),
    "ppr": ("PPR", "পিপিআর", "goat,sheep"),
    "pox": ("Goat/Sheep Pox", "ছাগল ও ভেড়ার বসন্ত", "goat,sheep"),
    "parasites": ("Internal Parasites", "অভ্যন্তরীণ পরজীবী", "cattle,goat,sheep"),
}
SPECIES_DISEASES = {s: [d for d in DISEASES if s in DISEASE_NAMES[d][2].split(",")] for s in ("cattle", "goat", "sheep")}

# Approximate upper limits of normal temperature (admin can change thresholds in the app).
TEMP_MAX = {"cattle": 39.5, "goat": 40.0, "sheep": 40.0}
TEMP_NORMAL = {"cattle": 38.6, "goat": 39.2, "sheep": 39.2}

CAT_COLS = ["species", "sex"]
NUM_COLS = ["age_months", "temperature_c", "weight_change_pct_7d", "feed_change_pct", "temp_above_max", "temp_missing"]
FEATURE_COLS = CAT_COLS + NUM_COLS + SYMPTOMS


def make_row(species, sex, age_months, temperature_c, weight_change, feed_change, symptoms, temp_max=None):
    """Build one feature dict. Missing temperature becomes NaN plus a flag."""
    tmax = temp_max if temp_max is not None else TEMP_MAX.get(species, 40.0)
    missing = temperature_c is None or (isinstance(temperature_c, float) and math.isnan(temperature_c))
    row = {
        "species": species,
        "sex": sex,
        "age_months": float(age_months) if age_months is not None else np.nan,
        "temperature_c": np.nan if missing else float(temperature_c),
        "weight_change_pct_7d": float(weight_change or 0.0),
        "feed_change_pct": float(feed_change or 0.0),
        "temp_above_max": 0.0 if missing else max(0.0, float(temperature_c) - tmax),
        "temp_missing": 1.0 if missing else 0.0,
    }
    for s in SYMPTOMS:
        row[s] = 1.0 if s in symptoms else 0.0
    return row
