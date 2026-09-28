from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE)

    anthropic_api_key: str
    voyage_api_key: str
    github_client_id: str
    github_client_secret: str
    frontend_url: str = "http://localhost:5173"


settings = Settings()
