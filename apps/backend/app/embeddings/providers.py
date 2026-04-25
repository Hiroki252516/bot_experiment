from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: list[list[float]]
    provider_name: str
    model_name: str
    dimensions: int
    device: str


class EmbeddingProvider(ABC):
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        raise NotImplementedError

    def _validate_dimensions(self, vectors: list[list[float]], model_name: str) -> int:
        if len(vectors) == 0:
            return self.settings.embedding_dimensions
        dimensions = len(vectors[0])
        if any(len(vector) != dimensions for vector in vectors):
            raise RuntimeError(f"Embedding model {model_name} returned inconsistent dimensions")
        if dimensions != self.settings.embedding_dimensions:
            raise RuntimeError(
                f"Embedding dimension mismatch for {model_name}: "
                f"expected EMBEDDING_DIMENSIONS={self.settings.embedding_dimensions}, got {dimensions}"
            )
        return dimensions


class MockEmbeddingProvider(EmbeddingProvider):
    provider_name = "mock"
    model_name = "mock-embedding"

    def _deterministic_vector(self, text: str) -> list[float]:
        dims = self.settings.embedding_dimensions
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [(digest[index % len(digest)] / 255.0) for index in range(dims)]

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        vectors = [self._deterministic_vector(text) for text in texts]
        dimensions = self._validate_dimensions(vectors, self.model_name)
        return EmbeddingResult(
            vectors=vectors,
            provider_name=self.provider_name,
            model_name=self.model_name,
            dimensions=dimensions,
            device="none",
        )


class GeminiEmbeddingProvider(EmbeddingProvider):
    provider_name = "gemini"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.gemini_api_base_url,
            headers={"x-goog-api-key": self.settings.gemini_api_key, "Content-Type": "application/json"},
            timeout=self.settings.request_timeout_seconds,
        )

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when EMBEDDING_PROVIDER=gemini")
        with self._client() as client:
            vectors: list[list[float]] = []
            for text in texts:
                body = {
                    "model": f"models/{self.settings.gemini_model_embed}",
                    "content": {"parts": [{"text": text}]},
                }
                response = client.post(f"/models/{self.settings.gemini_model_embed}:embedContent", json=body)
                response.raise_for_status()
                payload = response.json()
                vectors.append(payload["embedding"]["values"])
        dimensions = self._validate_dimensions(vectors, self.settings.gemini_model_embed)
        return EmbeddingResult(
            vectors=vectors,
            provider_name=self.provider_name,
            model_name=self.settings.gemini_model_embed,
            dimensions=dimensions,
            device="remote",
        )


def resolve_local_embed_device(requested_device: str, torch_module: Any) -> str:
    requested = requested_device.lower()
    mps_available = bool(
        getattr(getattr(torch_module, "backends", None), "mps", None)
        and torch_module.backends.mps.is_available()
    )
    if requested == "auto":
        return "mps" if mps_available else "cpu"
    if requested == "mps" and not mps_available:
        raise RuntimeError("LOCAL_EMBED_DEVICE=mps was requested, but PyTorch MPS is not available")
    if requested in {"cpu", "mps"}:
        return requested
    raise ValueError(f"Unsupported LOCAL_EMBED_DEVICE: {requested_device}")


class LocalSentenceTransformersEmbeddingProvider(EmbeddingProvider):
    provider_name = "local-sentence-transformers"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self._model: Any | None = None
        self._device: str | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers and torch are required when "
                "EMBEDDING_PROVIDER=local-sentence-transformers"
            ) from exc
        self._device = resolve_local_embed_device(self.settings.local_embed_device, torch)
        self._model = SentenceTransformer(
            self.settings.local_embed_model,
            device=self._device,
            cache_folder=str(self.settings.sentence_transformers_home),
        )
        return self._model

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                provider_name=self.provider_name,
                model_name=self.settings.local_embed_model,
                dimensions=self.settings.embedding_dimensions,
                device=self._device or self.settings.local_embed_device,
            )
        model = self._load_model()
        encoded = model.encode(
            texts,
            batch_size=self.settings.local_embed_batch_size,
            normalize_embeddings=self.settings.local_embed_normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = encoded.tolist()
        dimensions = self._validate_dimensions(vectors, self.settings.local_embed_model)
        return EmbeddingResult(
            vectors=vectors,
            provider_name=self.provider_name,
            model_name=self.settings.local_embed_model,
            dimensions=dimensions,
            device=self._device or "cpu",
        )


class LocalHttpEmbeddingProvider(EmbeddingProvider):
    provider_name = "local-http"

    def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[],
                provider_name=self.provider_name,
                model_name=self.settings.local_embed_model,
                dimensions=self.settings.embedding_dimensions,
                device="remote",
            )
        body = {
            "texts": texts,
            "model": self.settings.local_embed_model,
            "normalize": self.settings.local_embed_normalize,
        }
        with httpx.Client(timeout=self.settings.request_timeout_seconds) as client:
            response = client.post(f"{self.settings.local_embed_http_url.rstrip('/')}/embed", json=body)
            response.raise_for_status()
            payload = response.json()
        vectors = payload["vectors"]
        model_name = payload.get("model_name") or self.settings.local_embed_model
        dimensions = self._validate_dimensions(vectors, model_name)
        return EmbeddingResult(
            vectors=vectors,
            provider_name=self.provider_name,
            model_name=model_name,
            dimensions=dimensions,
            device=payload.get("device", "remote"),
        )


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    active_settings = settings or get_settings()
    provider_name = active_settings.embedding_provider
    if provider_name == "mock":
        return MockEmbeddingProvider(active_settings)
    if provider_name == "gemini":
        return GeminiEmbeddingProvider(active_settings)
    if provider_name == "local-sentence-transformers":
        return LocalSentenceTransformersEmbeddingProvider(active_settings)
    if provider_name == "local-http":
        return LocalHttpEmbeddingProvider(active_settings)
    raise ValueError(f"Unsupported embedding provider: {provider_name}")
