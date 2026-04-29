from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy import Select, bindparam, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Embedding, RagDocument, RagDocumentChunk


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


POSTGRES_RETRIEVAL_SQL = """
SELECT
  c.id AS chunk_id,
  c.document_id AS document_id,
  d.filename AS filename,
  c.chunk_index AS chunk_index,
  c.content AS text,
  e.model_name AS embedding_model,
  1 - (e.vector <=> CAST(:vector_literal AS vector)) AS score
FROM embeddings e
JOIN rag_document_chunks c ON c.id = e.chunk_id
JOIN rag_documents d ON d.id = c.document_id
WHERE (CAST(:provider_name AS text) IS NULL OR e.provider_name = CAST(:provider_name AS text))
  AND (CAST(:model_name AS text) IS NULL OR e.model_name = CAST(:model_name AS text))
  AND (CAST(:dimensions AS integer) IS NULL OR e.dimensions = CAST(:dimensions AS integer))
  {document_filter}
  {source_filter}
ORDER BY e.vector <=> CAST(:vector_literal AS vector)
LIMIT :top_k
"""

POSTGRES_LEXICAL_RETRIEVAL_SQL = """
SELECT
  c.id AS chunk_id,
  c.document_id AS document_id,
  d.filename AS filename,
  c.chunk_index AS chunk_index,
  c.content AS text,
  e.model_name AS embedding_model,
  0.45 + (0.1 * ({score_expression})) AS score
FROM embeddings e
JOIN rag_document_chunks c ON c.id = e.chunk_id
JOIN rag_documents d ON d.id = c.document_id
WHERE (CAST(:provider_name AS text) IS NULL OR e.provider_name = CAST(:provider_name AS text))
  AND (CAST(:model_name AS text) IS NULL OR e.model_name = CAST(:model_name AS text))
  AND (CAST(:dimensions AS integer) IS NULL OR e.dimensions = CAST(:dimensions AS integer))
  {document_filter}
  {source_filter}
  AND ({lexical_filter})
ORDER BY score DESC, c.chunk_index ASC
LIMIT :top_k
"""


def _normalize_document_ids(document_ids: list[str] | None) -> list[str]:
    return [document_id for document_id in (document_ids or []) if document_id]


def _extract_lexical_terms(question: str) -> list[str]:
    normalized = question.lower()
    terms: list[str] = []

    def add(term: str) -> None:
        value = term.strip().lower()
        if value and value not in terms:
            terms.append(value)

    if "第一回" in question or "第1回" in question or "第１回" in question or "1回" in question:
        for term in ["第一回", "第1回", "第１回", "1回", "１回", "01"]:
            add(term)
    if "課題" in question:
        add("課題")
    if "プログラミング" in question:
        for term in ["基礎プログラミング演習", "プログラミング", "演習"]:
            add(term)
    if "html" in normalized:
        for term in ["html", ".html", "htmlファイル"]:
            add(term)

    for token in re.findall(r"[a-zA-Z0-9_.+-]+|[一-龯ぁ-んァ-ヶー]{2,}", question):
        if token in {"内容", "教えて", "ください", "とは", "について"}:
            continue
        add(token)
    return terms[:12]


def _merge_ranked_rows(vector_rows: list[dict[str, Any]], lexical_rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    by_chunk_id: dict[str, dict[str, Any]] = {}
    for row in vector_rows + lexical_rows:
        existing = by_chunk_id.get(row["chunk_id"])
        if existing is None or float(row["score"]) > float(existing["score"]):
            by_chunk_id[row["chunk_id"]] = row
    rows = list(by_chunk_id.values())
    rows.sort(key=lambda item: float(item["score"]), reverse=True)
    return rows[:top_k]


def _best_score(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return max(float(row["score"]) for row in rows)


def _row_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["score"] = float(item["score"])
    item["chunk_index"] = int(item["chunk_index"])
    return item


def _source_filter(document_ids: list[str]) -> str:
    return "" if document_ids else "AND d.source_type != 'seed'"


def _document_filter(document_ids: list[str]) -> str:
    return "AND c.document_id IN :document_ids" if document_ids else ""


def retrieve_chunks(
    session: Session,
    query_embedding: list[float],
    top_k: int,
    provider_name: str | None = None,
    model_name: str | None = None,
    dimensions: int | None = None,
    document_ids: list[str] | None = None,
    min_score: float | None = None,
    lexical_fallback_question: str | None = None,
) -> list[dict[str, Any]]:
    if not query_embedding:
        return []

    normalized_document_ids = _normalize_document_ids(document_ids)
    resolved_min_score = get_settings().min_retrieval_score if min_score is None else min_score
    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        vector_literal = _vector_literal(query_embedding)
        sql = text(
            POSTGRES_RETRIEVAL_SQL.format(
                document_filter=_document_filter(normalized_document_ids),
                source_filter=_source_filter(normalized_document_ids),
            )
        )
        if normalized_document_ids:
            sql = sql.bindparams(bindparam("document_ids", expanding=True))
        params: dict[str, Any] = {
            "vector_literal": vector_literal,
            "top_k": top_k,
            "provider_name": provider_name,
            "model_name": model_name,
            "dimensions": dimensions,
        }
        if normalized_document_ids:
            params["document_ids"] = normalized_document_ids
        rows = session.execute(sql, params).mappings().all()
        vector_rows = [_row_dict(row) for row in rows]
        if _best_score(vector_rows) >= resolved_min_score or not lexical_fallback_question:
            return vector_rows
        lexical_rows = _retrieve_lexical_chunks_postgres(
            session=session,
            top_k=top_k,
            question=lexical_fallback_question,
            provider_name=provider_name,
            model_name=model_name,
            dimensions=dimensions,
            document_ids=normalized_document_ids,
        )
        return _merge_ranked_rows(vector_rows, lexical_rows, top_k)

    vector_rows = _retrieve_vector_chunks_sqlite(
        session=session,
        query_embedding=query_embedding,
        provider_name=provider_name,
        model_name=model_name,
        dimensions=dimensions,
        document_ids=normalized_document_ids,
        top_k=top_k,
    )
    if _best_score(vector_rows) >= resolved_min_score or not lexical_fallback_question:
        return vector_rows
    lexical_rows = _retrieve_lexical_chunks_sqlite(
        session=session,
        question=lexical_fallback_question,
        provider_name=provider_name,
        model_name=model_name,
        dimensions=dimensions,
        document_ids=normalized_document_ids,
        top_k=top_k,
    )
    return _merge_ranked_rows(vector_rows, lexical_rows, top_k)


def _base_sqlite_query() -> Select:
    query: Select = (
        select(Embedding, RagDocumentChunk, RagDocument)
        .join(RagDocumentChunk, RagDocumentChunk.id == Embedding.chunk_id)
        .join(RagDocument, RagDocument.id == RagDocumentChunk.document_id)
    )
    return query


def _apply_sqlite_filters(
    query: Select,
    provider_name: str | None,
    model_name: str | None,
    dimensions: int | None,
    document_ids: list[str],
) -> Select:
    if provider_name is not None:
        query = query.where(Embedding.provider_name == provider_name)
    if model_name is not None:
        query = query.where(Embedding.model_name == model_name)
    if dimensions is not None:
        query = query.where(Embedding.dimensions == dimensions)
    if document_ids:
        query = query.where(RagDocumentChunk.document_id.in_(document_ids))
    else:
        query = query.where(RagDocument.source_type != "seed")
    return query


def _retrieve_vector_chunks_sqlite(
    session: Session,
    query_embedding: list[float],
    provider_name: str | None,
    model_name: str | None,
    dimensions: int | None,
    document_ids: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    query = _apply_sqlite_filters(_base_sqlite_query(), provider_name, model_name, dimensions, document_ids)
    rows = session.execute(query).all()
    scored: list[dict[str, Any]] = []
    for embedding, chunk, document in rows:
        score = _cosine_similarity(query_embedding, embedding.vector)
        scored.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": document.filename,
                "chunk_index": chunk.chunk_index,
                "text": chunk.content,
                "embedding_model": embedding.model_name,
                "score": score,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def _retrieve_lexical_chunks_sqlite(
    session: Session,
    question: str,
    provider_name: str | None,
    model_name: str | None,
    dimensions: int | None,
    document_ids: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    terms = _extract_lexical_terms(question)
    if not terms:
        return []
    query = _apply_sqlite_filters(_base_sqlite_query(), provider_name, model_name, dimensions, document_ids)
    rows = session.execute(query).all()
    scored: list[dict[str, Any]] = []
    for embedding, chunk, document in rows:
        haystack = f"{document.filename}\n{chunk.content}".lower()
        match_count = sum(1 for term in terms if term in haystack)
        if match_count == 0:
            continue
        score = min(1.0, 0.45 + (0.1 * match_count))
        scored.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "filename": document.filename,
                "chunk_index": chunk.chunk_index,
                "text": chunk.content,
                "embedding_model": embedding.model_name,
                "score": score,
            }
        )
    scored.sort(key=lambda item: (item["score"], -item["chunk_index"]), reverse=True)
    return scored[:top_k]


def _retrieve_lexical_chunks_postgres(
    session: Session,
    top_k: int,
    question: str,
    provider_name: str | None,
    model_name: str | None,
    dimensions: int | None,
    document_ids: list[str],
) -> list[dict[str, Any]]:
    terms = _extract_lexical_terms(question)
    if not terms:
        return []
    lexical_filter_parts = []
    score_parts = []
    params: dict[str, Any] = {
        "top_k": top_k,
        "provider_name": provider_name,
        "model_name": model_name,
        "dimensions": dimensions,
    }
    if document_ids:
        params["document_ids"] = document_ids
    for index, term in enumerate(terms):
        param_name = f"term_{index}"
        lexical_filter_parts.append(f"(lower(c.content) LIKE :{param_name} OR lower(d.filename) LIKE :{param_name})")
        score_parts.append(f"CASE WHEN lower(c.content) LIKE :{param_name} OR lower(d.filename) LIKE :{param_name} THEN 1 ELSE 0 END")
        params[param_name] = f"%{term}%"
    sql = text(
        POSTGRES_LEXICAL_RETRIEVAL_SQL.format(
            score_expression=" + ".join(score_parts),
            lexical_filter=" OR ".join(lexical_filter_parts),
            document_filter=_document_filter(document_ids),
            source_filter=_source_filter(document_ids),
        )
    )
    if document_ids:
        sql = sql.bindparams(bindparam("document_ids", expanding=True))
    rows = session.execute(sql, params).mappings().all()
    return [_row_dict(row) for row in rows]


def has_embeddings(session: Session) -> bool:
    settings = get_settings()
    _ = settings
    return session.query(Embedding).first() is not None
