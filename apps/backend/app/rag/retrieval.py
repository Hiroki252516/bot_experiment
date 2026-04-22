from __future__ import annotations

import math
from typing import Any

from sqlalchemy import Select, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Embedding, RagDocumentChunk


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in values) + "]"


def retrieve_chunks(
    session: Session,
    query_embedding: list[float],
    top_k: int,
) -> list[dict[str, Any]]:
    if not query_embedding:
        return []

    dialect = session.bind.dialect.name if session.bind else "sqlite"
    if dialect == "postgresql":
        vector_literal = _vector_literal(query_embedding)
        sql = text(
            """
            SELECT
              c.id AS chunk_id,
              c.document_id AS document_id,
              c.content AS text,
              e.model_name AS embedding_model,
              1 - (e.vector <=> CAST(:vector_literal AS vector)) AS score
            FROM embeddings e
            JOIN rag_document_chunks c ON c.id = e.chunk_id
            ORDER BY e.vector <=> CAST(:vector_literal AS vector)
            LIMIT :top_k
            """
        )
        rows = session.execute(sql, {"vector_literal": vector_literal, "top_k": top_k}).mappings().all()
        return [dict(row) for row in rows]

    query: Select = (
        select(Embedding, RagDocumentChunk)
        .join(RagDocumentChunk, RagDocumentChunk.id == Embedding.chunk_id)
    )
    rows = session.execute(query).all()
    scored: list[dict[str, Any]] = []
    for embedding, chunk in rows:
        score = _cosine_similarity(query_embedding, embedding.vector)
        scored.append(
            {
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "text": chunk.content,
                "embedding_model": embedding.model_name,
                "score": score,
            }
        )
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def has_embeddings(session: Session) -> bool:
    settings = get_settings()
    _ = settings
    return session.query(Embedding).first() is not None

