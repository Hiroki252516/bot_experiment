from __future__ import annotations

from app.core.config import get_settings
from app.embeddings.providers import get_embedding_provider


def main() -> None:
    settings = get_settings()
    provider = get_embedding_provider(settings)
    result = provider.embed_texts(["モデルキャッシュ確認用の短い日本語テキストです。"])
    print(
        "Prefetched embedding model: "
        f"provider={result.provider_name} model={result.model_name} "
        f"dimensions={result.dimensions} device={result.device}"
    )


if __name__ == "__main__":
    main()
