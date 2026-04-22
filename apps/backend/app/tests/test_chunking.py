from app.rag.chunking import chunk_text


def test_chunk_text_preserves_content() -> None:
    text = "\n\n".join([f"Paragraph {index} " + ("x" * 100) for index in range(12)])
    chunks = chunk_text(text)

    assert len(chunks) >= 2
    assert "Paragraph 0" in chunks[0]
    assert any("Paragraph 11" in chunk for chunk in chunks)

