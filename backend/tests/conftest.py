import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["MODEL_DIR"] = f"{_tmp}/model"
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.config import settings
    from app.ml.train import train
    train(n_rows=3000, model_dir=settings.MODEL_DIR, verbose=False)  # small model for tests
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def make_user(client):
    from app.database import SessionLocal
    from app.models import User
    counter = {"n": 0}

    def _make(role="farmer", approve=True):
        counter["n"] += 1
        email = f"{role}{counter['n']}@test.com"
        r = client.post("/api/v1/auth/register", json={"name": f"{role} {counter['n']}", "email": email, "password": "Password123!",
                                                         "role": role if role != "admin" else "farmer"})
        assert r.status_code == 201, r.text
        uid = r.json()["id"]
        db = SessionLocal()
        u = db.get(User, uid)
        if role == "admin":
            u.role = "admin"
        if approve:
            u.is_approved = True
        db.commit(); db.close()
        tok = client.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"}).json()["access_token"]
        return {"id": uid, "email": email, "h": _auth(tok)}
    return _make


@pytest.fixture()
def farm_setup(client, make_user):
    """A farmer with a farm and one cattle and one goat."""
    f = make_user("farmer")
    farm = client.post("/api/v1/farms", json={"name": "Test Farm"}, headers=f["h"]).json()
    def animal(tag, species="cattle", sex="female"):
        r = client.post("/api/v1/animals", json={"farm_id": farm["id"], "tag_no": tag, "species": species, "sex": sex, "age_months": 36}, headers=f["h"])
        assert r.status_code == 201, r.text
        return r.json()
    import uuid
    s = uuid.uuid4().hex[:5]
    return {"farmer": f, "farm": farm, "cow": animal(f"C-{s}"), "goat": animal(f"G-{s}", "goat")}
