"""Export vet-confirmed cases for future retraining.  Run:  python -m app.ml.export_feedback
Writes data/feedback_labeled.csv (automatic retraining is out of scope)."""
import csv
from pathlib import Path
from ..database import SessionLocal
from ..models import Animal, Disease, HealthRecord, Prediction, PredictionFeedback


def main():
    db = SessionLocal()
    out = Path(__file__).resolve().parents[3] / "data" / "feedback_labeled.csv"
    out.parent.mkdir(exist_ok=True)
    n = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species", "sex", "age_months", "temperature_c", "weight_kg", "feed_intake_kg", "symptoms", "label", "source"])
        for fb in db.query(PredictionFeedback).all():
            p = db.get(Prediction, fb.prediction_id)
            rec, animal = db.get(HealthRecord, p.record_id), db.get(Animal, p.animal_id)
            if fb.confirmed:
                label = p.top_predictions[0]["disease_key"]
            elif fb.actual_disease_id:
                label = db.get(Disease, fb.actual_disease_id).key
            else:
                continue  # rejected without a known true disease: cannot be used as a label
            w.writerow([animal.species, animal.sex, animal.age_months, rec.temperature_c, rec.weight_kg, rec.feed_intake_kg,
                        ";".join(s.key for s in rec.symptoms), label, "vet_feedback"])
            n += 1
    print(f"Exported {n} labeled cases to {out}")


if __name__ == "__main__":
    main()
