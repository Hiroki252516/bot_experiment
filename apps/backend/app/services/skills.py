from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_provider
from app.models.entities import (
    AnswerCandidate,
    AnswerGenerationRun,
    AnswerSelection,
    ChatMessage,
    Skill,
    SkillRevision,
    SkillUpdateJob,
    utcnow,
)
from app.skills.merger import merge_skill_profile


def process_skill_update_job(session: Session, job: SkillUpdateJob) -> None:
    settings = get_settings()
    provider = get_provider(settings)

    message = session.get(ChatMessage, job.chat_message_id)
    selection = session.get(AnswerSelection, job.selection_id) if job.selection_id else None
    if not message or not selection:
        raise ValueError("Skill update job is missing chat message or selection")

    generation = session.scalar(
        select(AnswerGenerationRun).where(AnswerGenerationRun.chat_message_id == message.id)
    )
    candidates = list(
        session.scalars(
            select(AnswerCandidate).where(AnswerCandidate.generation_run_id == generation.id).order_by(AnswerCandidate.rank.asc())
        )
    )
    chosen = next(candidate for candidate in candidates if candidate.id == selection.selected_candidate_id)
    rejected = [candidate for candidate in candidates if candidate.id != selection.selected_candidate_id]

    skill = session.scalar(select(Skill).where(Skill.user_id == message.user_id))
    if not skill:
        raise ValueError("Skill not found for user")
    previous_revision = session.get(SkillRevision, skill.active_revision_id) if skill.active_revision_id else None
    previous_profile = previous_revision.profile_json if previous_revision else settings.default_skill_profile

    job.status = "running"
    job.attempt_count += 1
    job.updated_at = utcnow()
    session.commit()

    delta, _metadata = provider.extract_skill_delta(
        previous_skill=previous_profile,
        chosen_candidate={
            "id": chosen.id,
            "title": chosen.title,
            "style_tags": chosen.style_tags,
            "answer_text": chosen.answer_text,
        },
        rejected_candidates=[
            {"id": candidate.id, "title": candidate.title, "style_tags": candidate.style_tags}
            for candidate in rejected
        ],
        user_comment=selection.comment,
    )
    next_profile = merge_skill_profile(previous_profile, delta)
    current_revision_number = previous_revision.revision_number if previous_revision else 0
    next_revision = SkillRevision(
        skill_id=skill.id,
        revision_number=current_revision_number + 1,
        profile_json=next_profile,
        summary_rule=delta.summary_rule,
        update_reason=f"Selection {selection.id} preferred {chosen.title}",
        source_selection_id=selection.id,
    )
    session.add(next_revision)
    session.flush()

    skill.active_revision_id = next_revision.id
    skill.updated_at = utcnow()
    job.status = "completed"
    job.error_message = None
    job.updated_at = utcnow()
    session.commit()

