from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader


def parse_document(path: Path, mime_type: str) -> str:
    if mime_type == "application/pdf" or path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    return path.read_text(encoding="utf-8")

