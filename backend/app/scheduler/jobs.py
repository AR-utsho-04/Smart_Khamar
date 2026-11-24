"""Background jobs (APScheduler). Each job opens its own DB session and is safe to run repeatedly."""
import logging
from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from ..database import SessionLocal
from ..models import Alert, Animal, FarmVet, HealthRecord, Reminder, User, utcnow
from ..services import iot
from ..services.pipeline import create_alert, notify_alert, thr

log = logging.getLogger("jobs")


def reminders_daily(db):
    today, n = date.today(), 0
    for r in db.query(Reminder).filter(Reminder.status == "pending", Reminder.due_date < today).all():
        r.status = "overdue"
    for r in db.query(Reminder).filter(Reminder.status.in_(["pending", "overdue"])).all():
        a = db.get(Animal, r.animal_id)
        if not a or a.is_archived or a.status in ("sold", "deceased"):
            continue
        days = (r.due_date - today).days
        kind = "follow_up_due" if r.type == "follow_up" else None
        params = {"title": r.title, "date": r.due_date.isoformat()}
        if r.status == "overdue" and not r.notified_overdue:
            r.notified_overdue = True
            create_alert(db, a, kind or "vaccination_overdue", "medium", params, dedupe=False); n += 1
        elif 0 <= days <= 1 and not r.notified_1d:
            r.notified_1d = r.notified_7d = True
            create_alert(db, a, kind or "vaccination_due", "low", params, dedupe=False); n += 1
        elif 1 < days <= 7 and not r.notified_7d:
            r.notified_7d = True
            create_alert(db, a, kind or "vaccination_due", "low", params, dedupe=False); n += 1
    db.commit()
    return f"reminders processed, {n} notifications"


def missed_entry_daily(db):
    n = 0
    for a in db.query(Animal).filter(Animal.status.in_(["under_observation", "sick"]), Animal.is_archived.is_(False)).all():
        days = int(thr(db, a.species, "missed_entry_days") or 2)
        last = db.query(HealthRecord).filter(HealthRecord.animal_id == a.id).order_by(HealthRecord.recorded_at.desc()).first()
        if not last or last.recorded_at < utcnow() - timedelta(days=days):
            if create_alert(db, a, "missed_entry", "low", {"days": days}):
                n += 1
    db.commit()
    return f"{n} missed-entry alerts"


def escalation_check(db):
    n = 0
    for al in db.query(Alert).filter(Alert.severity == "high", Alert.status == "open", Alert.escalated.is_(False)).all():
        a = db.get(Animal, al.animal_id) if al.animal_id else None
        if not a:
            continue
        hours = int(thr(db, a.species, "escalation_hours") or 6)
        if al.created_at < utcnow() - timedelta(hours=hours):
            al.escalated = True
            create_alert(db, a, "unacknowledged_escalation", "high", {"hours": hours}, dedupe=False)
            n += 1
    db.commit()
    return f"{n} escalations"


def snooze_reactivate(db):
    rows = db.query(Alert).filter(Alert.status == "snoozed", Alert.snoozed_until <= utcnow()).all()
    for al in rows:
        al.status, al.snoozed_until = "open", None
    db.commit()
    return f"{len(rows)} alerts reopened"


JOBS = {"iot_offline_check": iot.offline_check, "iot_cleanup_daily": iot.cleanup,
        "reminders_daily": reminders_daily, "missed_entry_daily": missed_entry_daily,
        "escalation_check": escalation_check, "snooze_reactivate": snooze_reactivate}


def run_job(name):
    if name not in JOBS:
        raise KeyError(name)
    db = SessionLocal()
    try:
        result = JOBS[name](db)
        log.info("job %s: %s", name, result)
        return result
    except Exception:
        db.rollback()
        log.exception("job %s failed", name)
        raise
    finally:
        db.close()


def start_scheduler():
    sch = BackgroundScheduler()
    sch.add_job(run_job, "cron", hour=6, minute=0, args=["reminders_daily"], id="reminders_daily")
    sch.add_job(run_job, "cron", hour=7, minute=0, args=["missed_entry_daily"], id="missed_entry_daily")
    sch.add_job(run_job, "interval", minutes=30, args=["escalation_check"], id="escalation_check")
    sch.add_job(run_job, "interval", minutes=10, args=["snooze_reactivate"], id="snooze_reactivate")
    sch.add_job(run_job, "interval", minutes=5, args=["iot_offline_check"], id="iot_offline_check")
    sch.add_job(run_job, "cron", hour=3, minute=0, args=["iot_cleanup_daily"], id="iot_cleanup_daily")
    sch.start()
    return sch
