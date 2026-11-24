"""Synthetic training data generator.

IMPORTANT: The profiles below are SIMPLIFIED DEMO ASSUMPTIONS, not clinical data.
Replace or validate them with real veterinary data before any real-world use.
"""
import numpy as np
import pandas as pd
from .features import SYMPTOMS, DISEASES, SPECIES_DISEASES, TEMP_NORMAL, make_row, FEATURE_COLS

# disease: (temp_mean, temp_sd, {symptom: prob}, (weight_mean, weight_sd), (feed_mean, feed_sd))
PROFILES = {
    "healthy": (None, 0.3, {}, (0, 1.5), (0, 10)),
    "fmd": (40.2, 0.5, {"mouth_lesions": .9, "lameness": .7, "loss_of_appetite": .9, "reduced_milk_yield": .6, "weakness": .5, "fever": .8}, (-3, 2), (-45, 15)),
    "lsd": (40.0, 0.5, {"skin_nodules": .95, "nasal_discharge": .5, "eye_discharge": .5, "loss_of_appetite": .7, "reduced_milk_yield": .7, "lameness": .3, "fever": .8}, (-3, 2), (-35, 15)),
    "mastitis": (39.8, 0.5, {"swollen_udder": .95, "reduced_milk_yield": .9, "loss_of_appetite": .4, "fever": .6}, (-1, 1.5), (-20, 12)),
    "bef": (40.5, 0.5, {"lameness": .8, "weakness": .7, "loss_of_appetite": .8, "nasal_discharge": .4, "reduced_milk_yield": .7, "fever": .9}, (-2, 2), (-40, 15)),
    "ppr": (41.0, 0.5, {"nasal_discharge": .9, "eye_discharge": .8, "mouth_lesions": .7, "diarrhea": .7, "cough": .6, "loss_of_appetite": .9, "fever": .9}, (-4, 2), (-50, 15)),
    "pox": (40.5, 0.5, {"skin_nodules": .95, "nasal_discharge": .5, "eye_discharge": .4, "loss_of_appetite": .7, "fever": .8}, (-3, 2), (-35, 15)),
    "parasites": (39.3, 0.4, {"diarrhea": .8, "weakness": .7, "loss_of_appetite": .5}, (-5, 3), (-15, 10)),
}


def generate(n=6000, seed=42, noise=0.05, missing_temp=0.03) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        disease = DISEASES[i % len(DISEASES)]  # balanced classes
        species = rng.choice([s for s in SPECIES_DISEASES if disease in SPECIES_DISEASES[s]])
        sex = "female" if disease == "mastitis" else rng.choice(["male", "female"])  # mastitis affects the udder
        age = float(rng.integers(6, 121))
        tmean, tsd, probs, (wm, ws), (fm, fs) = PROFILES[disease]
        tmean = TEMP_NORMAL[species] if tmean is None else tmean
        temp = float(rng.normal(tmean, tsd))
        if rng.random() < missing_temp:
            temp = None
        default_p = 0.03 if disease == "healthy" else 0.05
        syms = {s for s in SYMPTOMS if rng.random() < probs.get(s, default_p)}
        if sex == "male":
            syms.discard("swollen_udder")
            syms.discard("reduced_milk_yield")
        row = make_row(species, sex, age, temp, float(rng.normal(wm, ws)), float(rng.normal(fm, fs)), syms)
        row["label"] = disease
        rows.append(row)
    df = pd.DataFrame(rows)
    flip = rng.random(len(df)) < noise  # label noise so scores are not trivially perfect
    df.loc[flip, "label"] = rng.choice(DISEASES, size=int(flip.sum()))
    return df[FEATURE_COLS + ["label"]]


if __name__ == "__main__":
    d = generate(200)
    print(d.head())
