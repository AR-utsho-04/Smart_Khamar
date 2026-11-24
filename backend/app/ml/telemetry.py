"""IoT telemetry: normal-behaviour simulation, feature engineering and persistence rule.
Used by the anomaly model (training and live scoring) and by scripts/iot_simulator.py.

NOTE: baselines below are approximate placeholders for demonstration. Confirm them with a veterinarian."""
import math
import numpy as np
from .features import TEMP_NORMAL

HR_NORMAL = {"cattle": 65.0, "goat": 80.0, "sheep": 75.0}  # resting heart rate (beats per minute), approximate
FEATURES = ["temp_dev_species", "hr_dev_pct", "activity_dev", "temp_vs_baseline", "hr_vs_baseline_pct"]
CRIT_TEMP_HIGH, CRIT_TEMP_LOW, CRIT_HR_HIGH, CRIT_HR_LOW = 41.0, 36.5, 130.0, 30.0

REASONS = {  # key: (English, Bangla)
    "high_temp": ("high temperature", "উচ্চ তাপমাত্রা"), "low_temp": ("low temperature", "কম তাপমাত্রা"),
    "high_hr": ("high heart rate", "উচ্চ হৃদস্পন্দন"), "low_hr": ("low heart rate", "কম হৃদস্পন্দন"),
    "low_activity": ("low activity", "কম নড়াচড়া"), "high_activity": ("unusually high activity", "অস্বাভাবিক বেশি নড়াচড়া"),
}


def expected_activity(hour: float) -> float:
    """Normal daily rhythm: active in the afternoon, resting at night (index 0-100)."""
    return 40 + 30 * math.sin(2 * math.pi * (hour - 9) / 24)


def expected_temp(species: str, hour: float) -> float:
    return TEMP_NORMAL[species] + 0.15 * math.sin(2 * math.pi * (hour - 10) / 24)


def expected_hr(species: str, hour: float) -> float:
    return HR_NORMAL[species] + 0.15 * (expected_activity(hour) - 40)


def feature_row(species, hour, temp, hr, act, base_temp=None, base_hr=None):
    """Features for ONE reading. Missing hr/activity become neutral (0 deviation), so temperature-only devices work."""
    bt = base_temp if base_temp is not None else TEMP_NORMAL[species]
    bh = base_hr if base_hr is not None else HR_NORMAL[species]
    return [
        (temp - expected_temp(species, hour)) if temp is not None else 0.0,
        ((hr - expected_hr(species, hour)) / HR_NORMAL[species] * 100) if hr is not None else 0.0,
        (act - expected_activity(hour)) if act is not None else 0.0,
        (temp - bt) if temp is not None else 0.0,
        ((hr - bh) / bh * 100) if hr is not None else 0.0,
    ]


def is_critical(temp, hr) -> bool:
    return bool((temp is not None and (temp >= CRIT_TEMP_HIGH or temp <= CRIT_TEMP_LOW)) or
                (hr is not None and (hr >= CRIT_HR_HIGH or hr <= CRIT_HR_LOW)))


def reasons_for(f) -> list:
    """Which signals look abnormal, from a feature row (used to explain an alert)."""
    out = []
    if f[0] > 0.8: out.append("high_temp")
    if f[0] < -1.0: out.append("low_temp")
    if f[1] > 25: out.append("high_hr")
    if f[1] < -25: out.append("low_hr")
    if f[2] < -22: out.append("low_activity")
    if f[2] > 35: out.append("high_activity")
    return out


def persistent(flags, window=5, need=3):
    """True where at least `need` of the last `window` readings are flagged (filters out single noisy readings)."""
    a = np.asarray(flags, dtype=int)
    c = np.concatenate([[0], np.cumsum(a)])
    idx = np.arange(len(a))
    start = np.maximum(0, idx - window + 1)
    return (c[idx + 1] - c[start]) >= need


def simulate_animal(species, n, rng, start_hour=0.0, interval_min=10.0):
    """Normal readings for one animal: returns dict of arrays (hour, temp, hr, act)."""
    t_off, h_off, a_scale = rng.normal(0, 0.12), rng.normal(0, 0.04), rng.uniform(0.85, 1.15)
    hours = (start_hour + np.arange(n) * interval_min / 60.0) % 24
    act = np.clip([expected_activity(h) * a_scale + rng.normal(0, 8) for h in hours], 0, 100)
    temp = np.array([expected_temp(species, h) + t_off + rng.normal(0, 0.12) for h in hours])
    hr = np.array([expected_hr(species, h) * (1 + h_off) + 0.15 * (a - expected_activity(h)) + rng.normal(0, 4) for h, a in zip(hours, act)])
    return {"hour": hours, "temp": temp, "hr": np.clip(hr, 20, 220), "act": act}


KINDS = ["fever", "hypothermia", "tachycardia", "lethargy", "illness"]


def inject_episode(d, start, length, kind, rng):
    """Change readings start..start+length into an abnormal episode (in place)."""
    sl = slice(start, start + length)
    n = len(d["temp"][sl])
    ramp = np.minimum(1.0, (np.arange(n) + 1) / 3.0)  # builds up over ~3 readings
    if kind == "fever":
        d["temp"][sl] += rng.uniform(1.3, 2.6) * ramp
    elif kind == "hypothermia":
        d["temp"][sl] -= rng.uniform(1.8, 3.0) * ramp
    elif kind == "tachycardia":
        d["hr"][sl] *= 1 + rng.uniform(0.4, 0.8) * ramp
    elif kind == "lethargy":
        d["act"][sl] = d["act"][sl] * rng.uniform(0.1, 0.3) + 0.0
        d["hr"][sl] *= 1 - 0.08 * ramp
    else:  # illness: mild fever + faster heart + less movement
        d["temp"][sl] += rng.uniform(1.2, 2.2) * ramp
        d["hr"][sl] *= 1 + rng.uniform(0.25, 0.5) * ramp
        d["act"][sl] = d["act"][sl] * rng.uniform(0.25, 0.5)
    d["hr"][sl] = np.clip(d["hr"][sl], 20, 220)


def baselines(d, window=144, min_periods=12, species=None):
    """Personal baselines: rolling median of the PREVIOUS readings (same idea as the live system)."""
    import pandas as pd
    t = pd.Series(d["temp"]).shift(1).rolling(window, min_periods=min_periods).median()
    h = pd.Series(d["hr"]).shift(1).rolling(window, min_periods=min_periods).median()
    return t.to_numpy(), h.to_numpy()


class LiveGenerator:
    """Produces one reading at a time for a pretend collar (used by the simulator script and the online demo)."""

    def __init__(self, species, seed=0):
        self.species = species
        self.rng = np.random.default_rng(seed)
        self.t_off, self.h_off, self.a_scale = self.rng.normal(0, 0.1), self.rng.normal(0, 0.03), self.rng.uniform(0.9, 1.1)
        self.battery = 96.0
        self.sick_left = 0   # readings left in the current illness episode
        self.sick_step = 0

    def start_episode(self, length=14):
        self.sick_left, self.sick_step = length, 0

    def next(self, when):
        h = when.hour + when.minute / 60.0
        act = expected_activity(h) * self.a_scale + self.rng.normal(0, 6)
        temp = expected_temp(self.species, h) + self.t_off + self.rng.normal(0, 0.1)
        hr = expected_hr(self.species, h) * (1 + self.h_off) + 0.15 * (act - expected_activity(h)) + self.rng.normal(0, 3)
        if self.sick_left > 0:
            self.sick_step += 1
            self.sick_left -= 1
            ramp = min(1.0, self.sick_step / 3.0)
            temp += 2.0 * ramp
            hr *= 1 + 0.4 * ramp
            act *= 0.35
        self.battery = max(1.0, self.battery - 0.01)
        return {"recorded_at": when, "temperature_c": round(float(temp), 2), "heart_rate_bpm": round(float(np.clip(hr, 20, 220)), 1),
                "activity_index": round(float(np.clip(act, 0, 100)), 1), "battery_pct": round(self.battery, 1)}
