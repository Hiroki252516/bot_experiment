from __future__ import annotations

import json
from typing import Any

import pytest

from app.core.config import Settings
from app.llm.providers import OllamaGenerationProvider, get_generation_provider


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeClient:
    def __init__(self, payload: dict[str, Any], calls: list[dict[str, Any]]) -> None:
        self.payload = payload
        self.calls = calls

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def post(self, url: str, json: dict[str, Any]) -> FakeResponse:
        self.calls.append({"url": url, "json": json})
        return FakeResponse(self.payload)


def _settings() -> Settings:
    return Settings(
        generation_provider="ollama",
        ollama_base_url="http://host.docker.internal:11434",
        ollama_model_generate="gemma4:e2b",
        upload_dir="/tmp/tutorbot-test/uploads",
        export_dir="/tmp/tutorbot-test/exports",
        hf_home="/tmp/tutorbot-test/model_cache/huggingface",
        transformers_cache="/tmp/tutorbot-test/model_cache/huggingface/transformers",
        sentence_transformers_home="/tmp/tutorbot-test/model_cache/sentence-transformers",
    )


def _patch_ollama_client(monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_httpx_client(*args, **kwargs) -> FakeClient:
        return FakeClient(payload, calls)

    monkeypatch.setattr("app.llm.providers.httpx.Client", fake_httpx_client)
    return calls


def _ollama_payload(content: dict[str, Any]) -> dict[str, Any]:
    return {"message": {"content": json.dumps(content)}}


def test_generation_provider_factory_returns_ollama() -> None:
    provider = get_generation_provider(_settings())

    assert isinstance(provider, OllamaGenerationProvider)
    assert provider.provider_name == "ollama"


def test_ollama_generate_candidates_parses_chat_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _ollama_payload(
        {
            "candidates": [
                {
                    "title": "候補1",
                    "style_tags": ["stepwise"],
                    "answer_text": "## 概要\n\n手順で説明します。\n\n## 要点\n\n- 最初のポイント\n- 次のポイント",
                    "rationale": "段階的説明を重視。",
                },
                {
                    "title": "候補2",
                    "style_tags": ["example-first"],
                    "answer_text": "## 概要\n\n例から説明します。\n\n1. 例を見る\n2. 手順を確認する",
                    "rationale": "具体例を重視。",
                },
                {
                    "title": "候補3",
                    "style_tags": ["concise"],
                    "answer_text": "## 概要\n\n短く説明します。\n\n- 要点だけ確認します",
                    "rationale": "簡潔さを重視。",
                },
            ]
        }
    )
    calls = _patch_ollama_client(monkeypatch, payload)
    provider = OllamaGenerationProvider(_settings())

    candidates, metadata = provider.generate_candidates(
        question="一次方程式とは何ですか？",
        retrievals=[{"text": "一次方程式は未知数の一次式を含む等式です。"}],
        skill_profile={},
        candidate_count=3,
        skills_enabled=True,
    )

    assert len(candidates.candidates) == 3
    assert candidates.candidates[0].title == "候補1"
    assert "## 概要" in candidates.candidates[0].answer_text
    assert metadata.provider_name == "ollama"
    assert metadata.model_name == "gemma4:e2b"
    assert calls[0]["url"] == "/api/chat"
    assert calls[0]["json"]["stream"] is False
    assert calls[0]["json"]["model"] == "gemma4:e2b"
    assert calls[0]["json"]["format"]["type"] == "object"
    assert "candidate.answer_text must be Markdown text" in calls[0]["json"]["messages"][0]["content"]


def test_ollama_candidate_count_mismatch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _ollama_payload(
        {
            "candidates": [
                {
                    "title": "候補1",
                    "style_tags": ["stepwise"],
                    "answer_text": "手順で説明します。",
                    "rationale": "段階的説明を重視。",
                }
            ]
        }
    )
    _patch_ollama_client(monkeypatch, payload)
    provider = OllamaGenerationProvider(_settings())

    with pytest.raises(RuntimeError, match="expected 3"):
        provider.generate_candidates(
            question="一次方程式とは何ですか？",
            retrievals=[],
            skill_profile={},
            candidate_count=3,
            skills_enabled=True,
        )


def test_ollama_extract_skill_delta_parses_chat_response(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = _ollama_payload(
        {
            "add_preferences": {
                "preferred_explanation_style": ["example-first"],
                "preferred_structure_pattern": ["example-then-steps"],
                "preferred_hint_level": "medium",
                "preferred_answer_length": "medium",
                "evidence_preference": "cite-retrieved-context",
            },
            "add_dislikes": ["answer-only"],
            "summary_rule": "具体例から始める説明を好む。",
        }
    )
    _patch_ollama_client(monkeypatch, payload)
    provider = OllamaGenerationProvider(_settings())

    delta, metadata = provider.extract_skill_delta(
        previous_skill={},
        chosen_candidate={"title": "候補2", "style_tags": ["example-first"]},
        rejected_candidates=[{"title": "候補1", "style_tags": ["concise"]}],
        user_comment="例が分かりやすい",
    )

    assert delta.summary_rule == "具体例から始める説明を好む。"
    assert delta.add_preferences.preferred_explanation_style == ["example-first"]
    assert delta.add_dislikes == ["answer-only"]
    assert metadata.provider_name == "ollama"


def test_ollama_invalid_json_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_ollama_client(monkeypatch, {"message": {"content": "not json"}})
    provider = OllamaGenerationProvider(_settings())

    with pytest.raises(RuntimeError, match="Ollama returned invalid JSON"):
        provider.generate_candidates(
            question="一次方程式とは何ですか？",
            retrievals=[],
            skill_profile={},
            candidate_count=3,
            skills_enabled=True,
        )
