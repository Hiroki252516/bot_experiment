from __future__ import annotations

from app.models.entities import Embedding, RagDocument, RagDocumentChunk
from app.rag.retrieval import POSTGRES_RETRIEVAL_SQL, retrieve_chunks


def test_postgres_retrieval_sql_casts_nullable_filter_parameters() -> None:
    assert "CAST(:provider_name AS text) IS NULL" in POSTGRES_RETRIEVAL_SQL
    assert "e.provider_name = CAST(:provider_name AS text)" in POSTGRES_RETRIEVAL_SQL
    assert "CAST(:model_name AS text) IS NULL" in POSTGRES_RETRIEVAL_SQL
    assert "e.model_name = CAST(:model_name AS text)" in POSTGRES_RETRIEVAL_SQL
    assert "CAST(:dimensions AS integer) IS NULL" in POSTGRES_RETRIEVAL_SQL
    assert "e.dimensions = CAST(:dimensions AS integer)" in POSTGRES_RETRIEVAL_SQL


def _add_embedding(session, provider_name: str, model_name: str, content: str, vector: list[float]) -> None:
    document = RagDocument(
        filename=f"{model_name}.md",
        mime_type="text/markdown",
        source_type="test",
        storage_path="/tmp/test.md",
        sha256=model_name.ljust(64, "0")[:64],
        ingest_status="completed",
    )
    session.add(document)
    session.flush()
    chunk = RagDocumentChunk(
        document_id=document.id,
        chunk_index=0,
        content=content,
        char_count=len(content),
        chunking_strategy="test",
        metadata_json={},
    )
    session.add(chunk)
    session.flush()
    session.add(
        Embedding(
            chunk_id=chunk.id,
            provider_name=provider_name,
            model_name=model_name,
            vector=vector,
            dimensions=len(vector),
        )
    )
    session.commit()


def test_retrieval_filters_active_embedding_model(session) -> None:
    _add_embedding(session, "gemini", "gemini-embedding-001", "Gemini vector should be ignored", [1.0, 0.0, 0.0])
    _add_embedding(session, "local-sentence-transformers", "pkshatech/GLuCoSE-base-ja", "Local vector should be used", [0.0, 1.0, 0.0])

    rows = retrieve_chunks(
        session,
        [1.0, 0.0, 0.0],
        top_k=5,
        provider_name="local-sentence-transformers",
        model_name="pkshatech/GLuCoSE-base-ja",
        dimensions=3,
    )

    assert len(rows) == 1
    assert rows[0]["text"] == "Local vector should be used"
    assert rows[0]["embedding_model"] == "pkshatech/GLuCoSE-base-ja"
