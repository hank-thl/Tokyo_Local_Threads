import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"


@dataclass(frozen=True)
class Config:
    flask_env: str
    secret_key: str
    cors_origins: list[str]
    mongodb_uri: str
    mongodb_db_name: str
    mongodb_collection_name: str


def load_config() -> Config:
    load_dotenv(ENV_PATH)

    cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:5173")
    return Config(
        flask_env=os.environ.get("FLASK_ENV", "development"),
        secret_key=os.environ.get("SECRET_KEY", "dev-secret-key"),
        cors_origins=[origin.strip() for origin in cors_origins.split(",") if origin.strip()],
        mongodb_uri=os.environ.get("MONGODB_URI", ""),
        mongodb_db_name=os.environ.get("MONGODB_DB_NAME", "tokyo_local_threads"),
        mongodb_collection_name=os.environ.get("MONGODB_COLLECTION_NAME", "documents"),
    )
