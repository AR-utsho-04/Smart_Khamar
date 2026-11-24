from collections import defaultdict
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import false
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import accessible_farm_ids, get_animal_checked, get_current_user, get_farm_checked
from ..models import (Alert, Animal, Consultation, HealthRecord, Prediction, Reminder, User, Farm, utcnow)
from ..services import reports
from ..services.lookups import disease_map

router = APIRouter(tags=["dashboard"])


def scoped_animals(db, user, farm_id=None):
    ids = accessible_farm_ids(db, user)
    q = db.query(Animal).filter(Animal.is_archived.is_(False))
    if ids is not None:
        q = q.filter(Animal.farm_id.in_(ids)) if ids else q.filter(false())
    if farm_id:
        get_farm_checked(db, user, farm_id)
        q = q.filter(Animal.farm_id == farm_id)
    return q


def build_summary(db, user, farm_id=None, date_from=None, date_to=None):
    end = date_to or date.today()
    start = date_from or end - timedelta(days=29)
    t0, t1 = datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.max.time())
    animals = scoped_animals(db, user, farm_id).all()
    aid = [a.id for a in animals]
    by_species, by_status = defaultdict(int), defaultdict(int)
    for a in animals:
        by_species[a.species] += 1
        by_status[a.status] += 1

    sev = {"high": 0, "medium": 0, "low": 0}
    if aid:
        aq = db.query(Alert).filter(Alert.animal_id.in_(aid), Alert.status == "open")
        if user.role == "vet":
            aq = aq.filter(Alert.severity == "high")
        for al in aq.all():
            sev[al.severity] += 1

    risk, cases, temps = {"low": 0, "medium": 0, "high": 0}, defaultdict(lambda: defaultdict(set)), defaultdict(list)
    if aid:
        seen = set()
        for p in db.query(Prediction).filter(Prediction.animal_id.in_(aid)).order_by(Prediction.created_at.desc(), Prediction.id.desc()).all():
            if p.animal_id not in seen:
                seen.add(p.animal_id)
                risk[p.risk_level] += 1
            if t0 <= p.created_at <= t1 and p.top_predictions and p.top_predictions[0]["disease_key"] != "healthy":
                cases[p.created_at.date().isoformat()][p.top_predictions[0]["disease_key"]].add(p.animal_id)
        for r in db.query(HealthRecord).filter(HealthRecord.animal_id.in_(aid), HealthRecord.recorded_at >= t0,
                                               HealthRecord.recorded_at <= t1, HealthRecord.temperature_c.isnot(None)).all():
            temps[r.recorded_at.date().isoformat()].append(r.temperature_c)
    disease_cases = [{"date": d, **{k: len(v) for k, v in sorted(cases[d].items())}} for d in sorted(cases)]
    temp_trend = [{"date": d, "avg_temp": round(sum(v) / len(v), 2)} for d, v in sorted(temps.items())]

    overdue_animals = set()
    upcoming = []
    if aid:
        for r in db.query(Reminder).filter(Reminder.animal_id.in_(aid), Reminder.status == "overdue", Reminder.type == "vaccination").all():
            overdue_animals.add(r.animal_id)
        tags = {a.id: a.tag_no for a in animals}
        for r in db.query(Reminder).filter(Reminder.animal_id.in_(aid), Reminder.status.in_(["pending", "overdue"])).order_by(Reminder.due_date).limit(10).all():
            upcoming.append({"id": r.id, "animal_id": r.animal_id, "animal_tag": tags.get(r.animal_id), "title": r.title,
                             "due_date": r.due_date.isoformat(), "status": r.status})
    cov = round((len(animals) - len(overdue_animals)) / len(animals) * 100, 1) if animals else 0.0
    return {"animals_total": len(animals), "animals_by_species": dict(by_species), "animals_by_status": dict(by_status),
            "open_alerts_by_severity": sev, "risk_distribution": risk, "disease_cases_over_time": disease_cases,
            "temperature_trend": temp_trend, "vaccination_coverage_pct": cov, "upcoming_reminders": upcoming,
            "range": {"from": start.isoformat(), "to": end.isoformat()}}


@router.get("/dashboard/summary")
def summary(farm_id: int | None = None, date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
            user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_summary(db, user, farm_id, date_from, date_to)


def _file(content: bytes, fmt: str, name: str):
    media = "application/pdf" if fmt == "pdf" else "text/csv; charset=utf-8"
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


@router.get("/reports/herd")
def herd_report(format: str = "pdf", farm_id: int | None = None, date_from: date | None = Query(None, alias="from"),
                date_to: date | None = Query(None, alias="to"), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = build_summary(db, user, farm_id, date_from, date_to)
    rows = [["Animals total", s["animals_total"]]]
    rows += [[f"Species: {k}", v] for k, v in s["animals_by_species"].items()]
    rows += [[f"Status: {k}", v] for k, v in s["animals_by_status"].items()]
    rows += [[f"Open alerts ({k})", v] for k, v in s["open_alerts_by_severity"].items()]
    rows += [[f"Risk level: {k}", v] for k, v in s["risk_distribution"].items()]
    rows.append(["Vaccination coverage %", s["vaccination_coverage_pct"]])
    if format == "csv":
        return _file(reports.to_csv(["metric", "value"], rows), "csv", "herd_report")
    cases = [["Date", "Disease cases"]] + [[c["date"], ", ".join(f"{k}: {v}" for k, v in c.items() if k != "date")] for c in s["disease_cases_over_time"]]
    blocks = [("p", f"Period: {s['range']['from']} to {s['range']['to']}"), ("h", "Herd summary"), ("table", [["Metric", "Value"]] + rows),
              ("h", "Suspected disease cases (AI)"), ("table", cases if len(cases) > 1 else [["Date", "Disease cases"], ["-", "none"]]),
              ("h", "Upcoming reminders"), ("table", [["Animal", "Reminder", "Due", "Status"]] + [[r["animal_tag"], r["title"], r["due_date"], r["status"]] for r in s["upcoming_reminders"]])]
    return _file(reports.to_pdf("Herd Health Report", blocks), "pdf", "herd_report")


@router.get("/reports/animal/{animal_id}")
def animal_card(animal_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    a = get_animal_checked(db, user, animal_id)
    dm = disease_map(db)
    recs = db.query(HealthRecord).filter(HealthRecord.animal_id == a.id).order_by(HealthRecord.recorded_at.desc()).limit(10).all()
    pred = db.query(Prediction).filter(Prediction.animal_id == a.id).order_by(Prediction.created_at.desc(), Prediction.id.desc()).first()
    done = db.query(Reminder).filter(Reminder.animal_id == a.id, Reminder.status == "done").order_by(Reminder.completed_at.desc()).all()
    cons = db.query(Consultation).filter(Consultation.animal_id == a.id).order_by(Consultation.created_at.desc()).all()
    blocks = [("h", "Animal details"),
              ("table", [["Tag", "Name", "Species", "Sex", "Status", "Weight (kg)"], [a.tag_no, a.name, a.species, a.sex, a.status, a.weight_kg]]),
              ("h", "Latest AI risk estimate")]
    if pred:
        top = ", ".join(f"{dm.get(t['disease_key'], (t['disease_key'],))[0]} {round(t['probability'] * 100)}%" for t in pred.top_predictions)
        blocks.append(("p", f"Risk level: {pred.risk_level}. Top results: {top}. (Not a diagnosis.)"))
    else:
        blocks.append(("p", "No prediction yet."))
    blocks += [("h", "Last 10 health records"),
               ("table", [["Date", "Temp C", "Weight", "Feed", "Symptoms"]] + [[r.recorded_at.strftime("%Y-%m-%d %H:%M"), r.temperature_c, r.weight_kg, r.feed_intake_kg, ", ".join(s.name_en for s in r.symptoms)] for r in recs]),
               ("h", "Vaccination and care history"),
               ("table", [["Date", "Item"]] + [[r.completed_at.strftime("%Y-%m-%d") if r.completed_at else "-", r.title] for r in done] if done else [["Date", "Item"], ["-", "none"]]),
               ("h", "Consultations"),
               ("table", [["Date", "Diagnosis", "Treatment", "Medicine"]] + [[c.created_at.strftime("%Y-%m-%d"), c.diagnosis, c.treatment, c.medicine] for c in cons] if cons else [["Date", "Diagnosis", "Treatment", "Medicine"], ["-", "none", "", ""]])]
    return _file(reports.to_pdf(f"Animal Health Card: {a.tag_no}", blocks), "pdf", f"animal_{a.tag_no}")


@router.get("/reports/vaccinations-due")
def vaccinations_due(format: str = "pdf", farm_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    animals = {a.id: a for a in scoped_animals(db, user, farm_id).all()}
    rows = []
    if animals:
        for r in db.query(Reminder).filter(Reminder.animal_id.in_(list(animals)), Reminder.status.in_(["pending", "overdue"]),
                                           Reminder.type.in_(["vaccination", "deworming", "checkup"])).order_by(Reminder.due_date).all():
            a = animals[r.animal_id]
            rows.append([a.tag_no, a.species, r.title, r.due_date.isoformat(), r.status])
    head = ["animal_tag", "species", "reminder", "due_date", "status"]
    if format == "csv":
        return _file(reports.to_csv(head, rows), "csv", "vaccinations_due")
    return _file(reports.to_pdf("Vaccinations and Care Due", [("table", [head] + rows if rows else [head, ["-", "", "none", "", ""]])]), "pdf", "vaccinations_due")


@router.get("/reports/treatments")
def treatments(farm_id: int | None = None, date_from: date | None = Query(None, alias="from"), date_to: date | None = Query(None, alias="to"),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    animals = {a.id: a for a in scoped_animals(db, user, farm_id).all()}
    rows = []
    if animals:
        q = db.query(Consultation).filter(Consultation.animal_id.in_(list(animals)))
        if date_from:
            q = q.filter(Consultation.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to:
            q = q.filter(Consultation.created_at <= datetime.combine(date_to, datetime.max.time()))
        vets = {u.id: u.name for u in db.query(User).filter(User.role == "vet").all()}
        for c in q.order_by(Consultation.created_at.desc()).all():
            rows.append([c.created_at.strftime("%Y-%m-%d"), animals[c.animal_id].tag_no, c.diagnosis, c.treatment, c.medicine, c.dosage, vets.get(c.vet_id)])
    return _file(reports.to_csv(["date", "animal_tag", "diagnosis", "treatment", "medicine", "dosage", "vet"], rows), "csv", "treatments")
