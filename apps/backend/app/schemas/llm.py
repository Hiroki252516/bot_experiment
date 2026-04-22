from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GeneratedCandidate(BaseModel):
    title: str
    style_tags: list[str]
    answer_text: str
    rationale: str


class GeneratedCandidateSet(BaseModel):
    candidates: list[GeneratedCandidate]


class SkillDeltaPreferences(BaseModel):
    preferred_explanation_style: list[str] = Field(default_factory=list)
    preferred_structure_pattern: list[str] = Field(default_factory=list)
    preferred_hint_level: str | None = None
    preferred_answer_length: str | None = None
    evidence_preference: str | None = None


class SkillDelta(BaseModel):
    add_preferences: SkillDeltaPreferences = Field(default_factory=SkillDeltaPreferences)
    add_dislikes: list[str] = Field(default_factory=list)
    summary_rule: str


class ProviderMetadata(BaseModel):
    provider_name: str
    model_name: str
    temperature: float
    top_p: float
    prompt_version: str
    raw_response: dict[str, Any] | None = None

