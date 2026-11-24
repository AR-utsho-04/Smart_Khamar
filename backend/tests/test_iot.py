import json
from datetime import datetime, timedelta, timezone

from app.ml import telemetry as tm

API = "/api/v1"


def ts(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def reading(minutes_ago, species="cattle", temp_add=0.0, hr_mul=1.0, act_mul=1.0):
    """A reading that follows normal behaviour, optionally made abnormal."""
    when = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    h = when.hour + when.minute / 60.0
    return {"recorded_at": ts(minutes_ago), "temperature_c": round(tm.expected_temp(species, h) + temp_add, 2),
            "heart_rate_bpm": round(tm.expected_hr(species, h) * hr_mul, 1), "activity_index": round(tm.expected_activity(h) * act_mul, 1), "battery_pct": 90}


def normal_series(n, species="cattle", start=400):
    return [reading(start - i * 10, species) for i in range(n)]


def new_device(client, farm_setup, animal="cow", assign=True):
    body = {"farm_id": farm_setup["farm"]["id"], "name": "Collar"}
    if assign:
        body["animal_id"] = farm_setup[animal]["id"]
    r = client.post(f"{API}/iot/devices", json=body, headers=farm_setup["farmer"]["h"])
    assert r.status_code == 201, r.text
    return r.json()


def send(client, key, readings):
    return client.post(f"{API}/iot/telemetry", json={"readings": readings}, headers={"X-Device-Key": key})


def iot_alerts(client, farm_setup, animal="cow"):
    items = client.get(f"{API}/alerts?animal_id={farm_setup[animal]['id']}&status=all", headers=farm_setup["farmer"]["h"]).json()["items"]
    return [a for a in items if a["type"] == "iot_anomaly"]


def test_device_registry_and_auth(client, farm_setup, make_user):
    d = new_device(client, farm_setup)
    assert d["api_key"].startswith("dev_") and d["status"] == "never_seen"
    assert "api_key" not in client.get(f"{API}/iot/devices", headers=farm_setup["farmer"]["h"]).json()[0]  # key shown only once
    assert send(client, "wrong-key", [reading(1)]).status_code == 401
    assert client.post(f"{API}/iot/telemetry", json={"temperature_c": 38.6}).status_code == 401
    vet, other = make_user("vet"), make_user("farmer")
    body = {"farm_id": farm_setup["farm"]["id"], "name": "x"}
    assert client.post(f"{API}/iot/devices", json=body, headers=vet["h"]).status_code == 403
    assert client.post(f"{API}/iot/devices", json=body, headers=other["h"]).status_code == 404
    assert client.get(f"{API}/iot/devices", headers=other["h"]).json() == []
    assert client.post(f"{API}/iot/devices", json={**body, "animal_id": farm_setup["cow"]["id"]}, headers=farm_setup["farmer"]["h"]).status_code == 409  # one device per animal


def test_normal_data_raises_no_alert(client, farm_setup):
    d = new_device(client, farm_setup)
    r = send(client, d["api_key"], normal_series(40))
    assert r.status_code == 201 and r.json()["analyzed"] is True
    assert iot_alerts(client, farm_setup) == []
    assert client.get(f"{API}/iot/devices", headers=farm_setup["farmer"]["h"]).json()[0]["status"] == "online"


def test_sustained_anomaly_creates_alert(client, farm_setup):
    d = new_device(client, farm_setup)
    send(client, d["api_key"], normal_series(40, start=500))
    bad = [reading(60 - i * 10, temp_add=2.0, hr_mul=1.4, act_mul=0.3) for i in range(6)]
    r = send(client, d["api_key"], bad).json()
    assert r["alert_id"] is not None
    alerts = iot_alerts(client, farm_setup)
    assert len(alerts) == 1 and alerts[0]["severity"] == "high"
    assert "high temperature" in alerts[0]["message_en"] and alerts[0]["message_bn"]
    again = send(client, d["api_key"], [reading(0, temp_add=2.0, hr_mul=1.4, act_mul=0.3)]).json()
    assert len(iot_alerts(client, farm_setup)) == 1  # de-duplicated, not spammed
    animal = client.get(f"{API}/animals/{farm_setup['cow']['id']}", headers=farm_setup["farmer"]["h"]).json()
    assert animal["status"] == "under_observation"


def test_single_noisy_reading_is_ignored(client, farm_setup):
    d = new_device(client, farm_setup)
    series = normal_series(30, start=500)
    series.append(reading(100, temp_add=2.0))  # one spike
    series += [reading(90 - i * 10) for i in range(5)]
    send(client, d["api_key"], series)
    assert iot_alerts(client, farm_setup) == []


def test_critical_temperature_alerts_quickly(client, farm_setup):
    d = new_device(client, farm_setup)
    send(client, d["api_key"], normal_series(20, start=300))
    r = send(client, d["api_key"], [{"recorded_at": ts(10), "temperature_c": 41.6}, {"recorded_at": ts(5), "temperature_c": 41.8}]).json()
    assert r["alert_id"] is not None
    assert iot_alerts(client, farm_setup)[0]["severity"] == "high"


def test_temperature_only_device_works(client, farm_setup):
    d = new_device(client, farm_setup, animal="goat")
    base = [{"recorded_at": ts(300 - i * 10), "temperature_c": round(tm.expected_temp("goat", (datetime.now(timezone.utc) - timedelta(minutes=300 - i * 10)).hour), 2)} for i in range(25)]
    assert send(client, d["api_key"], base).json()["alert_id"] is None
    fever = [{"recorded_at": ts(40 - i * 10), "temperature_c": 41.2} for i in range(4)]
    assert send(client, d["api_key"], fever).json()["alert_id"] is not None


def test_invalid_readings_are_rejected(client, farm_setup):
    d = new_device(client, farm_setup)
    assert send(client, d["api_key"], [{"temperature_c": 80}]).status_code == 422
    assert client.post(f"{API}/iot/telemetry", json={}, headers={"X-Device-Key": d["api_key"]}).status_code == 422
    r = send(client, d["api_key"], [reading(5), {"temperature_c": 99}]).json()
    assert r["accepted"] == 1 and r["rejected"][0]["index"] == 1
    single = client.post(f"{API}/iot/telemetry", json={"temperature_c": 38.7}, headers={"X-Device-Key": d["api_key"]})
    assert single.status_code == 201 and single.json()["accepted"] == 1  # single flat reading works too


def test_unassigned_device_stores_without_analysis(client, farm_setup):
    d = new_device(client, farm_setup, assign=False)
    r = send(client, d["api_key"], [reading(1)]).json()
    assert r["accepted"] == 1 and r["analyzed"] is False
    h = farm_setup["farmer"]["h"]
    assert client.patch(f"{API}/iot/devices/{d['id']}", json={"animal_id": farm_setup["cow"]["id"]}, headers=h).json()["animal_tag"]
    assert client.patch(f"{API}/iot/devices/{d['id']}", json={"animal_id": None}, headers=h).json()["status"] == "unassigned"


def test_offline_and_low_battery_alerts(client, farm_setup):
    from app.database import SessionLocal
    from app.models import Device
    from app.scheduler.jobs import run_job
    d = new_device(client, farm_setup)
    send(client, d["api_key"], [dict(reading(1), battery_pct=8)])
    db = SessionLocal()
    dev = db.get(Device, d["id"])
    dev.last_seen_at = datetime.utcnow() - timedelta(hours=2)
    db.commit(); db.close()
    run_job("iot_offline_check")
    types = {a["type"] for a in client.get(f"{API}/alerts?animal_id={farm_setup['cow']['id']}&status=all", headers=farm_setup["farmer"]["h"]).json()["items"]}
    assert {"device_offline", "device_low_battery"} <= types


def test_readings_endpoint_and_summary(client, farm_setup, make_user):
    d = new_device(client, farm_setup)
    send(client, d["api_key"], normal_series(30))
    h = farm_setup["farmer"]["h"]
    r = client.get(f"{API}/iot/animals/{farm_setup['cow']['id']}/readings?hours=24", headers=h).json()
    assert r["total_readings"] == 30 and r["points"] and r["latest"]["temperature_c"] and r["devices"][0]["status"] == "online"
    s = client.get(f"{API}/iot/summary", headers=h).json()
    assert s["devices"] >= 1 and s["online"] >= 1
    other = make_user("farmer")
    assert client.get(f"{API}/iot/animals/{farm_setup['cow']['id']}/readings", headers=other["h"]).status_code == 404


def test_rotate_key_invalidates_old_key(client, farm_setup):
    d = new_device(client, farm_setup)
    new = client.post(f"{API}/iot/devices/{d['id']}/rotate-key", headers=farm_setup["farmer"]["h"]).json()["api_key"]
    assert send(client, d["api_key"], [reading(1)]).status_code == 401
    assert send(client, new, [reading(1)]).status_code == 201


def test_anomaly_model_quality(client):
    from app.config import settings
    m = json.loads((settings.MODEL_DIR / "anomaly_metrics.json").read_text())
    assert m["episode_detection_rate"] >= 0.8       # checks the pipeline on simulated data
    assert m["false_alerts_per_animal_week"] < 1.0
