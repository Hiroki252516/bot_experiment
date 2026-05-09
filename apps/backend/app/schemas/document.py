from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    mime_type: str
    source_type: str
    ingest_status: str
    created_at: datetime
    document_skill_status: str | None = None
    active_document_skill_revision_id: str | None = None
    document_skill_revision_number: int | None = None
    document_skill_entries_count: int = 0
    document_skill_updated_at: datetime | None = None


class IngestJobResponse(BaseModel):
    ingestion_job_id: str
    status: str


class DocumentDeleteResponse(BaseModel):
    document_id: str
    deleted: bool


class DocumentChunkResponse(BaseModel):
    chunk_id: str
    chunk_index: int
    content: str
    metadata: dict
    has_embedding: bool
