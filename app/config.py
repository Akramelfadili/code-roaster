from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application configuration, loaded from environment variables or `.env`."""

    model_config = SettingsConfigDict(env_file=_ENV_FILE)

    anthropic_api_key: str
    voyage_api_key: str
    github_client_id: str
    github_client_secret: str
    frontend_url: str = "http://localhost:5173"
    database_url: str
    test_database_url: str | None = None
    daily_cost_budget_usd: float = 10.0
    chroma_persist_dir: Path = Path("data/chroma")

    @field_validator("chroma_persist_dir")
    @classmethod
    def _resolve_against_project_root(cls, path: Path) -> Path:
        """Anchor a relative path to the project root, not the working directory."""
        return path if path.is_absolute() else _PROJECT_ROOT / path


settings = Settings()
