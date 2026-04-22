from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Learning Skill Accumulation Chatbot"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "sqlite+pysqlite:///:memory:"
    backend_cors_origins: str = "http://localhost:3000"
    upload_dir: Path = Path("/tmp/tutorbot/uploads")
    export_dir: Path = Path("/tmp/tutorbot/exports")
    seed_dir: Path = Path("/tmp/tutorbot/seeds")

    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model_generate: str = "gemini-2.0-flash"
    gemini_model_embed: str = "gemini-embedding-001"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    default_candidate_count: int = 3
    default_retrieval_top_k: int = 5
    default_chunk_size: int = 1200
    default_chunk_overlap: int = 200
    embedding_dimensions: int = 768
    skill_updater_poll_interval_seconds: int = 5
    job_batch_size: int = 10

    generation_temperature: float = 0.4
    generation_top_p: float = 0.9
    prompt_version: str = "v1"
    request_timeout_seconds: float = 30.0

    default_skill_profile: dict = Field(
        default_factory=lambda: {
            "preferred_explanation_style": [],
            "preferred_structure_pattern": [],
            "preferred_hint_level": "medium",
            "preferred_answer_length": "medium",
            "disliked_patterns": [],
            "evidence_preference": "cite-retrieved-context",
            "notes": [],
        }
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings

