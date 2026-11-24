"""Create data/sample_health_data.csv for the CSV-import demo (recent evening readings + 2 deliberately bad rows)."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(3)
tags = [f"C-00{i}" for i in range(1, 7)] + [f"G-00{i}" for i in range(1, 5)] + ["S-001", "S-002"]
base = {"C": (38.6, 8.0, 300), "G": (39.2, 1.6, 28), "S": (39.2, 1.4, 32)}
out = Path(__file__).resolve().parents[2] / "data" / "sample_health_data.csv"
out.parent.mkdir(exist_ok=True)
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tag_no", "recorded_at", "temperature_c", "weight_kg", "feed_intake_kg", "milk_yield_l", "symptoms", "notes"])
    for d in range(5, 0, -1):
        day = date.today() - timedelta(days=d)
        for t in tags:
            tmp, feed, wt = base[t[0]]
            w.writerow([t, f"{day.isoformat()}T18:00:00", round(random.gauss(tmp, 0.2), 1), round(wt * random.uniform(0.95, 1.05), 1),
                        round(feed * random.uniform(0.9, 1.1), 2), "", "", ""])
    w.writerow(["X-999", f"{date.today().isoformat()}T09:00:00", 38.5, 300, 8, "", "", "bad row: unknown animal"])
    w.writerow(["C-001", f"{date.today().isoformat()}T09:00:00", 55.0, 300, 8, "", "", "bad row: impossible temperature"])
print("wrote", out)
