import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
BASE_DIR = Path(__file__).resolve().parent


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./livestock.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM = os.getenv("SMTP_FROM", "alerts@example.com")
    SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"
    SENSOR_API_KEY = os.getenv("SENSOR_API_KEY", "dev-sensor-key")
    SEED_DEMO = os.getenv("SEED_DEMO", "false").lower() == "true"
    FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST", str(BASE_DIR.parent.parent / "frontend" / "dist")))
    IOT_DEMO_SIMULATOR = os.getenv("IOT_DEMO_SIMULATOR", "false").lower() == "true"
    MODEL_DIR = Path(os.getenv("MODEL_DIR", str(BASE_DIR / "ml" / "artifacts")))


settings = Settings()
