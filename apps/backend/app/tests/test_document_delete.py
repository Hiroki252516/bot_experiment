from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

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
)
from app.rag.retrieval import retrieve_chunks
from app.services.documents import delete_document


def _create_document_with_rag_rows(session, storage_path: Path) -> tuple[RagDocument, RagDocumentChunk]:
    storage_path.write_text("test document", encoding="utf-8")
    document = RagDocument(
        filename=storage_path.name,
        mime_type="text/plain",
        source_type="test",
        storage_path=str(storage_path),
        sha256="1" * 64,
        ingest_status="completed",
    )
    session.add(document)
    session.flush()
    chunk = RagDocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content="retrieval target",
        char_count=len("retrieval target"),
        chunking_strategy="test",
        metadata_json={},
    )
    session.add(chunk)
    session.flush()
    session.add(
        Embedding(
            chunk_id=chunk.id,
            provider_name="mock",
            model_name="mock-embedding",
            vector=[1.0, 0.0],
            dimensions=2,
        )
    )
    session.add(IngestionJob(document_id=document.id, status="completed"))
    document_skill = DocumentSkill(document_id=document.id, status="completed")
    session.add(document_skill)
    session.flush()
    revision = DocumentSkillRevision(
        document_skill_id=document_skill.id,
        revision_number=1,
        profile_json={"summary": "test"},
        summary="test",
        extraction_model_name="mock-model",
        prompt_version="test",
        source_digest=document.sha256,
        update_reason="test",
    )
    session.add(revision)
    session.flush()
    entry = DocumentSkillEntry(
        document_skill_revision_id=revision.id,
        entry_type="fact",
        title="test",
        content="retrieval target",
        normalized_text="retrieval target",
        metadata_json={},
    )
    session.add(entry)
    session.flush()
    document_skill.active_revision_id = revision.id
    session.add(
        DocumentSkillUsageLog(
            chat_message_id="fake-message-id",
            document_id=document.id,
            document_skill_revision_id=revision.id,
            document_skill_entry_id=entry.id,
            included_order=1,
            context_kind="fact",
            context_hash="0" * 64,
        )
    )
    session.add(
        RetrievalLog(
            chat_message_id="fake-message-id",
            chunk_id=chunk.id,
            score=1.0,
            rank=1,
            embedding_model="mock-embedding",
        )
    )
    session.commit()
    return document, chunk


def test_delete_document_removes_related_rows_and_file(session, tmp_path) -> None:
    document, chunk = _create_document_with_rag_rows(session, tmp_path / "delete-me.txt")

    delete_document(session, document.id)

    assert session.get(RagDocument, document.id) is None
    assert session.get(RagDocumentChunk, chunk.id) is None
    assert session.scalar(select(Embedding.id).where(Embedding.chunk_id == chunk.id)) is None
    assert session.scalar(select(IngestionJob.id).where(IngestionJob.document_id == document.id)) is None
    assert session.scalar(select(RetrievalLog.id).where(RetrievalLog.chunk_id == chunk.id)) is None
    assert session.scalar(select(DocumentSkill.id).where(DocumentSkill.document_id == document.id)) is None
    assert session.scalar(select(DocumentSkillUsageLog.id).where(DocumentSkillUsageLog.document_id == document.id)) is None
    assert not Path(document.storage_path).exists()


def test_delete_missing_document_returns_404(client) -> None:
    response = client.delete("/api/documents/missing-document-id")

    assert response.status_code == 404


def test_deleted_document_is_not_retrieved(session, tmp_path) -> None:
    document, _chunk = _create_document_with_rag_rows(session, tmp_path / "retrieval-delete.txt")
    before = retrieve_chunks(
        session,
        [1.0, 0.0],
        top_k=5,
        provider_name="mock",
        model_name="mock-embedding",
        dimensions=2,
    )
    assert len(before) == 1

    delete_document(session, document.id)
    after = retrieve_chunks(
        session,
        [1.0, 0.0],
        top_k=5,
        provider_name="mock",
        model_name="mock-embedding",
        dimensions=2,
    )

    assert after == []
