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
    hf_home: Path = Path("/app/model_cache/huggingface")
    transformers_cache: Path = Path("/app/model_cache/huggingface/transformers")
    sentence_transformers_home: Path = Path("/app/model_cache/sentence-transformers")

    generation_provider: str | None = None
    embedding_provider: str = "local-sentence-transformers"
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model_generate: str = "gemini-2.0-flash"
    gemini_model_embed: str = "gemini-embedding-001"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    local_embed_model: str = "pkshatech/GLuCoSE-base-ja"
    local_embed_device: str = "auto"
    local_embed_batch_size: int = 16
    local_embed_normalize: bool = True
    local_embed_http_url: str = "http://host.docker.internal:8088"

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

    @property
    def active_generation_provider(self) -> str:
        return self.generation_provider or self.llm_provider

    def ensure_directories(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.hf_home.mkdir(parents=True, exist_ok=True)
        self.transformers_cache.mkdir(parents=True, exist_ok=True)
        self.sentence_transformers_home.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
