"""Optional in-process demo: keeps the seeded demo collars sending data so an online demo looks alive.
Enable with  IOT_DEMO_SIMULATOR=true.  Every ~20 minutes one collar has a short fever episode."""
import logging
import threading
import time
from datetime import timezone, datetime
from ..database import SessionLocal
from ..ml.telemetry import LiveGenerator
from ..models import Animal, Device
from . import iot

log = logging.getLogger("iot_demo")
TAGS = ["C-001", "C-003", "G-002"]
SPECIES = {"C": "cattle", "G": "goat", "S": "sheep"}


def _loop(interval):
    gens, cycle = {}, 0
    while True:
        try:
            db = SessionLocal()
            try:
                for tag in TAGS:
                    d = db.query(Device).filter(Device.key_hash == iot.hash_key(f"demo-device-key-{tag}")).first()
                    if not d:
                        continue  # demo data not created yet
                    gen = gens.setdefault(tag, LiveGenerator(SPECIES[tag[0]], seed=sum(map(ord, tag)) + 99))
                    if tag == TAGS[0] and cycle % 80 == 40:
                        gen.start_episode(14)
                    r = gen.next(datetime.now(timezone.utc))
                    iot.ingest(db, d, [r], notify=True)
                    db.commit()
            finally:
                db.close()
        except Exception:  # never stop the demo because of one failed cycle (for example a locked SQLite file)
            log.exception("demo simulator cycle failed")
        cycle += 1
        time.sleep(interval)


def start(interval=15):
    t = threading.Thread(target=_loop, args=(interval,), daemon=True, name="iot-demo")
    t.start()
    return t
