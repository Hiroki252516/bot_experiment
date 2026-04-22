from __future__ import annotations

from app.core.config import get_settings


def chunk_text(text: str) -> list[str]:
    settings = get_settings()
    max_chars = settings.default_chunk_size
    overlap = settings.default_chunk_overlap
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(current) + len(paragraph) + 2 <= max_chars:
            current = f"{current}\n\n{paragraph}".strip()
            continue

        if current:
            chunks.append(current)
        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            chunk = paragraph[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap
        current = ""

    if current:
        chunks.append(current)
    return chunks

