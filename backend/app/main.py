import logging
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from . import models  # noqa: F401  (registers tables)
from .ml import predict as ml
from .routers import auth, farms, animals, records, alerts, vet, dashboard, admin, iot
from .scheduler.jobs import start_scheduler
from .services.common import ValidationFail
from .services.lookups import ensure_lookups

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        ensure_lookups(db)
    finally:
        db.close()
    if settings.SEED_DEMO:  # used for online demos: the free host forgets the database when it sleeps
        seeding = SessionLocal()
        has_users = seeding.query(User).count() > 0
        seeding.close()
        if not has_users:
            from scripts.seed import main as seed_main
            threading.Thread(target=seed_main, daemon=True).start()  # runs in the background so the site starts fast
    if not ml.model_available():
        logging.warning("AI model not found. Run:  python -m app.ml.train   (records still save; predictions return no result)")
    if settings.IOT_DEMO_SIMULATOR:
        from .services import iot_demo
        iot_demo.start()
    sched = start_scheduler() if settings.SCHEDULER_ENABLED else None
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="AI-Based Livestock Health Monitoring System", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(ValidationFail)
async def validation_fail(request: Request, exc: ValidationFail):
    return JSONResponse(status_code=422, content={"detail": "validation_error", "errors": exc.errors})


@app.exception_handler(RequestValidationError)
async def request_validation(request: Request, exc: RequestValidationError):
    errs = [{"field": ".".join(str(p) for p in e["loc"] if p not in ("body", "query")), "message": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "validation_error", "errors": errs})


@app.get("/health")
def health():
    return {"status": "ok"}


for r in (auth, farms, animals, records, alerts, vet, dashboard, admin, iot):
    app.include_router(r.router, prefix="/api/v1")


# ---- Serve the built website (frontend/dist) from the same server, for online publishing ----
_dist = settings.FRONTEND_DIST
if (_dist / "index.html").exists():
    if (_dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(status_code=404, content={"detail": "not_found"})
        f = (_dist / full_path).resolve()
        if full_path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")  # React handles the page routes
