from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.embeddings.providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    get_embedding_provider,
    resolve_local_embed_device,
)
from app.llm.providers import get_generation_provider


class ValidationOnlyEmbeddingProvider(EmbeddingProvider):
    provider_name = "validation-only"

    def embed_texts(self, texts: list[str]):
        raise NotImplementedError


def test_generation_and_embedding_provider_factories_are_independent() -> None:
    settings = Settings(
        generation_provider="gemini",
        embedding_provider="mock",
        gemini_api_key="test-key",
        upload_dir="/tmp/tutorbot-test/uploads",
        export_dir="/tmp/tutorbot-test/exports",
        hf_home="/tmp/tutorbot-test/model_cache/huggingface",
        transformers_cache="/tmp/tutorbot-test/model_cache/huggingface/transformers",
        sentence_transformers_home="/tmp/tutorbot-test/model_cache/sentence-transformers",
    )

    generation_provider = get_generation_provider(settings)
    embedding_provider = get_embedding_provider(settings)

    assert generation_provider.provider_name == "gemini"
    assert embedding_provider.provider_name == "mock"


def test_mock_embedding_provider_uses_configured_dimensions() -> None:
    settings = Settings(
        embedding_provider="mock",
        embedding_dimensions=12,
        upload_dir="/tmp/tutorbot-test/uploads",
        export_dir="/tmp/tutorbot-test/exports",
        hf_home="/tmp/tutorbot-test/model_cache/huggingface",
        transformers_cache="/tmp/tutorbot-test/model_cache/huggingface/transformers",
        sentence_transformers_home="/tmp/tutorbot-test/model_cache/sentence-transformers",
    )

    result = MockEmbeddingProvider(settings).embed_texts(["日本語の教材"])

    assert result.provider_name == "mock"
    assert result.model_name == "mock-embedding"
    assert result.dimensions == 12
    assert len(result.vectors[0]) == 12


def test_embedding_dimension_mismatch_fails_explicitly() -> None:
    settings = Settings(
        embedding_dimensions=4,
        upload_dir="/tmp/tutorbot-test/uploads",
        export_dir="/tmp/tutorbot-test/exports",
        hf_home="/tmp/tutorbot-test/model_cache/huggingface",
        transformers_cache="/tmp/tutorbot-test/model_cache/huggingface/transformers",
        sentence_transformers_home="/tmp/tutorbot-test/model_cache/sentence-transformers",
    )

    provider = ValidationOnlyEmbeddingProvider(settings)

    with pytest.raises(RuntimeError, match="Embedding dimension mismatch"):
        provider._validate_dimensions([[0.1, 0.2, 0.3]], "test-model")


def test_local_embed_device_auto_falls_back_to_cpu_without_mps() -> None:
    torch_module = SimpleNamespace(backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)))

    assert resolve_local_embed_device("auto", torch_module) == "cpu"


def test_local_embed_device_mps_requires_mps_available() -> None:
    torch_module = SimpleNamespace(backends=SimpleNamespace(mps=SimpleNamespace(is_available=lambda: False)))

    with pytest.raises(RuntimeError, match="MPS is not available"):
        resolve_local_embed_device("mps", torch_module)
