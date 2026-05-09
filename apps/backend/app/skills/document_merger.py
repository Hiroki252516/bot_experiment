from __future__ import annotations

import re
from typing import Any

from app.schemas.document_skill import DocumentSkillProfile


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = _norm(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _merge_pages(*page_lists: list[int]) -> list[int]:
    pages = {page for page_list in page_lists for page in page_list if page is not None}
    return sorted(pages)


def empty_document_skill_profile(filename: str) -> dict[str, Any]:
    return DocumentSkillProfile(
        document_title=filename,
        answering_guidelines=[
            "教材に書かれた事実・手順・注意点を優先して回答する。",
            "教材に根拠がない場合は、該当箇所が見つからないことを明示する。",
        ],
    ).model_dump()


def merge_document_skill_profile(previous: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    profile = DocumentSkillProfile.model_validate(previous).model_dump()
    incoming = DocumentSkillProfile.model_validate(delta).model_dump()

    if incoming.get("summary"):
        summaries = _unique_strings([profile.get("summary", ""), incoming["summary"]])
        profile["summary"] = "\n".join(summaries)[:4000]

    for field in ["learning_objectives", "warnings", "common_misconceptions", "answering_guidelines"]:
        profile[field] = _unique_strings([*profile.get(field, []), *incoming.get(field, [])])

    profile["key_concepts"] = _merge_by_key(
        profile.get("key_concepts", []),
        incoming.get("key_concepts", []),
        key_field="name",
        text_fields=["explanation"],
    )
    profile["definitions"] = _merge_by_key(
        profile.get("definitions", []),
        incoming.get("definitions", []),
        key_field="term",
        text_fields=["definition"],
    )
    profile["facts"] = _merge_by_key(
        profile.get("facts", []),
        incoming.get("facts", []),
        key_field="statement",
        text_fields=[],
    )
    profile["procedures"] = _merge_by_key(
        profile.get("procedures", []),
        incoming.get("procedures", []),
        key_field="title",
        text_fields=[],
        list_fields=["steps"],
    )
    profile["examples"] = _merge_by_key(
        profile.get("examples", []),
        incoming.get("examples", []),
        key_field="title",
        text_fields=["content"],
    )
    profile["formulas"] = _merge_by_key(
        profile.get("formulas", []),
        incoming.get("formulas", []),
        key_field="name",
        text_fields=["expression", "explanation"],
    )
    profile["source_map"] = _merge_source_map(profile.get("source_map", []), incoming.get("source_map", []))
    return DocumentSkillProfile.model_validate(profile).model_dump()


def _merge_by_key(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    *,
    key_field: str,
    text_fields: list[str],
    list_fields: list[str] | None = None,
) -> list[dict[str, Any]]:
    list_fields = list_fields or []
    by_key: dict[str, dict[str, Any]] = {}
    for item in [*existing, *incoming]:
        key_value = str(item.get(key_field, "")).strip()
        if not key_value:
            continue
        key = _norm(key_value)
        current = by_key.get(key)
        if not current:
            by_key[key] = dict(item)
            continue
        current["source_pages"] = _merge_pages(current.get("source_pages", []), item.get("source_pages", []))
        for field in text_fields:
            merged = _unique_strings([current.get(field, ""), item.get(field, "")])
            current[field] = "\n".join(merged)
        for field in list_fields:
            current[field] = _unique_strings([*current.get(field, []), *item.get(field, [])])
    return list(by_key.values())


def _merge_source_map(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int | None]] = set()
    result: list[dict[str, Any]] = []
    for item in [*existing, *incoming]:
        excerpt = str(item.get("excerpt", "")).strip()
        page = item.get("page")
        key = (_norm(excerpt), page)
        if excerpt and key not in seen:
            seen.add(key)
            result.append(item)
    return result[:200]


def profile_to_entries(profile: dict[str, Any]) -> list[dict[str, Any]]:
    validated = DocumentSkillProfile.model_validate(profile)
    entries: list[dict[str, Any]] = []
    if validated.summary:
        entries.append(_entry("summary", "教材概要", validated.summary, []))
    for objective in validated.learning_objectives:
        entries.append(_entry("learning_objective", "学習目標", objective, []))
    for concept in validated.key_concepts:
        entries.append(_entry("key_concept", concept.name, concept.explanation, concept.source_pages))
    for definition in validated.definitions:
        entries.append(_entry("definition", definition.term, definition.definition, definition.source_pages))
    for fact in validated.facts:
        entries.append(_entry("fact", "教材内の事実", fact.statement, fact.source_pages))
    for procedure in validated.procedures:
        content = "\n".join(f"{index + 1}. {step}" for index, step in enumerate(procedure.steps))
        entries.append(_entry("procedure", procedure.title, content, procedure.source_pages))
    for example in validated.examples:
        entries.append(_entry("example", example.title, example.content, example.source_pages))
    for formula in validated.formulas:
        content = f"{formula.expression}\n{formula.explanation}".strip()
        entries.append(_entry("formula", formula.name, content, formula.source_pages))
    for warning in validated.warnings:
        entries.append(_entry("warning", "注意点", warning, []))
    for misconception in validated.common_misconceptions:
        entries.append(_entry("misconception", "誤解しやすい点", misconception, []))
    for source in validated.source_map:
        entries.append(
            _entry(
                "source_quote",
                "教材抜粋",
                source.excerpt,
                [source.page] if source.page is not None else [],
                source.source_span,
            )
        )
    return entries


def _entry(entry_type: str, title: str, content: str, source_pages: list[int], source_span: str | None = None) -> dict[str, Any]:
    source_page = source_pages[0] if source_pages else None
    normalized = _norm(f"{title} {content}")
    return {
        "entry_type": entry_type,
        "title": title[:255],
        "content": content.strip(),
        "normalized_text": normalized,
        "source_page": source_page,
        "source_span": source_span,
        "confidence": 1.0,
        "metadata_json": {"source_pages": source_pages},
    }
