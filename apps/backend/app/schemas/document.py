from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    mime_type: str
    ingest_status: str
    created_at: datetime


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
