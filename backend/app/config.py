from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["demo", "openai"] = "demo"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.0

    db_path: Path = Path("data/northwind.db")
    checkpoint_path: Path = Path("data/checkpoints.db")

    max_supervisor_steps: int = 8
    max_revisions: int = 1

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    def resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else BACKEND_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
