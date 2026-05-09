from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_generation_model_name, get_generation_provider
from app.models.entities import (
    AnswerCandidate,
    AnswerGenerationRun,
    AnswerSelection,
    ChatMessage,
    ChatSession,
    ExperimentRun,
    SkillRevision,
    SkillUpdateJob,
    SubjectiveFeedback,
    utcnow,
)
from app.schemas.chat import ChatGenerateRequest, ChatSelectRequest
from app.services.document_skills import (
    build_document_skill_context,
    get_usage_contexts_for_message,
    persist_document_skill_usage_logs,
)
from app.services.users import get_user_with_skill


def _ensure_session(session: Session, user_id: str, session_id: str | None) -> ChatSession:
    if session_id:
        chat_session = session.get(ChatSession, session_id)
        if chat_session:
            if chat_session.user_id != user_id:
                raise PermissionError("Chat session does not belong to the authenticated user")
            return chat_session
    chat_session = ChatSession(user_id=user_id)
    session.add(chat_session)
    session.flush()
    return chat_session


def generate_candidates_for_chat(
    session: Session,
    payload: ChatGenerateRequest,
    authenticated_user_id: str | None = None,
) -> dict:
    settings = get_settings()
    generation_provider = get_generation_provider(settings)
    user_id = authenticated_user_id or payload.user_id
    if not user_id:
        raise ValueError("User not found")

    user, skill, active_revision = get_user_with_skill(session, user_id)
    if not user or not skill:
        raise ValueError("User not found")
    user.last_seen_at = utcnow()

    chat_session = _ensure_session(session, user_id, payload.session_id)
    message = ChatMessage(
        session_id=chat_session.id,
        user_id=user_id,
        question_text=payload.question,
        skills_enabled=payload.skills_enabled,
        active_skill_revision_id=active_revision.id if payload.skills_enabled and active_revision else None,
        experiment_condition=payload.experiment_condition,
    )
    session.add(message)
    session.flush()

    skill_profile = active_revision.profile_json if payload.skills_enabled and active_revision else settings.default_skill_profile
    document_skill_context, document_skill_usage_items = build_document_skill_context(
        session,
        document_ids=payload.document_ids,
        enabled=payload.document_skills_enabled,
    )

    generation = AnswerGenerationRun(
        chat_message_id=message.id,
        provider_name=generation_provider.provider_name,
        model_name=get_generation_model_name(settings, generation_provider.provider_name),
        temperature=settings.generation_temperature,
        top_p=settings.generation_top_p,
        candidate_count=payload.candidate_count,
        prompt_version=settings.prompt_version,
        retrieval_top_k=0,
        status="completed",
    )
    session.add(generation)
    session.flush()

    candidates: list[AnswerCandidate] = []
    candidate_set, _metadata = generation_provider.generate_candidates(
        question=payload.question,
        preference_skill_profile=skill_profile,
        document_skill_context=document_skill_context,
        candidate_count=payload.candidate_count,
        personalization_skills_enabled=payload.skills_enabled,
        document_skills_enabled=payload.document_skills_enabled,
    )
    for index, candidate in enumerate(candidate_set.candidates, start=1):
        candidates.append(
            AnswerCandidate(
                generation_run_id=generation.id,
                rank=index,
                display_order=index,
                title=candidate.title,
                style_tags=candidate.style_tags,
                answer_text=candidate.answer_text,
                rationale_internal=candidate.rationale,
            )
        )

    session.add_all(candidates)
    persist_document_skill_usage_logs(session, chat_message_id=message.id, usage_items=document_skill_usage_items)

    experiment_run = ExperimentRun(
        user_id=user_id,
        chat_message_id=message.id,
        condition_name=payload.experiment_condition or ("skills_on" if payload.skills_enabled else "skills_off"),
        skills_enabled=payload.skills_enabled,
        candidate_count=payload.candidate_count,
        notes=payload.course_context,
    )
    session.add(experiment_run)
    session.commit()

    return {
        "session_id": chat_session.id,
        "chat_message_id": message.id,
        "generation_run_id": generation.id,
        "skills_enabled": payload.skills_enabled,
        "active_skill_revision_id": message.active_skill_revision_id,
        "retrievals": [],
        "document_skill_contexts": document_skill_context["documents"],
        "candidates": candidates,
    }


def select_candidate_for_chat(
    session: Session,
    payload: ChatSelectRequest,
    authenticated_user_id: str | None = None,
) -> dict:
    message = session.get(ChatMessage, payload.chat_message_id)
    if not message:
        raise ValueError("Chat message not found")
    if authenticated_user_id and message.user_id != authenticated_user_id:
        raise PermissionError("Chat message does not belong to the authenticated user")

    existing = session.scalar(select(AnswerSelection).where(AnswerSelection.chat_message_id == payload.chat_message_id))
    if existing:
        raise ValueError("Selection already exists for this chat message")

    selected_candidate = session.get(AnswerCandidate, payload.selected_candidate_id)
    if not selected_candidate:
        raise ValueError("Selected candidate not found")
    generation = session.get(AnswerGenerationRun, selected_candidate.generation_run_id)
    if not generation or generation.chat_message_id != message.id:
        raise ValueError("Selected candidate does not belong to this chat message")

    selection = AnswerSelection(
        chat_message_id=payload.chat_message_id,
        selected_candidate_id=payload.selected_candidate_id,
        satisfaction_score=payload.satisfaction_score,
        clarity_score=payload.clarity_score,
        comment=payload.comment,
    )
    session.add(selection)
    selected_candidate.is_selected_cache = True
    session.flush()

    session.add_all(
        [
            SubjectiveFeedback(selection_id=selection.id, feedback_type="satisfaction_score", score_int=payload.satisfaction_score),
            SubjectiveFeedback(selection_id=selection.id, feedback_type="clarity_score", score_int=payload.clarity_score),
        ]
    )
    if payload.comment:
        session.add(SubjectiveFeedback(selection_id=selection.id, feedback_type="comment", text_value=payload.comment))

    job = SkillUpdateJob(
        user_id=message.user_id,
        chat_message_id=message.id,
        selection_id=selection.id,
        job_type="skill_update",
        status="pending",
        attempt_count=0,
        payload_json={"chat_message_id": message.id},
        updated_at=utcnow(),
    )
    session.add(job)
    session.commit()
    return {"selection_id": selection.id, "skill_update_job_id": job.id, "status": "accepted"}


def get_session_detail(session: Session, session_id: str) -> dict:
    chat_session = session.get(ChatSession, session_id)
    if not chat_session:
        raise ValueError("Session not found")

    messages = list(
        session.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())
        )
    )
    items = []
    for message in messages:
        generation = session.scalar(
            select(AnswerGenerationRun).where(AnswerGenerationRun.chat_message_id == message.id)
        )
        candidates = (
            list(
                session.scalars(
                    select(AnswerCandidate)
                    .where(AnswerCandidate.generation_run_id == generation.id)
                    .order_by(AnswerCandidate.display_order.asc())
                )
            )
            if generation
            else []
        )
        selection = session.scalar(select(AnswerSelection).where(AnswerSelection.chat_message_id == message.id))
        document_skill_contexts = get_usage_contexts_for_message(session, message.id)
        items.append(
            {
                "chat_message_id": message.id,
                "question_text": message.question_text,
                "skills_enabled": message.skills_enabled,
                "active_skill_revision_id": message.active_skill_revision_id,
                "candidates": [
                    {
                        "candidate_id": candidate.id,
                        "title": candidate.title,
                        "style_tags": candidate.style_tags,
                        "answer_text": candidate.answer_text,
                        "rank": candidate.rank,
                        "display_order": candidate.display_order,
                    }
                    for candidate in candidates
                ],
                "selection": {
                    "selection_id": selection.id,
                    "selected_candidate_id": selection.selected_candidate_id,
                    "satisfaction_score": selection.satisfaction_score,
                    "clarity_score": selection.clarity_score,
                    "comment": selection.comment,
                }
                if selection
                else None,
                "retrievals": [],
                "document_skill_contexts": document_skill_contexts,
                "created_at": message.created_at,
            }
        )
    return {"session_id": chat_session.id, "user_id": chat_session.user_id, "messages": items}


def get_user_logs(session: Session, user_id: str) -> list[dict]:
    sessions = list(
        session.scalars(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at.desc()))
    )
    return [get_session_detail(session, chat_session.id) for chat_session in sessions]


def get_turn_detail(session: Session, chat_message_id: str) -> dict:
    message = session.get(ChatMessage, chat_message_id)
    if not message:
        raise ValueError("Chat message not found")
    session_detail = get_session_detail(session, message.session_id)
    for item in session_detail["messages"]:
        if item["chat_message_id"] == chat_message_id:
            return item
    raise ValueError("Chat message detail not found")


def get_skill_history(session: Session, user_id: str) -> list[SkillRevision]:
    _, skill, _ = get_user_with_skill(session, user_id)
    if not skill:
        raise ValueError("User not found")
    return list(
        session.scalars(
            select(SkillRevision)
            .where(SkillRevision.skill_id == skill.id)
            .order_by(SkillRevision.revision_number.asc())
        )
    )
