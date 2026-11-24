import io
import json
from datetime import datetime, timedelta, timezone

API = "/api/v1"


def iso_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- auth and roles ----------
def test_register_login_and_wrong_password(client, make_user):
    u = make_user("farmer")
    assert client.get(f"{API}/auth/me", headers=u["h"]).json()["role"] == "farmer"
    r = client.post(f"{API}/auth/login", json={"email": u["email"], "password": "wrong-password"})
    assert r.status_code == 401
    assert client.post(f"{API}/auth/register", json={"name": "x", "email": u["email"], "password": "Password123!", "role": "farmer"}).status_code == 409


def test_unapproved_vet_blocked_then_approved(client, make_user):
    vet = make_user("vet", approve=False)
    assert client.get(f"{API}/auth/me", headers=vet["h"]).status_code == 200
    r = client.get(f"{API}/consultations/queue", headers=vet["h"])
    assert r.status_code == 403 and r.json()["detail"] == "vet_not_approved"
    admin = make_user("admin")
    assert client.patch(f"{API}/admin/vets/{vet['id']}/approve", headers=admin["h"]).status_code == 200
    assert client.get(f"{API}/consultations/queue", headers=vet["h"]).status_code == 200


def test_role_checks(client, make_user):
    f = make_user("farmer")
    assert client.get(f"{API}/admin/users", headers=f["h"]).status_code == 403
    assert client.get(f"{API}/animals").status_code == 401


# ---------- access control ----------
def test_farmer_cannot_read_other_farm(client, farm_setup, make_user):
    other = make_user("farmer")
    assert client.get(f"{API}/animals/{farm_setup['cow']['id']}", headers=other["h"]).status_code == 404
    assert client.get(f"{API}/animals/{farm_setup['cow']['id']}", headers=farm_setup["farmer"]["h"]).status_code == 200
    items = client.get(f"{API}/animals", headers=other["h"]).json()["items"]
    assert all(a["id"] != farm_setup["cow"]["id"] for a in items)


def test_vet_access_requires_two_step_approval(client, farm_setup, make_user):
    vet = make_user("vet")
    cow = farm_setup["cow"]
    assert client.get(f"{API}/animals/{cow['id']}", headers=vet["h"]).status_code == 404
    inv = client.post(f"{API}/farms/{farm_setup['farm']['id']}/vets", json={"vet_email": vet["email"]}, headers=farm_setup["farmer"]["h"])
    assert inv.status_code == 201
    assert client.get(f"{API}/animals/{cow['id']}", headers=vet["h"]).status_code == 404  # still pending
    invs = client.get(f"{API}/vet/invitations", headers=vet["h"]).json()
    assert client.patch(f"{API}/vet/invitations/{invs[0]['id']}", json={"status": "approved"}, headers=vet["h"]).status_code == 200
    assert client.get(f"{API}/animals/{cow['id']}", headers=vet["h"]).status_code == 200
    # vet cannot edit animals
    assert client.put(f"{API}/animals/{cow['id']}", json={"name": "x"}, headers=vet["h"]).status_code == 403
    client.patch(f"{API}/farms/{farm_setup['farm']['id']}/vets/{vet['id']}", json={"status": "revoked"}, headers=farm_setup["farmer"]["h"])
    assert client.get(f"{API}/animals/{cow['id']}", headers=vet["h"]).status_code == 404


def test_animal_crud_and_duplicate_tag(client, farm_setup):
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    dup = client.post(f"{API}/animals", json={"farm_id": farm_setup["farm"]["id"], "tag_no": cow["tag_no"], "species": "cattle", "sex": "male"}, headers=h)
    assert dup.status_code == 409
    assert client.put(f"{API}/animals/{cow['id']}", json={"name": "Lali"}, headers=h).json()["name"] == "Lali"
    assert client.delete(f"{API}/animals/{cow['id']}", headers=h).status_code == 200
    ids = [a["id"] for a in client.get(f"{API}/animals", headers=h).json()["items"]]
    assert cow["id"] not in ids


# ---------- records and validation ----------
def test_record_validation(client, farm_setup):
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    url = f"{API}/animals/{cow['id']}/records"
    assert client.post(url, json={"temperature_c": 55}, headers=h).status_code == 422
    assert client.post(url, json={}, headers=h).status_code == 422
    assert client.post(url, json={"symptoms": ["not_a_symptom"]}, headers=h).status_code == 422
    assert client.post(url, json={"temperature_c": 38.5}, headers=h).status_code == 201


# ---------- rules and alerts ----------
def test_fever_alert_and_dedup(client, farm_setup):
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    url = f"{API}/animals/{cow['id']}/records"
    r1 = client.post(url, json={"temperature_c": 41.0}, headers=h).json()
    assert any(a["type"] == "fever" and a["severity"] == "high" for a in r1["alerts"])  # 41.0 > 39.5 + 1.0
    r2 = client.post(url, json={"temperature_c": 41.2}, headers=h).json()
    assert not any(a["type"] == "fever" for a in r2["alerts"])  # de-duplicated within 24h
    alerts = client.get(f"{API}/alerts?animal_id={cow['id']}", headers=h).json()["items"]
    assert sum(a["type"] == "fever" for a in alerts) == 1


def test_weight_loss_and_appetite_drop(client, farm_setup):
    h, goat = farm_setup["farmer"]["h"], farm_setup["goat"]
    url = f"{API}/animals/{goat['id']}/records"
    for d in (8, 7, 6):
        assert client.post(url, json={"recorded_at": iso_ago(d), "weight_kg": 30.0, "feed_intake_kg": 1.6}, headers=h).status_code == 201
    r = client.post(url, json={"weight_kg": 27.0, "feed_intake_kg": 0.8}, headers=h).json()
    types = {a["type"] for a in r["alerts"]}
    assert "weight_loss" in types and "appetite_drop" in types
    assert r["derived"]["weight_change_pct_7d"] < -5


def test_risk_and_safety_net():
    from app.database import SessionLocal
    from app.services.pipeline import risk_from
    db = SessionLocal()
    assert risk_from(db, "cattle", 0.05, 38.6, []) == ("low", False)
    assert risk_from(db, "cattle", 0.45, 38.6, []) == ("medium", False)
    assert risk_from(db, "cattle", 0.70, 38.6, []) == ("high", False)
    assert risk_from(db, "cattle", 0.05, 41.0, ["mouth_lesions", "lameness"]) == ("high", True)  # safety net overrides the model
    assert risk_from(db, "cattle", 0.05, 41.0, ["mouth_lesions"]) == ("low", False)
    db.close()


# ---------- AI ----------
def test_prediction_high_risk_and_species_filter(client, farm_setup):
    h = farm_setup["farmer"]["h"]
    r = client.post(f"{API}/animals/{farm_setup['cow']['id']}/records",
                    json={"temperature_c": 40.6, "symptoms": ["mouth_lesions", "lameness", "loss_of_appetite", "fever"], "feed_intake_kg": 3}, headers=h).json()
    p = r["prediction"]
    assert p["risk_level"] == "high" and p["top_predictions"][0]["disease_key"] == "fmd"
    assert len(p["top_factors"]) >= 1
    # goat with skin nodules: cattle-only disease (lsd) must never appear
    g = client.post(f"{API}/animals/{farm_setup['goat']['id']}/records",
                    json={"temperature_c": 40.5, "symptoms": ["skin_nodules", "fever"]}, headers=h).json()["prediction"]
    assert "lsd" not in [t["disease_key"] for t in g["top_predictions"]]


def test_vet_feedback_and_consultation_flow(client, farm_setup, make_user):
    f, farm, cow = farm_setup["farmer"], farm_setup["farm"], farm_setup["cow"]
    vet = make_user("vet")
    client.post(f"{API}/farms/{farm['id']}/vets", json={"vet_email": vet["email"]}, headers=f["h"])
    inv = client.get(f"{API}/vet/invitations", headers=vet["h"]).json()[0]
    client.patch(f"{API}/vet/invitations/{inv['id']}", json={"status": "approved"}, headers=vet["h"])
    pred = client.post(f"{API}/animals/{cow['id']}/records", json={"temperature_c": 40.6, "symptoms": ["mouth_lesions", "lameness"]}, headers=f["h"]).json()["prediction"]
    assert client.post(f"{API}/predictions/{pred['id']}/feedback", json={"confirmed": True}, headers=f["h"]).status_code == 403
    assert client.post(f"{API}/predictions/{pred['id']}/feedback", json={"confirmed": False, "actual_disease_key": "bef"}, headers=vet["h"]).status_code == 200
    follow = (datetime.now() + timedelta(days=3)).date().isoformat()
    c = client.post(f"{API}/animals/{cow['id']}/consultations", json={"diagnosis": "Suspected FMD", "treatment": "Isolate", "follow_up_date": follow, "prediction_id": pred["id"]}, headers=vet["h"])
    assert c.status_code == 201
    assert client.post(f"{API}/animals/{cow['id']}/consultations", json={"diagnosis": "x"}, headers=f["h"]).status_code == 403
    rem = client.get(f"{API}/reminders?animal_id={cow['id']}", headers=f["h"]).json()["items"]
    assert any(r["type"] == "follow_up" for r in rem)
    cid = c.json()["id"]
    assert client.post(f"{API}/consultations/{cid}/comments", json={"body": "Thanks doctor"}, headers=f["h"]).status_code == 201
    assert len(client.get(f"{API}/consultations/{cid}", headers=vet["h"]).json()["comments"]) == 1
    queue = client.get(f"{API}/consultations/queue", headers=vet["h"]).json()
    assert any(a["id"] == cow["id"] for a in queue)


# ---------- CSV import ----------
def test_csv_import(client, farm_setup):
    h, farm, cow = farm_setup["farmer"]["h"], farm_setup["farm"], farm_setup["cow"]
    csv_text = ("tag_no,recorded_at,temperature_c,weight_kg,feed_intake_kg,milk_yield_l,symptoms,notes\n"
                f"{cow['tag_no']},2026-11-01,38.6,300,8,,,ok\n"
                f"NOPE-1,2026-11-01,38.6,300,8,,,\n"
                f"{cow['tag_no']},2026-11-02,abc,300,8,,,\n"
                f"{cow['tag_no']},2026-11-03,38.7,300,8,,fever;cough,\n")
    r = client.post(f"{API}/records/import", data={"farm_id": farm["id"]}, files={"file": ("x.csv", io.BytesIO(csv_text.encode()), "text/csv")}, headers=h)
    rep = r.json()
    assert r.status_code == 200 and rep["total_rows"] == 4 and rep["imported"] == 2 and rep["failed"] == 2
    assert {e["row"] for e in rep["errors"]} == {3, 4}


# ---------- reminders and scheduler ----------
def test_reminders_generate_done_and_overdue_job(client, farm_setup):
    from app.database import SessionLocal
    from app.models import Reminder
    from app.scheduler.jobs import run_job
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    g = client.post(f"{API}/animals/{cow['id']}/reminders/generate", headers=h).json()
    assert g["created"] >= 3
    assert client.post(f"{API}/animals/{cow['id']}/reminders/generate", headers=h).json()["created"] == 0  # no duplicates
    first = g["items"][0]
    done = client.patch(f"{API}/reminders/{first['id']}", json={"status": "done"}, headers=h)
    assert done.json()["status"] == "done"
    after = client.get(f"{API}/reminders?animal_id={cow['id']}&status=pending", headers=h).json()["items"]
    assert len([r for r in after if r["title"] == first["title"]]) == 1  # the next one was created
    db = SessionLocal()
    r = db.get(Reminder, g["items"][1]["id"])
    r.due_date = (datetime.now() - timedelta(days=3)).date()
    db.commit(); db.close()
    run_job("reminders_daily")
    alerts = client.get(f"{API}/alerts?animal_id={cow['id']}", headers=h).json()["items"]
    assert any(a["type"] == "vaccination_overdue" for a in alerts)


def test_alert_acknowledge_snooze(client, farm_setup):
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    client.post(f"{API}/animals/{cow['id']}/records", json={"temperature_c": 41.0}, headers=h)
    al = client.get(f"{API}/alerts?status=open", headers=h).json()["items"][0]
    assert client.patch(f"{API}/alerts/{al['id']}/snooze", json={"hours": 2}, headers=h).json()["status"] == "snoozed"
    assert client.patch(f"{API}/alerts/{al['id']}/acknowledge", headers=h).json()["status"] == "acknowledged"
    assert client.get(f"{API}/alerts/summary", headers=h).status_code == 200


# ---------- dashboard, reports, admin ----------
def test_dashboard_and_reports(client, farm_setup):
    h, cow = farm_setup["farmer"]["h"], farm_setup["cow"]
    client.post(f"{API}/animals/{cow['id']}/records", json={"temperature_c": 40.8, "symptoms": ["mouth_lesions", "lameness"]}, headers=h)
    s = client.get(f"{API}/dashboard/summary", headers=h).json()
    for k in ("animals_total", "animals_by_species", "animals_by_status", "open_alerts_by_severity", "risk_distribution",
              "disease_cases_over_time", "temperature_trend", "vaccination_coverage_pct", "upcoming_reminders"):
        assert k in s
    assert s["animals_total"] >= 2
    pdf = client.get(f"{API}/reports/herd?format=pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{API}/reports/herd?format=csv", headers=h).status_code == 200
    assert client.get(f"{API}/reports/animal/{cow['id']}", headers=h).content.startswith(b"%PDF")
    assert client.get(f"{API}/reports/vaccinations-due?format=csv", headers=h).status_code == 200


def test_admin_thresholds_change_alert_behaviour(client, farm_setup, make_user):
    admin, h, cow = make_user("admin"), farm_setup["farmer"]["h"], farm_setup["cow"]
    client.put(f"{API}/admin/thresholds", json=[{"species": "cattle", "parameter": "temperature_c", "min_value": 38.0, "max_value": 38.9}], headers=admin["h"])
    r = client.post(f"{API}/animals/{cow['id']}/records", json={"temperature_c": 39.2}, headers=h).json()
    assert any(a["type"] == "fever" for a in r["alerts"])  # 39.2 is now above the new maximum
    client.put(f"{API}/admin/thresholds", json=[{"species": "cattle", "parameter": "temperature_c", "min_value": 38.0, "max_value": 39.5}], headers=admin["h"])
    assert client.get(f"{API}/admin/audit-log", headers=admin["h"]).status_code == 200
    assert client.get(f"{API}/admin/model", headers=admin["h"]).json()["available"] is True


def test_sensor_endpoint(client, farm_setup):
    cow, farm = farm_setup["cow"], farm_setup["farm"]
    body = {"farm_id": farm["id"], "tag_no": cow["tag_no"], "temperature_c": 38.7}
    assert client.post(f"{API}/readings", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.post(f"{API}/readings", json=body, headers={"X-API-Key": "dev-sensor-key"}).status_code == 201


# ---------- ML ----------
def test_ml_pipeline_artifacts_and_score(client):
    from app.config import settings
    m = json.loads((settings.MODEL_DIR / "metrics.json").read_text())
    assert (settings.MODEL_DIR / "model.joblib").exists()
    assert m["final"]["macro_f1"] > 0.7  # checks the pipeline on synthetic data, not clinical accuracy


def test_male_never_gets_mastitis(client, farm_setup):
    h, farm = farm_setup["farmer"]["h"], farm_setup["farm"]
    bull = client.post(f"{API}/animals", json={"farm_id": farm["id"], "tag_no": "BULL-1", "species": "cattle", "sex": "male", "age_months": 40}, headers=h).json()
    p = client.post(f"{API}/animals/{bull['id']}/records", json={"temperature_c": 39.9, "symptoms": ["swollen_udder", "reduced_milk_yield"]}, headers=h).json()["prediction"]
    assert "mastitis" not in [t["disease_key"] for t in p["top_predictions"]]


def test_healthy_animal_stays_low_risk(client, farm_setup):
    h = farm_setup["farmer"]["h"]
    for animal, t, w in ((farm_setup["cow"], 38.6, 300), (farm_setup["goat"], 39.2, 30)):
        p = client.post(f"{API}/animals/{animal['id']}/records", json={"temperature_c": t, "feed_intake_kg": 5, "weight_kg": w}, headers=h).json()["prediction"]
        assert p["risk_level"] == "low", p
