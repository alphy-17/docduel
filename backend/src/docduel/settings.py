from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", extra="ignore", populate_by_name=True
    )

    config_dir: Path = REPO_DIR / "config"
    data_dir: Path = REPO_DIR / "data"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'docduel.db').as_posix()}"
    live_mode_enabled: bool = False
    # Required on POST /api/runs in live mode. .env uses LIVE_ACCESS_CODE (ACCESS_CODE also works).
    access_code: SecretStr = Field(
        default=SecretStr(""), validation_alias=AliasChoices("LIVE_ACCESS_CODE", "ACCESS_CODE")
    )
    rate_limit_per_hour: int = 30  # live mode only: uploads + runs per visitor per hour
    corrections_enabled: bool = True  # the Corrections page is a local tool; off in production
    cors_origins: str = "http://localhost:5173"

    # Document ingestion
    azure_di_endpoint: str = ""
    azure_di_key: SecretStr = SecretStr("")
    keep_uploads: bool = True  # dev keeps files for previews; production sets False (rule R7)

    @property
    def ocr_cache_dir(self) -> Path:
        return self.data_dir / "cache" / "ocr"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
