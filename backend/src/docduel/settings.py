from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    config_dir: Path = REPO_DIR / "config"
    data_dir: Path = REPO_DIR / "data"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'docduel.db').as_posix()}"
    live_mode_enabled: bool = False
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
