from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from fastapi import UploadFile
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_generation_model_name, get_generation_provider
from app.models.entities import (
    DocumentSkill,
    DocumentSkillEntry,
    DocumentSkillRevision,
    DocumentSkillUsageLog,
    Embedding,
    IngestionJob,
    RagDocument,
    RagDocumentChunk,
    RetrievalLog,
    utcnow,
)
from app.rag.parsing import parse_document
from app.skills.document_merger import empty_document_skill_profile, merge_document_skill_profile, profile_to_entries

logger = logging.getLogger(__name__)


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
    document = session.get(RagDocument, document_id)
    if not document:
        raise ValueError("Document not found")
    document.ingest_status = "pending"
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


def get_document_skill(session: Session, document_id: str) -> tuple[RagDocument, DocumentSkill | None, DocumentSkillRevision | None]:
    document = session.get(RagDocument, document_id)
    if not document:
        raise ValueError("Document not found")
    document_skill = session.scalar(select(DocumentSkill).where(DocumentSkill.document_id == document_id))
    revision = session.get(DocumentSkillRevision, document_skill.active_revision_id) if document_skill and document_skill.active_revision_id else None
    return document, document_skill, revision


def list_document_skill_revisions(session: Session, document_id: str) -> list[DocumentSkillRevision]:
    _document, document_skill, _revision = get_document_skill(session, document_id)
    if not document_skill:
        return []
    return list(
        session.scalars(
            select(DocumentSkillRevision)
            .where(DocumentSkillRevision.document_skill_id == document_skill.id)
            .order_by(DocumentSkillRevision.revision_number.desc())
        )
    )


def list_document_skill_entries(session: Session, document_id: str) -> list[DocumentSkillEntry]:
    _document, _document_skill, revision = get_document_skill(session, document_id)
    if not revision:
        return []
    return list(
        session.scalars(
            select(DocumentSkillEntry)
            .where(DocumentSkillEntry.document_skill_revision_id == revision.id)
            .order_by(DocumentSkillEntry.entry_type.asc(), DocumentSkillEntry.created_at.asc())
        )
    )


def delete_document(session: Session, document_id: str) -> None:
    document = session.get(RagDocument, document_id)
    if not document:
        raise ValueError("Document not found")

    storage_path = Path(document.storage_path)
    chunk_ids = list(
        session.scalars(select(RagDocumentChunk.id).where(RagDocumentChunk.document_id == document.id))
    )
    document_skill = session.scalar(select(DocumentSkill).where(DocumentSkill.document_id == document.id))
    if document_skill:
        revision_ids = list(
            session.scalars(
                select(DocumentSkillRevision.id).where(DocumentSkillRevision.document_skill_id == document_skill.id)
            )
        )
        session.execute(delete(DocumentSkillUsageLog).where(DocumentSkillUsageLog.document_id == document.id))
        if revision_ids:
            session.execute(delete(DocumentSkillEntry).where(DocumentSkillEntry.document_skill_revision_id.in_(revision_ids)))
        document_skill.active_revision_id = None
        session.flush()
        session.execute(delete(DocumentSkillRevision).where(DocumentSkillRevision.document_skill_id == document_skill.id))
        session.execute(delete(DocumentSkill).where(DocumentSkill.id == document_skill.id))
    if chunk_ids:
        session.execute(delete(RetrievalLog).where(RetrievalLog.chunk_id.in_(chunk_ids)))
        session.execute(delete(Embedding).where(Embedding.chunk_id.in_(chunk_ids)))
    session.execute(delete(IngestionJob).where(IngestionJob.document_id == document.id))
    session.execute(delete(RagDocumentChunk).where(RagDocumentChunk.document_id == document.id))
    session.execute(delete(RagDocument).where(RagDocument.id == document.id))
    session.flush()

    try:
        storage_path.unlink(missing_ok=True)
    except OSError:
        logger.exception("Failed to delete uploaded document file: %s", storage_path)
        raise

    session.commit()


def process_ingestion_job(session: Session, job: IngestionJob) -> None:
    settings = get_settings()
    provider = get_generation_provider(settings)
    document = session.get(RagDocument, job.document_id)
    if not document:
        raise ValueError("Document not found")

    document_skill = _get_or_create_document_skill(session, document)
    try:
        job.status = "running"
        job.attempt_count += 1
        job.updated_at = utcnow()
        document.ingest_status = "running"
        document_skill.status = "running"
        document_skill.updated_at = utcnow()
        session.commit()

        units = _parse_document_skill_units(Path(document.storage_path), document.mime_type, settings.default_chunk_size)
        profile = empty_document_skill_profile(document.filename)
        document_metadata = {
            "document_id": document.id,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "source_type": document.source_type,
            "sha256": document.sha256,
        }
        last_metadata = None
        for unit in units:
            delta, metadata = provider.extract_document_skill_delta(document_metadata, unit, profile)
            profile = merge_document_skill_profile(profile, delta.model_dump())
            last_metadata = metadata

        revision_number = (
            session.scalar(
                select(DocumentSkillRevision.revision_number)
                .where(DocumentSkillRevision.document_skill_id == document_skill.id)
                .order_by(DocumentSkillRevision.revision_number.desc())
                .limit(1)
            )
            or 0
        ) + 1
        revision = DocumentSkillRevision(
            document_skill_id=document_skill.id,
            revision_number=revision_number,
            profile_json=profile,
            summary=profile.get("summary", ""),
            extraction_model_name=last_metadata.model_name if last_metadata else get_generation_model_name(settings),
            prompt_version=settings.prompt_version,
            source_digest=document.sha256,
            update_reason="document_skill_extraction",
        )
        session.add(revision)
        session.flush()
        for entry_payload in profile_to_entries(profile):
            session.add(DocumentSkillEntry(document_skill_revision_id=revision.id, **entry_payload))

        document_skill.active_revision_id = revision.id
        document_skill.status = "completed"
        document_skill.updated_at = utcnow()
        job.status = "completed"
        job.error_message = None
        job.updated_at = utcnow()
        document.ingest_status = "completed"
        session.commit()
    except Exception as exc:
        logger.exception("Document Skill extraction failed for document_id=%s", document.id)
        session.rollback()
        failed_document = session.get(RagDocument, document.id)
        failed_skill = session.scalar(select(DocumentSkill).where(DocumentSkill.document_id == document.id))
        failed_job = session.get(IngestionJob, job.id)
        if failed_job:
            failed_job.status = "failed"
            failed_job.error_message = str(exc)
            failed_job.updated_at = utcnow()
        if failed_document:
            failed_document.ingest_status = "failed"
        if failed_skill:
            failed_skill.status = "failed"
            failed_skill.updated_at = utcnow()
        session.commit()
        raise


def _get_or_create_document_skill(session: Session, document: RagDocument) -> DocumentSkill:
    document_skill = session.scalar(select(DocumentSkill).where(DocumentSkill.document_id == document.id))
    if document_skill:
        return document_skill
    document_skill = DocumentSkill(document_id=document.id, status="pending", updated_at=utcnow())
    session.add(document_skill)
    session.flush()
    return document_skill


def _parse_document_skill_units(path: Path, mime_type: str, max_chars: int) -> list[dict]:
    if mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
        units: list[dict] = []
        reader = PdfReader(str(path))
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for split_index, text_part in enumerate(_split_text(text, max_chars), start=1):
                units.append(
                    {
                        "unit_index": len(units),
                        "text": text_part,
                        "source_page": page_index,
                        "source_span": f"page:{page_index}:part:{split_index}",
                    }
                )
        return units or [{"unit_index": 0, "text": "", "source_page": None, "source_span": None}]

    text = parse_document(path, mime_type)
    return [
        {"unit_index": index, "text": text_part, "source_page": None, "source_span": f"part:{index + 1}"}
        for index, text_part in enumerate(_split_text(text, max_chars))
    ]


def _split_text(text: str, max_chars: int) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []
    units: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue
        if current:
            units.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
        else:
            units.extend(paragraph[index : index + max_chars] for index in range(0, len(paragraph), max_chars))
            current = ""
    if current:
        units.append(current)
    return units or [text[:max_chars]]
