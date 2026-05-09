from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SourceUnit(BaseModel):
    unit_index: int
    text: str
    source_page: int | None = None
    source_span: str | None = None


class SourceMapItem(BaseModel):
    excerpt: str
    page: int | None = None
    source_span: str | None = None


class KeyConcept(BaseModel):
    name: str
    explanation: str
    source_pages: list[int] = Field(default_factory=list)


class DefinitionItem(BaseModel):
    term: str
    definition: str
    source_pages: list[int] = Field(default_factory=list)


class FactItem(BaseModel):
    statement: str
    source_pages: list[int] = Field(default_factory=list)


class ProcedureItem(BaseModel):
    title: str
    steps: list[str] = Field(default_factory=list)
    source_pages: list[int] = Field(default_factory=list)


class ExampleItem(BaseModel):
    title: str
    content: str
    source_pages: list[int] = Field(default_factory=list)


class FormulaItem(BaseModel):
    name: str
    expression: str
    explanation: str = ""
    source_pages: list[int] = Field(default_factory=list)


class DocumentSkillProfile(BaseModel):
    schema_version: str = "document-skill-v1"
    document_title: str = ""
    summary: str = ""
    learning_objectives: list[str] = Field(default_factory=list)
    key_concepts: list[KeyConcept] = Field(default_factory=list)
    definitions: list[DefinitionItem] = Field(default_factory=list)
    facts: list[FactItem] = Field(default_factory=list)
    procedures: list[ProcedureItem] = Field(default_factory=list)
    examples: list[ExampleItem] = Field(default_factory=list)
    formulas: list[FormulaItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    common_misconceptions: list[str] = Field(default_factory=list)
    answering_guidelines: list[str] = Field(default_factory=list)
    source_map: list[SourceMapItem] = Field(default_factory=list)


class DocumentSkillDelta(DocumentSkillProfile):
    pass


class DocumentSkillContextEntry(BaseModel):
    entry_id: str
    entry_type: str
    title: str
    content: str
    source_page: int | None = None
    source_span: str | None = None
    included_order: int


class DocumentSkillContextDocument(BaseModel):
    document_id: str
    filename: str
    document_skill_revision_id: str
    entries: list[DocumentSkillContextEntry]


class DocumentSkillResponse(BaseModel):
    document_id: str
    filename: str
    document_skill_id: str | None = None
    active_revision_id: str | None = None
    status: str | None = None
    revision_number: int | None = None
    profile_json: dict[str, Any] | None = None
    entries_count: int = 0
    updated_at: datetime | None = None


class DocumentSkillRevisionResponse(BaseModel):
    revision_id: str
    revision_number: int
    summary: str
    extraction_model_name: str
    prompt_version: str
    source_digest: str | None
    update_reason: str
    created_at: datetime


class DocumentSkillEntryResponse(BaseModel):
    entry_id: str
    revision_id: str
    entry_type: str
    title: str
    content: str
    source_page: int | None
    source_span: str | None
    confidence: float
    metadata: dict[str, Any]
    created_at: datetime
