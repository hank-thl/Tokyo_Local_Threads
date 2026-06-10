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


def parse_cors_origins() -> list[str]:
    raw_origins = os.environ.get("CORS_ORIGINS")
    frontend_url = os.environ.get("FRONTEND_URL")

    origins = []
    if raw_origins:
        origins.extend(origin.strip() for origin in raw_origins.split(","))
    if frontend_url:
        origins.append(frontend_url.strip())

    # 保留本地開發常用網址，部署時再透過 Render env 加上 Vercel 網址。
    origins.extend(["http://localhost:5173", "http://127.0.0.1:5173"])

    normalized_origins = []
    for origin in origins:
        if not origin:
            continue
        normalized_origin = origin.rstrip("/")
        if normalized_origin not in normalized_origins:
            normalized_origins.append(normalized_origin)

    return normalized_origins


def load_config() -> Config:
    load_dotenv(ENV_PATH)

    return Config(
        flask_env=os.environ.get("FLASK_ENV", "development"),
        secret_key=os.environ.get("SECRET_KEY", "dev-secret-key"),
        cors_origins=parse_cors_origins(),
        mongodb_uri=os.environ.get("MONGODB_URI", ""),
        mongodb_db_name=os.environ.get("MONGODB_DB_NAME", "tokyo_local_threads"),
        mongodb_collection_name=os.environ.get("MONGODB_COLLECTION_NAME", "documents"),
    )
