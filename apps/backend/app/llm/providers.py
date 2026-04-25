from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.schemas.llm import GeneratedCandidateSet, ProviderMetadata, SkillDelta


class GenerationProvider(ABC):
    provider_name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def generate_candidates(
        self,
        question: str,
        retrievals: list[dict],
        skill_profile: dict,
        candidate_count: int,
        skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        raise NotImplementedError

    @abstractmethod
    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        raise NotImplementedError


class MockGenerationProvider(GenerationProvider):
    provider_name = "mock"

    def generate_candidates(
        self,
        question: str,
        retrievals: list[dict],
        skill_profile: dict,
        candidate_count: int,
        skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        styles = [
            ("Hint-first", ["hint-first", "stepwise"]),
            ("Worked example", ["example-first", "concrete"]),
            ("Concise summary", ["short", "direct"]),
            ("Socratic coach", ["socratic", "guided"]),
            ("Evidence-led", ["context-citing", "structured"]),
        ]
        cited_context = retrievals[0]["text"][:180] if retrievals else "No retrieved context available."
        notes = ", ".join(skill_profile.get("notes", [])) if skills_enabled else "skills disabled"
        candidates = []
        for rank in range(candidate_count):
            title, style_tags = styles[rank]
            answer_text = (
                f"{title}: For the question '{question}', start by grounding the learner in the key idea.\n\n"
                f"Retrieved context: {cited_context}\n\n"
                f"Adaptation note: {notes}\n\n"
                f"Step {rank + 1}: Explain the concept in a learner-facing way and end with a short self-check."
            )
            candidates.append(
                {
                    "title": title,
                    "style_tags": style_tags,
                    "answer_text": answer_text,
                    "rationale": f"Mock candidate {rank + 1} emphasizing {'/'.join(style_tags)}.",
                }
            )
        return (
            GeneratedCandidateSet.model_validate({"candidates": candidates}),
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock"},
            ),
        )

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        disliked = []
        rejected_tags = {tag for candidate in rejected_candidates for tag in candidate.get("style_tags", [])}
        for tag in sorted(rejected_tags):
            if "short" in tag or "direct" in tag:
                disliked.append("answer-only")
                break
        delta = SkillDelta.model_validate(
            {
                "add_preferences": {
                    "preferred_explanation_style": chosen_candidate.get("style_tags", [])[:1],
                    "preferred_structure_pattern": ["example-then-steps-then-check"]
                    if "example-first" in chosen_candidate.get("style_tags", [])
                    else ["steps-then-check"],
                    "preferred_hint_level": "medium",
                    "preferred_answer_length": "medium",
                    "evidence_preference": "cite-retrieved-context",
                },
                "add_dislikes": disliked,
                "summary_rule": user_comment
                or f"Prefer responses similar to {chosen_candidate.get('title', 'selected candidate')}.",
            }
        )
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name="mock-model",
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response={"mode": "mock"},
            ),
        )


class GeminiGenerationProvider(GenerationProvider):
    provider_name = "gemini"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.gemini_api_base_url,
            headers={"x-goog-api-key": self.settings.gemini_api_key, "Content-Type": "application/json"},
            timeout=self.settings.request_timeout_seconds,
        )

    def _generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required when GENERATION_PROVIDER=gemini")
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": self.settings.generation_temperature,
                "topP": self.settings.generation_top_p,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        }
        with self._client() as client:
            response = client.post(f"/models/{self.settings.gemini_model_generate}:generateContent", json=body)
            response.raise_for_status()
            payload = response.json()
        text_parts = payload["candidates"][0]["content"]["parts"]
        text_value = "".join(part.get("text", "") for part in text_parts)
        return {"parsed": json.loads(text_value), "raw": payload}

    def generate_candidates(
        self,
        question: str,
        retrievals: list[dict],
        skill_profile: dict,
        candidate_count: int,
        skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "candidates": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "title": {"type": "STRING"},
                            "style_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                            "answer_text": {"type": "STRING"},
                            "rationale": {"type": "STRING"},
                        },
                        "required": ["title", "style_tags", "answer_text", "rationale"],
                    },
                }
            },
            "required": ["candidates"],
        }
        prompt = (
            "You are generating tutoring answer candidates for a research system.\n"
            f"Question: {question}\n"
            f"Candidate count: {candidate_count}\n"
            f"Skills enabled: {skills_enabled}\n"
            f"Current skill profile JSON: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"Retrieved contexts JSON: {json.dumps(retrievals, ensure_ascii=False)}\n"
            "Return exactly the requested number of distinct learner-facing candidates."
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                result = self._generate_json(prompt, schema)
                parsed = GeneratedCandidateSet.model_validate(result["parsed"])
                if len(parsed.candidates) != candidate_count:
                    raise ValueError("candidate count mismatch")
                metadata = ProviderMetadata(
                    provider_name=self.provider_name,
                    model_name=self.settings.gemini_model_generate,
                    temperature=self.settings.generation_temperature,
                    top_p=self.settings.generation_top_p,
                    prompt_version=self.settings.prompt_version,
                    raw_response=result["raw"],
                )
                return parsed, metadata
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Gemini candidate generation failed: {last_error}") from last_error

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        schema = {
            "type": "OBJECT",
            "properties": {
                "add_preferences": {
                    "type": "OBJECT",
                    "properties": {
                        "preferred_explanation_style": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "preferred_structure_pattern": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "preferred_hint_level": {"type": "STRING"},
                        "preferred_answer_length": {"type": "STRING"},
                        "evidence_preference": {"type": "STRING"},
                    },
                },
                "add_dislikes": {"type": "ARRAY", "items": {"type": "STRING"}},
                "summary_rule": {"type": "STRING"},
            },
            "required": ["add_preferences", "add_dislikes", "summary_rule"],
        }
        prompt = (
            "You are extracting reusable learner preference rules.\n"
            f"Previous skill profile JSON: {json.dumps(previous_skill, ensure_ascii=False)}\n"
            f"Chosen candidate JSON: {json.dumps(chosen_candidate, ensure_ascii=False)}\n"
            f"Rejected candidates JSON: {json.dumps(rejected_candidates, ensure_ascii=False)}\n"
            f"User comment: {user_comment or ''}\n"
            "Return normalized preference deltas only."
        )
        result = self._generate_json(prompt, schema)
        return (
            SkillDelta.model_validate(result["parsed"]),
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.gemini_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )


class OllamaGenerationProvider(GenerationProvider):
    provider_name = "ollama"

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.ollama_base_url,
            headers={"Content-Type": "application/json"},
            timeout=self.settings.ollama_request_timeout_seconds,
        )

    def _generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": self.settings.ollama_model_generate,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": schema,
            "options": {
                "temperature": self.settings.generation_temperature,
                "top_p": self.settings.generation_top_p,
            },
        }
        with self._client() as client:
            response = client.post("/api/chat", json=body)
            response.raise_for_status()
            payload = response.json()

        try:
            content = payload["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError("Ollama response missing message.content") from exc
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned invalid JSON: {exc.msg}") from exc
        return {"parsed": parsed, "raw": payload}

    def generate_candidates(
        self,
        question: str,
        retrievals: list[dict],
        skill_profile: dict,
        candidate_count: int,
        skills_enabled: bool,
    ) -> tuple[GeneratedCandidateSet, ProviderMetadata]:
        schema = {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "minItems": candidate_count,
                    "maxItems": candidate_count,
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "style_tags": {"type": "array", "items": {"type": "string"}},
                            "answer_text": {"type": "string"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["title", "style_tags", "answer_text", "rationale"],
                    },
                }
            },
            "required": ["candidates"],
        }
        prompt = (
            "You are generating tutoring answer candidates for a research system.\n"
            "Return only JSON that matches the provided schema. Do not include markdown or commentary.\n"
            f"Question: {question}\n"
            f"Candidate count: {candidate_count}\n"
            f"Skills enabled: {skills_enabled}\n"
            f"Current skill profile JSON: {json.dumps(skill_profile, ensure_ascii=False)}\n"
            f"Retrieved contexts JSON: {json.dumps(retrievals, ensure_ascii=False)}\n"
            "Return exactly the requested number of distinct learner-facing candidates."
        )
        try:
            result = self._generate_json(prompt, schema)
            parsed = GeneratedCandidateSet.model_validate(result["parsed"])
            if len(parsed.candidates) != candidate_count:
                raise RuntimeError(
                    f"Ollama candidate generation returned {len(parsed.candidates)} candidates; "
                    f"expected {candidate_count}"
                )
            metadata = ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            )
            return parsed, metadata
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Ollama candidate generation failed: {exc}") from exc

    def extract_skill_delta(
        self,
        previous_skill: dict,
        chosen_candidate: dict,
        rejected_candidates: list[dict],
        user_comment: str | None,
    ) -> tuple[SkillDelta, ProviderMetadata]:
        schema = {
            "type": "object",
            "properties": {
                "add_preferences": {
                    "type": "object",
                    "properties": {
                        "preferred_explanation_style": {"type": "array", "items": {"type": "string"}},
                        "preferred_structure_pattern": {"type": "array", "items": {"type": "string"}},
                        "preferred_hint_level": {"type": ["string", "null"]},
                        "preferred_answer_length": {"type": ["string", "null"]},
                        "evidence_preference": {"type": ["string", "null"]},
                    },
                    "required": [
                        "preferred_explanation_style",
                        "preferred_structure_pattern",
                        "preferred_hint_level",
                        "preferred_answer_length",
                        "evidence_preference",
                    ],
                },
                "add_dislikes": {"type": "array", "items": {"type": "string"}},
                "summary_rule": {"type": "string"},
            },
            "required": ["add_preferences", "add_dislikes", "summary_rule"],
        }
        prompt = (
            "You are extracting reusable learner preference rules.\n"
            "Return only JSON that matches the provided schema. Do not include markdown or commentary.\n"
            f"Previous skill profile JSON: {json.dumps(previous_skill, ensure_ascii=False)}\n"
            f"Chosen candidate JSON: {json.dumps(chosen_candidate, ensure_ascii=False)}\n"
            f"Rejected candidates JSON: {json.dumps(rejected_candidates, ensure_ascii=False)}\n"
            f"User comment: {user_comment or ''}\n"
            "Return normalized preference deltas only."
        )
        try:
            result = self._generate_json(prompt, schema)
            delta = SkillDelta.model_validate(result["parsed"])
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Ollama skill delta extraction failed: {exc}") from exc
        return (
            delta,
            ProviderMetadata(
                provider_name=self.provider_name,
                model_name=self.settings.ollama_model_generate,
                temperature=self.settings.generation_temperature,
                top_p=self.settings.generation_top_p,
                prompt_version=self.settings.prompt_version,
                raw_response=result["raw"],
            ),
        )


def get_generation_provider(settings: Settings | None = None) -> GenerationProvider:
    active_settings = settings or get_settings()
    provider_name = active_settings.active_generation_provider
    if provider_name == "mock":
        return MockGenerationProvider(active_settings)
    if provider_name == "gemini":
        return GeminiGenerationProvider(active_settings)
    if provider_name == "ollama":
        return OllamaGenerationProvider(active_settings)
    raise ValueError(f"Unsupported generation provider: {provider_name}")


def get_generation_model_name(settings: Settings, provider_name: str | None = None) -> str:
    active_provider = provider_name or settings.active_generation_provider
    if active_provider == "gemini":
        return settings.gemini_model_generate
    if active_provider == "ollama":
        return settings.ollama_model_generate
    if active_provider == "mock":
        return "mock-model"
    return "unknown"


LLMProvider = GenerationProvider
MockProvider = MockGenerationProvider
GeminiProvider = GeminiGenerationProvider
OllamaProvider = OllamaGenerationProvider
get_provider = get_generation_provider
