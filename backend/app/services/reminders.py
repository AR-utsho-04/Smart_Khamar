from datetime import date, timedelta
from ..models import Reminder, VaccineSchedule, utcnow
from .common import animal_age_months


def generate_for_animal(db, animal):
    """Create reminders from active schedule templates (skips ones that already exist)."""
    created = []
    for s in db.query(VaccineSchedule).filter(VaccineSchedule.is_active.is_(True)).all():
        if s.species not in ("all", animal.species):
            continue
        exists = db.query(Reminder).filter(Reminder.animal_id == animal.id, Reminder.schedule_id == s.id,
                                           Reminder.status.in_(["pending", "overdue"])).first()
        if exists:
            continue
        due = date.today() + timedelta(days=14)
        age = animal_age_months(animal)
        if s.first_dose_age_days and age is not None and age * 30 < s.first_dose_age_days:
            due = date.today() + timedelta(days=s.first_dose_age_days - age * 30)
        r = Reminder(animal_id=animal.id, schedule_id=s.id, type=s.kind, title=s.name, due_date=due)
        db.add(r)
        created.append(r)
    db.flush()
    return created


def mark_done(db, r):
    """Mark done; if it came from a schedule, create the next reminder."""
    r.status, r.completed_at = "done", utcnow()
    if r.schedule_id:
        s = db.get(VaccineSchedule, r.schedule_id)
        if s:
            db.add(Reminder(animal_id=r.animal_id, schedule_id=s.id, type=r.type, title=r.title,
                            due_date=date.today() + timedelta(days=s.interval_days)))
