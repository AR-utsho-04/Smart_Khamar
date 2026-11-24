"""Pretend to be IoT collars: sends readings to the running backend, like a real device would.

Examples (run inside the backend folder, with the backend running):
  python scripts/iot_simulator.py                      # 3 healthy demo animals, a reading every 3 seconds
  python scripts/iot_simulator.py --sick C-001         # C-001 develops a fever after 8 readings -> watch the alert appear
  python scripts/iot_simulator.py --device-key dev_xxx --species cattle    # simulate YOUR device (key from the Devices page)
Stop with Ctrl+C."""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.ml.telemetry import LiveGenerator  # noqa: E402

SPECIES = {"C": "cattle", "G": "goat", "S": "sheep"}


def post(api, key, body):
    req = urllib.request.Request(f"{api}/api/v1/iot/telemetry", data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Device-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")
    except Exception as e:  # backend not running, wrong address, ...
        return 0, {"detail": str(e)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", default="http://127.0.0.1:8000", help="backend address")
    ap.add_argument("--interval", type=float, default=3.0, help="seconds between readings")
    ap.add_argument("--tags", default="C-001,C-003,G-002", help="demo animals (seeded devices use key demo-device-key-<TAG>)")
    ap.add_argument("--sick", default="", help="comma list of tags that start a fever episode")
    ap.add_argument("--after", type=int, default=8, help="readings before the episode starts")
    ap.add_argument("--length", type=int, default=14, help="length of the episode in readings")
    ap.add_argument("--device-key", default="", help="simulate one real device by its key")
    ap.add_argument("--species", default="cattle", choices=["cattle", "goat", "sheep"])
    a = ap.parse_args()

    if a.device_key:
        fleet = [("device", a.device_key, LiveGenerator(a.species, seed=1))]
    else:
        fleet = [(t, f"demo-device-key-{t}", LiveGenerator(SPECIES[t[0]], seed=sum(map(ord, t)))) for t in a.tags.split(",") if t]
    sick = {t for t in a.sick.split(",") if t}
    print(f"Simulating {len(fleet)} device(s) -> {a.api}  (Ctrl+C to stop)")
    n = 0
    try:
        while True:
            n += 1
            for tag, key, gen in fleet:
                if tag in sick and n == a.after + 1:
                    gen.start_episode(a.length)
                    print(f"   >>> {tag}: fever episode starts now")
                r = gen.next(datetime.now(timezone.utc))
                body = {**r, "recorded_at": r["recorded_at"].strftime("%Y-%m-%dT%H:%M:%SZ")}
                code, res = post(a.api, key, body)
                stamp = datetime.now().strftime("%H:%M:%S")
                if code == 201:
                    note = f"ALERT created (#{res['alert_id']})" if res.get("alert_id") else ("flagged" if res["anomalies"] else "ok")
                    print(f"[{stamp}] {tag:7s} temp {r['temperature_c']:5.2f}  hr {r['heart_rate_bpm']:5.1f}  act {r['activity_index']:5.1f}  -> {note}")
                else:
                    print(f"[{stamp}] {tag:7s} ERROR {code}: {res.get('detail')} (is the backend running? is the device key right?)")
            time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
