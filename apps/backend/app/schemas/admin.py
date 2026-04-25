from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SkillHistoryResponse(BaseModel):
    user_id: str
    revisions: list[dict]


class AdminRecomputeResponse(BaseModel):
    skill_update_job_id: str
    status: str


class RuntimeProviderResponse(BaseModel):
    generation_provider: str
    embedding_provider: str
    generation_model: str
    embedding_model: str
    embedding_dimensions: int
    local_embed_device: str


class ExperimentRunCreateRequest(BaseModel):
    user_id: str
    chat_message_id: str
    condition_name: str
    skills_enabled: bool
    candidate_count: int
    notes: str | None = None


class ExperimentRunResponse(BaseModel):
    run_id: str
    user_id: str
    chat_message_id: str
    condition_name: str
    skills_enabled: bool
    candidate_count: int
    notes: str | None
    created_at: datetime
