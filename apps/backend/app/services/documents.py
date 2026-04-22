from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_provider
from app.models.entities import Embedding, IngestionJob, RagDocument, RagDocumentChunk, utcnow
from app.rag.chunking import chunk_text
from app.rag.parsing import parse_document


def save_upload(file: UploadFile) -> tuple[Path, str]:
    settings = get_settings()
    target_path = settings.upload_dir / f"{utcnow().timestamp()}_{file.filename}"
    content = file.file.read()
    target_path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    return target_path, digest


def create_document(session: Session, file: UploadFile) -> RagDocument:
    path, digest = save_upload(file)
    document = RagDocument(
        filename=file.filename or "uploaded.txt",
        mime_type=file.content_type or "text/plain",
        source_type="upload",
        storage_path=str(path),
        sha256=digest,
        ingest_status="pending",
    )
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def create_ingestion_job(session: Session, document_id: str) -> IngestionJob:
    job = IngestionJob(document_id=document_id, status="pending", updated_at=utcnow())
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def list_documents(session: Session) -> list[RagDocument]:
    return list(session.scalars(select(RagDocument).order_by(RagDocument.created_at.desc())))


def list_chunks(session: Session, document_id: str) -> list[tuple[RagDocumentChunk, bool]]:
    chunks = list(
        session.scalars(
            select(RagDocumentChunk)
            .where(RagDocumentChunk.document_id == document_id)
            .order_by(RagDocumentChunk.chunk_index.asc())
        )
    )
    pairs = []
    for chunk in chunks:
        has_embedding = session.scalar(select(Embedding.id).where(Embedding.chunk_id == chunk.id)) is not None
        pairs.append((chunk, has_embedding))
    return pairs


def process_ingestion_job(session: Session, job: IngestionJob) -> None:
    settings = get_settings()
    provider = get_provider(settings)
    document = session.get(RagDocument, job.document_id)
    if not document:
        raise ValueError("Document not found")

    job.status = "running"
    job.attempt_count += 1
    job.updated_at = utcnow()
    document.ingest_status = "running"
    session.commit()

    text = parse_document(Path(document.storage_path), document.mime_type)
    chunks = chunk_text(text)

    chunk_ids = list(
        session.scalars(select(RagDocumentChunk.id).where(RagDocumentChunk.document_id == document.id))
    )
    if chunk_ids:
        session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
    session.execute(delete(RagDocumentChunk).where(RagDocumentChunk.document_id == document.id))
    session.flush()

    for index, chunk_text_value in enumerate(chunks):
        chunk = RagDocumentChunk(
            document_id=document.id,
            chunk_index=index,
            content=chunk_text_value,
            char_count=len(chunk_text_value),
            chunking_strategy=f"paragraph+{settings.default_chunk_size}/{settings.default_chunk_overlap}",
            metadata_json={"filename": document.filename},
        )
        session.add(chunk)
        session.flush()
        vector = provider.embed_texts([chunk_text_value])[0]
        embedding = Embedding(
            chunk_id=chunk.id,
            provider_name=provider.provider_name,
            model_name=settings.gemini_model_embed if provider.provider_name == "gemini" else "mock-embedding",
            vector=vector,
            dimensions=len(vector),
        )
        session.add(embedding)

    job.status = "completed"
    job.error_message = None
    job.updated_at = utcnow()
    document.ingest_status = "completed"
    session.commit()
