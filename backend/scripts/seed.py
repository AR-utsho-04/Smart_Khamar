"""Create demo data.  Run from the backend folder:  python scripts/seed.py
Safe to run twice. Demo password for all users: Password123!   (development only)"""
import os
import random
import sys
from datetime import date, datetime, time, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Animal, Consultation, Device, Farm, FarmVet, Reminder, User, utcnow  # noqa: E402
import numpy as np  # noqa: E402
from app.ml import telemetry as tm  # noqa: E402
from app.services import iot  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.lookups import ensure_lookups  # noqa: E402
from app.services.pipeline import save_record  # noqa: E402
from app.services.reminders import generate_for_animal  # noqa: E402

PASSWORD = "Password123!"
BASE = {"cattle": dict(temp=38.6, feed=8.0, weight=300.0), "goat": dict(temp=39.2, feed=1.6, weight=28.0),
        "sheep": dict(temp=39.2, feed=1.4, weight=32.0)}
# tag -> (days of illness, [(min day-index-from-end, symptoms to add)], temp at peak)
ILLNESS = {
    "C-002": dict(days=5, peak=40.6, feed=0.5, steps=[(3, ["mouth_lesions", "loss_of_appetite"]), (2, ["lameness", "fever"]), (1, ["reduced_milk_yield"])]),
    "G-001": dict(days=4, peak=41.0, feed=0.45, steps=[(3, ["nasal_discharge", "loss_of_appetite"]), (2, ["eye_discharge", "fever"]), (1, ["diarrhea", "cough"])]),
    "C-004": dict(days=3, peak=40.0, feed=0.75, steps=[(2, ["swollen_udder"]), (1, ["reduced_milk_yield", "fever"])]),
}
ANIMALS = ([(f"C-00{i}", "cattle", "female" if i != 5 else "male", 24 + i * 6, "Local Red Chittagong" if i % 2 else "Holstein Cross") for i in range(1, 7)]
           + [(f"G-00{i}", "goat", "female" if i % 2 else "male", 10 + i * 3, "Black Bengal") for i in range(1, 5)]
           + [(f"S-00{i}", "sheep", "female", 14 + i * 4, "Garole") for i in range(1, 3)])


def get_or_create_user(db, email, name, role, **kw):
    u = db.query(User).filter(User.email == email).first()
    if not u:
        u = User(email=email, name=name, role=role, password_hash=hash_password(PASSWORD), is_approved=True, **kw)
        db.add(u)
        db.flush()
    return u


def seed_devices(db, farm, animals):
    """5 demo collars with 24 hours of readings. C-002 and G-001 have a fever episode in the last ~2 hours."""
    by_tag = {a.tag_no: a for a in animals}
    rng = np.random.default_rng(24)
    plan = {"C-001": None, "C-003": None, "G-002": None, "C-002": "illness", "G-001": "fever"}
    now, n = utcnow(), 144  # 24 hours, one reading every 10 minutes
    for tag, episode in plan.items():
        a = by_tag[tag]
        key = "demo-device-key-" + tag  # demo only: public key so the simulator works out of the box
        d = Device(farm_id=farm.id, animal_id=a.id, name=f"Collar {tag}", device_uid=iot.new_uid(db), key_hash=iot.hash_key(key))
        db.add(d)
        db.flush()
        start = now - timedelta(minutes=10 * (n - 1))
        series = tm.simulate_animal(a.species, n, rng, start_hour=start.hour + start.minute / 60.0, interval_min=10)
        if episode:
            tm.inject_episode(series, n - 14, 14, episode, rng)
        readings = [{"recorded_at": start + timedelta(minutes=10 * i), "temperature_c": round(float(series["temp"][i]), 2),
                     "heart_rate_bpm": round(float(series["hr"][i]), 1), "activity_index": round(float(series["act"][i]), 1),
                     "battery_pct": round(85 - i * 0.02, 1)} for i in range(n)]
        for i in range(0, n, 48):  # in chunks, like a device uploading batches
            iot.ingest(db, d, readings[i:i + 48], notify=False)
            db.commit()


def main():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    ensure_lookups(db)
    random.seed(7)
    admin = get_or_create_user(db, "admin@demo.com", "Demo Admin", "admin")
    farmer = get_or_create_user(db, "farmer@demo.com", "Rahim Uddin", "farmer", phone="01700000000")
    vet = get_or_create_user(db, "vet@demo.com", "Dr. Karim Hossain", "vet", license_no="BVC-12345")
    farm = db.query(Farm).filter(Farm.owner_id == farmer.id).first()
    if not farm:
        farm = Farm(owner_id=farmer.id, name="Demo Farm", district="Dhaka", address="Savar", species_kept="cattle,goat,sheep")
        db.add(farm); db.flush()
    if not db.query(FarmVet).filter(FarmVet.farm_id == farm.id, FarmVet.vet_id == vet.id).first():
        db.add(FarmVet(farm_id=farm.id, vet_id=vet.id, status="approved", granted_at=utcnow()))
    db.commit()

    if db.query(Animal).filter(Animal.farm_id == farm.id).count() == 0:
        animals = []
        for tag, sp, sex, age, breed in ANIMALS:
            a = Animal(farm_id=farm.id, tag_no=tag, species=sp, sex=sex, age_months=age, breed=breed, name=None, weight_kg=BASE[sp]["weight"])
            db.add(a); animals.append(a)
        db.commit()
        today = date.today()
        for a in animals:
            b, ill = BASE[a.species], ILLNESS.get(a.tag_no)
            w = b["weight"] * random.uniform(0.9, 1.1)
            for day in range(29, -1, -1):
                when = datetime.combine(today - timedelta(days=day), time(8, 0))
                temp = random.gauss(b["temp"], 0.2)
                feed = b["feed"] * random.uniform(0.92, 1.08)
                w += random.uniform(-0.1, 0.25)
                syms = []
                if ill and day < ill["days"]:
                    k = ill["days"] - day  # 1 = first sick day
                    temp = b["temp"] + (ill["peak"] - b["temp"]) * k / ill["days"] + random.uniform(-0.1, 0.1)
                    feed *= 1 - (1 - ill["feed"]) * k / ill["days"]
                    w -= 0.4 * k
                    for m, add in ill["steps"]:
                        if day <= m:
                            syms += add
                data = {"recorded_at": when, "temperature_c": round(temp, 1), "weight_kg": round(w, 1), "feed_intake_kg": round(feed, 2),
                        "milk_yield_l": round(random.uniform(8, 12), 1) if a.species == "cattle" and a.sex == "female" and not syms else None,
                        "symptoms": list(dict.fromkeys(syms)), "notes": None}
                save_record(db, a, farmer, data, notify=False)
            db.commit()
        for a in animals:
            generate_for_animal(db, a)
        db.commit()
        rows = {r.animal_id: r for r in db.query(Reminder).all()}
        by_tag = {a.tag_no: a for a in animals}
        for tag, title, delta in (("C-001", "FMD vaccination", 7), ("C-003", "Deworming", 1), ("G-002", "General checkup", -3)):
            r = db.query(Reminder).filter(Reminder.animal_id == by_tag[tag].id, Reminder.title == title).first()
            if r:
                r.due_date = today + timedelta(days=delta)
                r.status = "overdue" if delta < 0 else "pending"
        c = by_tag["C-002"]
        db.add(Consultation(animal_id=c.id, vet_id=vet.id, diagnosis="Suspected foot-and-mouth disease", treatment="Isolate animal, supportive care, wound cleaning",
                            medicine="Anti-inflammatory (as prescribed)", dosage="As per vet", follow_up_date=today + timedelta(days=3)))
        db.add(Reminder(animal_id=c.id, type="follow_up", title="Follow-up: Suspected foot-and-mouth disease", due_date=today + timedelta(days=3)))
        db.commit()
    if db.query(Device).count() == 0:
        seed_devices(db, farm, db.query(Animal).filter(Animal.farm_id == farm.id).all())
    print("Seed complete.\n  admin@demo.com / farmer@demo.com / vet@demo.com   password: " + PASSWORD)
    db.close()


if __name__ == "__main__":
    main()
