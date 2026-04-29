from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.db.base import Base
from app.db.vector import EmbeddingVectorType

settings = get_settings()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    session_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_sessions.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    question_text: Mapped[str] = mapped_column(Text)
    skills_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    active_skill_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    experiment_condition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnswerGenerationRun(Base):
    __tablename__ = "answer_generation_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    chat_message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    provider_name: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(100))
    temperature: Mapped[float] = mapped_column(Float)
    top_p: Mapped[float] = mapped_column(Float)
    candidate_count: Mapped[int] = mapped_column(Integer)
    prompt_version: Mapped[str] = mapped_column(String(100))
    retrieval_top_k: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnswerCandidate(Base):
    __tablename__ = "answer_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    generation_run_id: Mapped[str] = mapped_column(ForeignKey("answer_generation_runs.id"))
    rank: Mapped[int] = mapped_column(Integer)
    display_order: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    style_tags: Mapped[list] = mapped_column(JSON, default=list)
    answer_text: Mapped[str] = mapped_column(Text)
    rationale_internal: Mapped[str] = mapped_column(Text)
    is_selected_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnswerSelection(Base):
    __tablename__ = "answer_selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    chat_message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"), unique=True)
    selected_candidate_id: Mapped[str] = mapped_column(ForeignKey("answer_candidates.id"))
    satisfaction_score: Mapped[int] = mapped_column(Integer)
    clarity_score: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SubjectiveFeedback(Base):
    __tablename__ = "subjective_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    selection_id: Mapped[str] = mapped_column(ForeignKey("answer_selections.id"))
    feedback_type: Mapped[str] = mapped_column(String(50))
    score_int: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    active_revision_id: Mapped[str | None] = mapped_column(ForeignKey("skill_revisions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    revisions: Mapped[list["SkillRevision"]] = relationship(
        back_populates="skill",
        foreign_keys="SkillRevision.skill_id",
        cascade="all, delete-orphan",
    )


class SkillRevision(Base):
    __tablename__ = "skill_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id"))
    revision_number: Mapped[int] = mapped_column(Integer)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    summary_rule: Mapped[str] = mapped_column(Text)
    update_reason: Mapped[str] = mapped_column(Text)
    source_selection_id: Mapped[str | None] = mapped_column(ForeignKey("answer_selections.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    skill: Mapped["Skill"] = relationship(back_populates="revisions", foreign_keys=[skill_id])


class SkillUpdateJob(Base):
    __tablename__ = "skill_update_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    chat_message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    selection_id: Mapped[str | None] = mapped_column(ForeignKey("answer_selections.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50), default="skill_update")
    status: Mapped[str] = mapped_column(String(50), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RagDocument(Base):
    __tablename__ = "rag_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(50))
    storage_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    ingest_status: Mapped[str] = mapped_column(String(50), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RagDocumentChunk(Base):
    __tablename__ = "rag_document_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("rag_documents.id"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    char_count: Mapped[int] = mapped_column(Integer)
    chunking_strategy: Mapped[str] = mapped_column(String(100))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("rag_document_chunks.id"))
    provider_name: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(100))
    vector: Mapped[list[float]] = mapped_column(EmbeddingVectorType(settings.embedding_dimensions))
    dimensions: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RetrievalLog(Base):
    __tablename__ = "retrieval_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    chat_message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("rag_document_chunks.id"))
    score: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    embedding_model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    chat_message_id: Mapped[str] = mapped_column(ForeignKey("chat_messages.id"))
    condition_name: Mapped[str] = mapped_column(String(100))
    skills_enabled: Mapped[bool] = mapped_column(Boolean)
    candidate_count: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("rag_documents.id"))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
