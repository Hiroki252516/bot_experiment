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


def _add_embedding(
    session,
    provider_name: str,
    model_name: str,
    content: str,
    vector: list[float],
    filename: str | None = None,
    source_type: str = "test",
) -> RagDocument:
    document = RagDocument(
        filename=filename or f"{model_name}.md",
        mime_type="text/markdown",
        source_type=source_type,
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
    return document


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


def test_retrieval_filters_selected_documents(session) -> None:
    _add_embedding(
        session,
        "local-sentence-transformers",
        "pkshatech/GLuCoSE-base-ja",
        "Quadratic equations test PDF.",
        [1.0, 0.0, 0.0],
        filename="algebra.pdf",
    )
    programming_document = _add_embedding(
        session,
        "local-sentence-transformers",
        "pkshatech/GLuCoSE-base-ja",
        "第1回課題: 01というフォルダを作成し、HTMLファイルを提出する。拡張子は .html。",
        [0.0, 1.0, 0.0],
        filename="基礎プログラミング演習1.pdf",
    )

    rows = retrieve_chunks(
        session,
        [1.0, 0.0, 0.0],
        top_k=5,
        provider_name="local-sentence-transformers",
        model_name="pkshatech/GLuCoSE-base-ja",
        dimensions=3,
        document_ids=[programming_document.id],
    )

    assert len(rows) == 1
    assert rows[0]["document_id"] == programming_document.id
    assert rows[0]["filename"] == "基礎プログラミング演習1.pdf"
    assert "HTMLファイル" in rows[0]["text"]


def test_retrieval_excludes_seed_documents_by_default(session) -> None:
    _add_embedding(
        session,
        "local-sentence-transformers",
        "pkshatech/GLuCoSE-base-ja",
        "Seed algebra should be ignored unless selected.",
        [1.0, 0.0, 0.0],
        filename="seed-algebra.md",
        source_type="seed",
    )
    uploaded_document = _add_embedding(
        session,
        "local-sentence-transformers",
        "pkshatech/GLuCoSE-base-ja",
        "Uploaded programming material should remain searchable.",
        [0.0, 1.0, 0.0],
        filename="uploaded.pdf",
        source_type="upload",
    )

    rows = retrieve_chunks(
        session,
        [1.0, 0.0, 0.0],
        top_k=5,
        provider_name="local-sentence-transformers",
        model_name="pkshatech/GLuCoSE-base-ja",
        dimensions=3,
    )

    assert len(rows) == 1
    assert rows[0]["document_id"] == uploaded_document.id


def test_lexical_fallback_finds_japanese_assignment_terms_when_vector_score_is_low(session) -> None:
    programming_document = _add_embedding(
        session,
        "local-sentence-transformers",
        "pkshatech/GLuCoSE-base-ja",
        "第1回課題: 01というフォルダを作成し、エディタで作成したHTMLファイルを提出する。内容は何でもよい。拡張子は .html。",
        [0.0, 1.0, 0.0],
        filename="基礎プログラミング演習1.pdf",
        source_type="upload",
    )

    rows = retrieve_chunks(
        session,
        [1.0, 0.0, 0.0],
        top_k=5,
        provider_name="local-sentence-transformers",
        model_name="pkshatech/GLuCoSE-base-ja",
        dimensions=3,
        document_ids=[programming_document.id],
        min_score=0.25,
        lexical_fallback_question="基礎プログラミング演習の第一回課題の内容を教えて",
    )

    assert len(rows) == 1
    assert rows[0]["score"] >= 0.25
    assert "01というフォルダ" in rows[0]["text"]
    assert "HTMLファイル" in rows[0]["text"]
    assert ".html" in rows[0]["text"]
