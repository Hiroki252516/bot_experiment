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
    ExperimentRun,
    RetrievalLog,
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
    retrievals = list(session.scalars(select(RetrievalLog).order_by(RetrievalLog.created_at.asc())))
    revisions = list(session.scalars(select(SkillRevision).order_by(SkillRevision.created_at.asc())))

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
        fieldnames=["retrieval_id", "chat_message_id", "chunk_id", "score", "rank", "embedding_model", "created_at"],
    )
    writer.writeheader()
    for retrieval in retrievals:
        writer.writerow(
            {
                "retrieval_id": retrieval.id,
                "chat_message_id": retrieval.chat_message_id,
                "chunk_id": retrieval.chunk_id,
                "score": retrieval.score,
                "rank": retrieval.rank,
                "embedding_model": retrieval.embedding_model,
                "created_at": retrieval.created_at.isoformat(),
            }
        )
    csv_payloads["retrievals.csv"] = retrievals_buffer.getvalue()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename, payload in csv_payloads.items():
            archive.writestr(filename, payload)
    return output_path

