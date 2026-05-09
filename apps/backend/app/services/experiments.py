from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import (
    AnswerCandidate,
    AnswerGenerationRun,
    AnswerSelection,
    ChatMessage,
    DocumentSkillEntry,
    DocumentSkillRevision,
    DocumentSkillUsageLog,
    ExperimentRun,
    SkillRevision,
)


def create_experiment_run(session: Session, payload) -> ExperimentRun:
    run = ExperimentRun(
        user_id=payload.user_id,
        chat_message_id=payload.chat_message_id,
        condition_name=payload.condition_name,
        skills_enabled=payload.skills_enabled,
        candidate_count=payload.candidate_count,
        notes=payload.notes,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def list_experiment_runs(session: Session) -> list[ExperimentRun]:
    return list(session.scalars(select(ExperimentRun).order_by(ExperimentRun.created_at.desc())))


def export_logs_zip(session: Session) -> Path:
    settings = get_settings()
    output_path = settings.export_dir / "logs_export.zip"

    turns = list(session.scalars(select(ChatMessage).order_by(ChatMessage.created_at.asc())))
    selections = {
        row.chat_message_id: row
        for row in session.scalars(select(AnswerSelection))
    }
    generations = {
        row.chat_message_id: row
        for row in session.scalars(select(AnswerGenerationRun))
    }
    candidates = list(session.scalars(select(AnswerCandidate).order_by(AnswerCandidate.created_at.asc())))
    revisions = list(session.scalars(select(SkillRevision).order_by(SkillRevision.created_at.asc())))
    document_skill_revisions = list(
        session.scalars(select(DocumentSkillRevision).order_by(DocumentSkillRevision.created_at.asc()))
    )
    document_skill_entries = list(session.scalars(select(DocumentSkillEntry).order_by(DocumentSkillEntry.created_at.asc())))
    document_skill_usage_logs = list(
        session.scalars(select(DocumentSkillUsageLog).order_by(DocumentSkillUsageLog.created_at.asc()))
    )

    csv_payloads: dict[str, str] = {}

    turns_buffer = io.StringIO()
    writer = csv.DictWriter(
        turns_buffer,
        fieldnames=[
            "chat_message_id",
            "user_id",
            "session_id",
            "question_text",
            "skills_enabled",
            "active_skill_revision_id",
            "model_name",
            "prompt_version",
            "created_at",
        ],
    )
    writer.writeheader()
    for turn in turns:
        generation = generations.get(turn.id)
        writer.writerow(
            {
                "chat_message_id": turn.id,
                "user_id": turn.user_id,
                "session_id": turn.session_id,
                "question_text": turn.question_text,
                "skills_enabled": turn.skills_enabled,
                "active_skill_revision_id": turn.active_skill_revision_id,
                "model_name": generation.model_name if generation else "",
                "prompt_version": generation.prompt_version if generation else "",
                "created_at": turn.created_at.isoformat(),
            }
        )
    csv_payloads["turns.csv"] = turns_buffer.getvalue()

    candidates_buffer = io.StringIO()
    writer = csv.DictWriter(
        candidates_buffer,
        fieldnames=["candidate_id", "generation_run_id", "rank", "display_order", "title", "style_tags", "answer_text", "is_selected_cache"],
    )
    writer.writeheader()
    for candidate in candidates:
        writer.writerow(
            {
                "candidate_id": candidate.id,
                "generation_run_id": candidate.generation_run_id,
                "rank": candidate.rank,
                "display_order": candidate.display_order,
                "title": candidate.title,
                "style_tags": "|".join(candidate.style_tags),
                "answer_text": candidate.answer_text,
                "is_selected_cache": candidate.is_selected_cache,
            }
        )
    csv_payloads["candidates.csv"] = candidates_buffer.getvalue()

    feedback_buffer = io.StringIO()
    writer = csv.DictWriter(
        feedback_buffer,
        fieldnames=["selection_id", "chat_message_id", "selected_candidate_id", "satisfaction_score", "clarity_score", "comment", "created_at"],
    )
    writer.writeheader()
    for selection in selections.values():
        writer.writerow(
            {
                "selection_id": selection.id,
                "chat_message_id": selection.chat_message_id,
                "selected_candidate_id": selection.selected_candidate_id,
                "satisfaction_score": selection.satisfaction_score,
                "clarity_score": selection.clarity_score,
                "comment": selection.comment or "",
                "created_at": selection.created_at.isoformat(),
            }
        )
    csv_payloads["feedback.csv"] = feedback_buffer.getvalue()

    revisions_buffer = io.StringIO()
    writer = csv.DictWriter(
        revisions_buffer,
        fieldnames=["revision_id", "skill_id", "revision_number", "summary_rule", "update_reason", "source_selection_id", "created_at"],
    )
    writer.writeheader()
    for revision in revisions:
        writer.writerow(
            {
                "revision_id": revision.id,
                "skill_id": revision.skill_id,
                "revision_number": revision.revision_number,
                "summary_rule": revision.summary_rule,
                "update_reason": revision.update_reason,
                "source_selection_id": revision.source_selection_id or "",
                "created_at": revision.created_at.isoformat(),
            }
        )
    csv_payloads["skill_revisions.csv"] = revisions_buffer.getvalue()

    retrievals_buffer = io.StringIO()
    writer = csv.DictWriter(
        retrievals_buffer,
        fieldnames=["deprecated_note"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "deprecated_note": "runtime RAG retrieval is deprecated; use document_skill_usage_logs.csv",
        }
    )
    csv_payloads["retrievals.csv"] = retrievals_buffer.getvalue()

    document_revisions_buffer = io.StringIO()
    writer = csv.DictWriter(
        document_revisions_buffer,
        fieldnames=[
            "revision_id",
            "document_skill_id",
            "revision_number",
            "summary",
            "extraction_model_name",
            "prompt_version",
            "source_digest",
            "update_reason",
            "created_at",
        ],
    )
    writer.writeheader()
    for revision in document_skill_revisions:
        writer.writerow(
            {
                "revision_id": revision.id,
                "document_skill_id": revision.document_skill_id,
                "revision_number": revision.revision_number,
                "summary": revision.summary,
                "extraction_model_name": revision.extraction_model_name,
                "prompt_version": revision.prompt_version,
                "source_digest": revision.source_digest or "",
                "update_reason": revision.update_reason,
                "created_at": revision.created_at.isoformat(),
            }
        )
    csv_payloads["document_skill_revisions.csv"] = document_revisions_buffer.getvalue()

    document_entries_buffer = io.StringIO()
    writer = csv.DictWriter(
        document_entries_buffer,
        fieldnames=[
            "entry_id",
            "document_skill_revision_id",
            "entry_type",
            "title",
            "content",
            "source_page",
            "source_span",
            "confidence",
            "created_at",
        ],
    )
    writer.writeheader()
    for entry in document_skill_entries:
        writer.writerow(
            {
                "entry_id": entry.id,
                "document_skill_revision_id": entry.document_skill_revision_id,
                "entry_type": entry.entry_type,
                "title": entry.title,
                "content": entry.content,
                "source_page": entry.source_page if entry.source_page is not None else "",
                "source_span": entry.source_span or "",
                "confidence": entry.confidence,
                "created_at": entry.created_at.isoformat(),
            }
        )
    csv_payloads["document_skill_entries.csv"] = document_entries_buffer.getvalue()

    usage_buffer = io.StringIO()
    writer = csv.DictWriter(
        usage_buffer,
        fieldnames=[
            "usage_log_id",
            "chat_message_id",
            "document_id",
            "document_skill_revision_id",
            "document_skill_entry_id",
            "included_order",
            "context_kind",
            "context_hash",
            "created_at",
        ],
    )
    writer.writeheader()
    for usage in document_skill_usage_logs:
        writer.writerow(
            {
                "usage_log_id": usage.id,
                "chat_message_id": usage.chat_message_id,
                "document_id": usage.document_id,
                "document_skill_revision_id": usage.document_skill_revision_id,
                "document_skill_entry_id": usage.document_skill_entry_id or "",
                "included_order": usage.included_order,
                "context_kind": usage.context_kind,
                "context_hash": usage.context_hash,
                "created_at": usage.created_at.isoformat(),
            }
        )
    csv_payloads["document_skill_usage_logs.csv"] = usage_buffer.getvalue()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, payload in csv_payloads.items():
            archive.writestr(filename, payload)
    return output_path
