from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import DocumentSkill, DocumentSkillEntry, DocumentSkillRevision, DocumentSkillUsageLog, RagDocument


@dataclass(frozen=True)
class DocumentSkillUsageItem:
    document_id: str
    document_skill_revision_id: str
    document_skill_entry_id: str
    included_order: int
    context_kind: str
    context_hash: str


ENTRY_PRIORITY = {
    "summary": 0,
    "learning_objective": 1,
    "procedure": 2,
    "key_concept": 3,
    "definition": 4,
    "fact": 5,
    "warning": 6,
    "example": 7,
    "formula": 8,
    "misconception": 9,
    "source_quote": 10,
}


def build_document_skill_context(
    session: Session,
    *,
    document_ids: list[str] | None,
    enabled: bool,
) -> tuple[dict, list[DocumentSkillUsageItem]]:
    settings = get_settings()
    if not enabled:
        return {"documents": []}, []

    stmt = (
        select(RagDocument, DocumentSkill, DocumentSkillRevision)
        .join(DocumentSkill, DocumentSkill.document_id == RagDocument.id)
        .join(DocumentSkillRevision, DocumentSkillRevision.id == DocumentSkill.active_revision_id)
        .where(DocumentSkill.status == "completed")
        .where(RagDocument.ingest_status == "completed")
        .order_by(RagDocument.created_at.desc())
    )
    if document_ids:
        stmt = stmt.where(RagDocument.id.in_(document_ids))
    else:
        stmt = stmt.where(RagDocument.source_type != "seed")

    documents: list[dict] = []
    usage_items: list[DocumentSkillUsageItem] = []
    used_chars = 0
    included_order = 0
    for document, _document_skill, revision in session.execute(stmt).all():
        entries = list(
            session.scalars(
                select(DocumentSkillEntry).where(DocumentSkillEntry.document_skill_revision_id == revision.id)
            )
        )
        entries.sort(key=lambda entry: (ENTRY_PRIORITY.get(entry.entry_type, 99), entry.created_at, entry.title))
        context_entries: list[dict] = []
        for entry in entries:
            if len(usage_items) >= settings.document_skill_max_entries:
                break
            content = entry.content
            if not settings.document_skill_include_source_excerpts and entry.entry_type == "source_quote":
                continue
            projected = used_chars + len(entry.title) + len(content)
            if projected > settings.document_skill_context_max_chars and usage_items:
                break
            used_chars = projected
            included_order += 1
            context_hash = hashlib.sha256(f"{entry.id}:{entry.content}".encode("utf-8")).hexdigest()
            context_entries.append(
                {
                    "entry_id": entry.id,
                    "entry_type": entry.entry_type,
                    "title": entry.title,
                    "content": content,
                    "source_page": entry.source_page,
                    "source_span": entry.source_span,
                    "included_order": included_order,
                }
            )
            usage_items.append(
                DocumentSkillUsageItem(
                    document_id=document.id,
                    document_skill_revision_id=revision.id,
                    document_skill_entry_id=entry.id,
                    included_order=included_order,
                    context_kind=entry.entry_type,
                    context_hash=context_hash,
                )
            )
        if context_entries:
            documents.append(
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "document_skill_revision_id": revision.id,
                    "entries": context_entries,
                }
            )
    return {"documents": documents}, usage_items


def persist_document_skill_usage_logs(
    session: Session,
    *,
    chat_message_id: str,
    usage_items: list[DocumentSkillUsageItem],
) -> None:
    for item in usage_items:
        session.add(
            DocumentSkillUsageLog(
                chat_message_id=chat_message_id,
                document_id=item.document_id,
                document_skill_revision_id=item.document_skill_revision_id,
                document_skill_entry_id=item.document_skill_entry_id,
                included_order=item.included_order,
                context_kind=item.context_kind,
                context_hash=item.context_hash,
            )
        )


def get_usage_contexts_for_message(session: Session, chat_message_id: str) -> list[dict]:
    rows = session.execute(
        select(RagDocument, DocumentSkillRevision, DocumentSkillEntry, DocumentSkillUsageLog)
        .join(DocumentSkillRevision, DocumentSkillRevision.id == DocumentSkillUsageLog.document_skill_revision_id)
        .join(RagDocument, RagDocument.id == DocumentSkillUsageLog.document_id)
        .join(DocumentSkillEntry, DocumentSkillEntry.id == DocumentSkillUsageLog.document_skill_entry_id)
        .where(DocumentSkillUsageLog.chat_message_id == chat_message_id)
        .order_by(DocumentSkillUsageLog.included_order.asc())
    ).all()
    by_document: dict[str, dict] = {}
    for document, revision, entry, usage in rows:
        context = by_document.setdefault(
            document.id,
            {
                "document_id": document.id,
                "filename": document.filename,
                "document_skill_revision_id": revision.id,
                "entries": [],
            },
        )
        context["entries"].append(
            {
                "entry_id": entry.id,
                "entry_type": entry.entry_type,
                "title": entry.title,
                "content": entry.content,
                "source_page": entry.source_page,
                "source_span": entry.source_span,
                "included_order": usage.included_order,
            }
        )
    return list(by_document.values())
