"""AI anomaly detection for continuous sensor data (Isolation Forest).

How it works
  1. Train ONLY on normal behaviour (unsupervised): the model learns what usual readings look like.
  2. A reading far from normal gets a low score. The threshold is set so ~1% of normal readings are flagged.
  3. Safety rules also flag critical vitals (for example temperature >= 41 C), even if the model is unsure.
  4. An alert is raised only when the flags PERSIST (3 of the last 5 readings), so one noisy reading never alerts.
Run training:  python -m app.ml.anomaly   (also runs inside  python -m app.ml.train)"""
import json
from datetime import datetime, timezone
import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from ..config import settings
from . import telemetry as tm

_model, _loaded_from = None, None
SPECIES = ["cattle", "goat", "sheep"]


def _path():
    return settings.MODEL_DIR / "anomaly.joblib"


def load(force=False):
    global _model, _loaded_from
    p = _path()
    if (_model is None or force or _loaded_from != str(p)) and p.exists():
        _model, _loaded_from = joblib.load(p), str(p)
    return _model


def available() -> bool:
    return load() is not None


def metrics():
    p = settings.MODEL_DIR / "anomaly_metrics.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def score_batch(species, rows, base_temp=None, base_hr=None):
    """rows: list of (hour, temp, hr, act). Returns list of dict(score, ml_flag, critical, reasons, features)."""
    feats = [tm.feature_row(species, h, t, hr, a, base_temp, base_hr) for h, t, hr, a in rows]
    m = load()
    scores = m["model"].score_samples(np.array(feats)) if (m is not None and feats) else [None] * len(feats)
    out = []
    for f, s, (h, t, hr, a) in zip(feats, scores, rows):
        reasons = tm.reasons_for(f)
        crit = tm.is_critical(t, hr)
        ml_flag = bool(s < m["threshold"]) if m is not None else False
        out.append({"score": None if s is None else float(s), "ml_flag": ml_flag, "critical": crit,
                    "flag": bool(ml_flag or crit or reasons),  # model OR safety rules OR a clearly abnormal signal
                    "reasons": reasons, "features": f})
    return out


def _dataset(rng, n_animals, days, interval, with_episodes):
    X, y, ids, C = [], [], [], []
    n = int(days * 24 * 60 / interval)
    for a in range(n_animals):
        sp = SPECIES[a % 3]
        d = tm.simulate_animal(sp, n, rng, start_hour=rng.uniform(0, 24), interval_min=interval)
        label = np.zeros(n, dtype=int)
        episodes = []
        if with_episodes and rng.random() < 0.6:
            pos = 200
            for _ in range(int(rng.integers(1, 4))):
                start = int(rng.integers(pos, n - 60)) if pos < n - 61 else None
                if start is None:
                    break
                length = int(rng.integers(8, 19))
                tm.inject_episode(d, start, length, str(rng.choice(tm.KINDS)), rng)
                label[start:start + length] = 1
                episodes.append((start, start + length))
                pos = start + length + 60
        bt, bh = tm.baselines(d)
        for i in range(n):
            X.append(tm.feature_row(sp, d["hour"][i], d["temp"][i], d["hr"][i], d["act"][i],
                                    None if np.isnan(bt[i]) else bt[i], None if np.isnan(bh[i]) else bh[i]))
        y.extend(label.tolist())
        C.extend(bool(tm.is_critical(d['temp'][i], d['hr'][i])) for i in range(n))
        ids.append((sp, d, n, label, episodes))
    return np.array(X), np.array(y), ids, np.array(C)


def train_anomaly(model_dir=None, seed=7, interval=10, verbose=False):
    model_dir = model_dir or settings.MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    X, _, _, _ = _dataset(rng, n_animals=60, days=7, interval=interval, with_episodes=False)  # NORMAL data only
    model = IsolationForest(n_estimators=200, random_state=seed).fit(X)
    threshold = float(np.percentile(model.score_samples(X), 1.0))  # flag the most unusual 1% of normal readings

    # evaluation on NEW animals that include abnormal episodes (labels are known because we injected them)
    Xe, ye, animals, crit = _dataset(np.random.default_rng(seed + 1), n_animals=120, days=7, interval=interval, with_episodes=True)
    s = model.score_samples(Xe)
    rule = np.array([bool(tm.reasons_for(f)) for f in Xe])
    ml_flag = (s < threshold) | crit | rule  # same combination as the live system: model OR safety rules
    tp = int(((ml_flag) & (ye == 1)).sum()); fp = int(((ml_flag) & (ye == 0)).sum()); fn = int(((~ml_flag) & (ye == 1)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    # episode level: does the persistence rule raise an alert inside each episode? how many false alerts per animal-week?
    detected = total = false_alerts = 0
    pos = 0
    for sp, d, n, label, episodes in animals:
        flags = ml_flag[pos:pos + n]
        p = tm.persistent(flags, 5, 3) | tm.persistent(crit[pos:pos + n], 3, 2)
        pos += n
        for a, b in episodes:
            total += 1
            detected += int(p[a:b + 5].any())
        edges = [i for i in range(n) if p[i] and (i == 0 or not p[i - 1])]
        last = -999
        for i in edges:
            near_episode = any(a - 6 <= i <= b + 6 for a, b in episodes)
            if not near_episode and i - last > 12:
                false_alerts += 1
            last = i
    m = {"version": "iot-v1", "trained_at": datetime.now(timezone.utc).isoformat(), "synthetic_data": True,
         "algorithm": "Isolation Forest (200 trees) + signal rules + critical-vitals rules + persistence (3 of last 5)",
         "train_readings": int(len(X)), "eval_readings": int(len(Xe)), "threshold": round(threshold, 4),
         "reading_precision": round(prec, 3), "reading_recall": round(rec, 3),
         "reading_f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
         "episodes": total, "episodes_detected": detected,
         "episode_detection_rate": round(detected / total, 3) if total else 0.0,
         "limitations": "Low activity at night cannot be told apart from normal sleep, so lethargy is mainly detected in the daytime.",
         "false_alerts": false_alerts, "false_alerts_per_animal_week": round(false_alerts / len(animals), 3)}
    joblib.dump({"model": model, "threshold": threshold, "features": tm.FEATURES, "version": "iot-v1"}, model_dir / "anomaly.joblib")
    (model_dir / "anomaly_metrics.json").write_text(json.dumps(m, indent=2), encoding="utf-8")
    load(force=True)
    if verbose:
        print(f"Anomaly model: episode detection {m['episode_detection_rate']:.0%} ({detected}/{total}), "
              f"false alerts per animal-week {m['false_alerts_per_animal_week']}, reading F1 {m['reading_f1']}")
    return m


if __name__ == "__main__":
    train_anomaly(verbose=True)
