from functools import lru_cache
from pydantic import BaseModel
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()  # carga el archivo .env de la raíz

class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "PetConnect")
    env: str = os.getenv("APP_ENV", "dev")
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = os.getenv("DB_NAME", "petconnect")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_expires_hours: int = int(os.getenv("JWT_EXPIRES_HOURS", "8"))
    media_dir: str = os.getenv("MEDIA_DIR", str(Path(__file__).resolve().parents[1] / "media"))
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    billing_provider: str = os.getenv("BILLING_PROVIDER", "mock").lower()

    

_settings: Settings | None = None
def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        Path(_settings.media_dir).mkdir(parents=True, exist_ok=True)
        Path(_settings.media_dir, "pets").mkdir(parents=True, exist_ok=True)
        Path(_settings.media_dir, "reports").mkdir(parents=True, exist_ok=True)
    return _settings