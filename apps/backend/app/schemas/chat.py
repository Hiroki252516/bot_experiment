from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ChatGenerateRequest(BaseModel):
    user_id: str
    question: str
    document_ids: list[str] | None = None
    course_context: str | None = None
    candidate_count: int = 3
    skills_enabled: bool = True
    session_id: str | None = None
    experiment_condition: str | None = None

    @field_validator("candidate_count")
    @classmethod
    def validate_candidate_count(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("candidate_count must be between 1 and 5")
        return value


class RetrievalItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    score: float
    text: str


class CandidateResponse(BaseModel):
    candidate_id: str
    title: str
    style_tags: list[str]
    answer_text: str
    rank: int
    display_order: int


class ChatGenerateResponse(BaseModel):
    session_id: str
    chat_message_id: str
    generation_run_id: str
    skills_enabled: bool
    active_skill_revision_id: str | None
    retrievals: list[RetrievalItemResponse]
    candidates: list[CandidateResponse]


class ChatSelectRequest(BaseModel):
    chat_message_id: str
    selected_candidate_id: str
    satisfaction_score: int = Field(ge=1, le=10)
    clarity_score: int = Field(ge=1, le=10)
    comment: str | None = None


class ChatSelectResponse(BaseModel):
    selection_id: str
    skill_update_job_id: str
    status: str


class SessionMessageDetail(BaseModel):
    chat_message_id: str
    question_text: str
    skills_enabled: bool
    active_skill_revision_id: str | None
    candidates: list[CandidateResponse]
    selection: dict | None
    retrievals: list[RetrievalItemResponse]
    created_at: datetime


class SessionDetailResponse(BaseModel):
    session_id: str
    user_id: str
    messages: list[SessionMessageDetail]
