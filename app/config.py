from functools import lru_cache
from pydantic import BaseModel
import os

class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "PetConnect")
    env: str = os.getenv("APP_ENV", "dev")
    mongodb_uri: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    db_name: str = os.getenv("DB_NAME", "petconnect")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me")
    jwt_expires_hours: int = int(os.getenv("JWT_EXPIRES_HOURS", "8"))

@lru_cache
def get_settings() -> Settings:
    return Settings()
