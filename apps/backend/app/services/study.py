from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import get_generation_provider
from app.models.entities import (
    DocumentSkill,
    RagDocument,
    StudyAssessment,
    StudyAssessmentAttempt,
    StudyChatTurn,
    StudyMasteryEstimate,
    StudyMaterial,
    StudyMaterialRead,
    StudyRun,
    User,
    utcnow,
)
from app.services.document_skills import build_document_skill_context


def _require_run(session: Session, run_id: str) -> StudyRun:
    run = session.get(StudyRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


def _ensure_assessment_cycle(assessment_type: str, cycle_index: int | None) -> int | None:
    if assessment_type == "mini_test":
        if not cycle_index:
            raise HTTPException(status_code=400, detail="cycle_index is required for mini_test")
        return cycle_index
    if cycle_index is not None:
        raise HTTPException(status_code=400, detail="cycle_index must be null for pre_test/post_test")
    return None


def start_run(session: Session, user_id: str, group: str, cycle_count: int = 3) -> StudyRun:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    skills_enabled = group == "A"
    settings = get_settings()

    run = StudyRun(
        user_id=user_id,
        group=group,
        skills_enabled=skills_enabled,
        cycle_count=cycle_count,
        provider_name=settings.active_generation_provider,
        model_name=None,
        prompt_version=settings.prompt_version,
        temperature=settings.generation_temperature,
        top_p=settings.generation_top_p,
        created_at=utcnow(),
        finished_at=None,
    )
    session.add(run)
    session.commit()
    return run


def finish_run(session: Session, run_id: str) -> StudyRun:
    run = _require_run(session, run_id)
    run.finished_at = utcnow()
    session.commit()
    return run


def get_or_create_material(session: Session, run: StudyRun, cycle_index: int) -> StudyMaterial:
    existing = session.execute(
        select(StudyMaterial).where(StudyMaterial.run_id == run.id, StudyMaterial.cycle_index == cycle_index)
    ).scalars().first()
    if existing:
        return existing

    if cycle_index < 1 or cycle_index > run.cycle_count:
        raise HTTPException(status_code=400, detail="cycle_index out of range")

    if run.group == "C":
        # MVP: fixed placeholder material. Replace with repository of fixed texts later.
        content_text = f"固定教材（Cycle {cycle_index}）\n\nこの教材は書籍学習条件向けのテキストです。"
        source_type = "fixed"
        difficulty = None
        metadata = {"fixed_material_version": 1}
    else:
        document_skill_context = _require_study_document_skill_context(session)
        provider = get_generation_provider(get_settings())
        generated, meta = provider.generate_material(
            cycle_index=cycle_index,
            skill_profile={},
            skills_enabled=run.skills_enabled,
            document_skill_context=document_skill_context,
        )
        content_text = generated["content_text"]
        source_type = "generated"
        difficulty = generated.get("difficulty")
        metadata = {
            "provider": meta.provider_name,
            "model": meta.model_name,
            "document_skill_context": document_skill_context,
        }

    material = StudyMaterial(
        run_id=run.id,
        cycle_index=cycle_index,
        source_type=source_type,
        content_text=content_text,
        difficulty=difficulty,
        metadata_json=metadata,
        created_at=utcnow(),
    )
    session.add(material)
    session.commit()
    return material


def confirm_material_read(
    session: Session,
    run_id: str,
    material_id: str,
    presented_at: datetime,
    read_confirmed_at: datetime,
) -> StudyMaterialRead:
    run = _require_run(session, run_id)
    material = session.get(StudyMaterial, material_id)
    if not material or material.run_id != run.id:
        raise HTTPException(status_code=404, detail="Material not found")
    if presented_at.tzinfo is None or read_confirmed_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="timestamps must be timezone-aware")
    duration = int((read_confirmed_at - presented_at).total_seconds())
    if duration < 0:
        raise HTTPException(status_code=400, detail="invalid duration")

    read = StudyMaterialRead(
        run_id=run.id,
        material_id=material.id,
        presented_at=presented_at,
        read_confirmed_at=read_confirmed_at,
        duration_seconds=duration,
        created_at=utcnow(),
    )
    session.add(read)
    session.commit()
    return read


def start_assessment(session: Session, run_id: str, assessment_type: str, cycle_index: int | None) -> StudyAssessmentAttempt:
    run = _require_run(session, run_id)
    cycle_index = _ensure_assessment_cycle(assessment_type, cycle_index)
    content_json = (
        _default_assessment_content(assessment_type, cycle_index)
        if run.group == "C"
        else _generate_assessment_content(session, run, assessment_type, cycle_index)
    )

    assessment = StudyAssessment(
        run_id=run.id,
        assessment_type=assessment_type,
        cycle_index=cycle_index,
        content_json=content_json,
        created_at=utcnow(),
    )
    session.add(assessment)
    session.flush()

    now = datetime.now(timezone.utc)
    attempt = StudyAssessmentAttempt(
        run_id=run.id,
        assessment_id=assessment.id,
        assessment_type=assessment_type,
        cycle_index=cycle_index,
        started_at=now,
        submitted_at=None,
        duration_seconds=None,
        answers_json={},
        score=None,
        max_score=None,
        result_json={},
        created_at=utcnow(),
    )
    session.add(attempt)
    session.commit()
    return attempt


def submit_assessment(session: Session, attempt_id: str, submitted_at: datetime, answers: list[dict]) -> StudyAssessmentAttempt:
    attempt = session.get(StudyAssessmentAttempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Assessment attempt not found")
    if attempt.submitted_at is not None:
        raise HTTPException(status_code=409, detail="Assessment attempt already submitted")
    if submitted_at.tzinfo is None:
        raise HTTPException(status_code=400, detail="submitted_at must be timezone-aware")

    duration = int((submitted_at - attempt.started_at).total_seconds())
    if duration < 0:
        raise HTTPException(status_code=400, detail="invalid duration")

    assessment = session.get(StudyAssessment, attempt.assessment_id)
    if not assessment:
        raise HTTPException(status_code=500, detail="Assessment missing")

    score, max_score, per_question = _score_mcq(assessment.content_json, answers)
    attempt.submitted_at = submitted_at
    attempt.duration_seconds = duration
    attempt.answers_json = {"answers": answers}
    attempt.score = score
    attempt.max_score = max_score
    attempt.result_json = {"per_question_correct": per_question}
    session.commit()
    return attempt


def estimate_mastery(session: Session, run_id: str, cycle_index: int) -> StudyMasteryEstimate:
    run = _require_run(session, run_id)
    if cycle_index < 1 or cycle_index > run.cycle_count:
        raise HTTPException(status_code=400, detail="cycle_index out of range")

    # MVP: naive estimate based on latest mini_test score for the cycle.
    attempt = session.execute(
        select(StudyAssessmentAttempt)
        .where(
            StudyAssessmentAttempt.run_id == run.id,
            StudyAssessmentAttempt.assessment_type == "mini_test",
            StudyAssessmentAttempt.cycle_index == cycle_index,
        )
        .order_by(StudyAssessmentAttempt.created_at.desc())
    ).scalars().first()
    if not attempt or attempt.score is None or attempt.max_score is None:
        raise HTTPException(status_code=400, detail="mini_test attempt not found for cycle")

    mastery = attempt.score / max(1, attempt.max_score)
    estimate_json = {
        "mastery_estimate": mastery,
        "confidence": 0.5,
        "evidence_summary": f"Cycle {cycle_index} mini_test score {attempt.score}/{attempt.max_score}.",
        "next_difficulty_recommendation": "easy" if mastery < 0.4 else "medium" if mastery < 0.75 else "hard",
    }

    estimate = StudyMasteryEstimate(run_id=run.id, cycle_index=cycle_index, estimate_json=estimate_json, created_at=utcnow())
    session.add(estimate)
    session.commit()
    return estimate


def chat_ask(session: Session, run_id: str, material_id: str, question_text: str) -> StudyChatTurn:
    run = _require_run(session, run_id)
    if run.group == "C":
        raise HTTPException(status_code=403, detail="Chat disabled for group C")

    material = session.get(StudyMaterial, material_id)
    if not material or material.run_id != run.id:
        raise HTTPException(status_code=404, detail="Material not found")

    # Guard: chat allowed only during material viewing window (read_confirm not yet done).
    read_exists = session.execute(
        select(StudyMaterialRead).where(StudyMaterialRead.run_id == run.id, StudyMaterialRead.material_id == material.id)
    ).scalars().first()
    if read_exists:
        raise HTTPException(status_code=409, detail="Chat is only allowed while material is being read")

    provider = get_generation_provider(get_settings())
    document_skill_context = _require_study_document_skill_context(session)
    answer, _meta = provider.answer_question(
        material_text=material.content_text,
        question_text=question_text,
        skill_profile={},
        skills_enabled=run.skills_enabled,
        document_skill_context=document_skill_context,
    )
    turn = StudyChatTurn(
        run_id=run.id,
        material_id=material.id,
        cycle_index=material.cycle_index,
        question_text=question_text,
        answer_text=answer["answer_text"],
        created_at=utcnow(),
    )
    session.add(turn)
    session.commit()
    return turn


def _require_study_document_skill_context(session: Session) -> dict:
    completed_upload_ids = list(
        session.scalars(
            select(DocumentSkill.document_id)
            .join(RagDocument, RagDocument.id == DocumentSkill.document_id)
            .where(DocumentSkill.status == "completed")
            .where(RagDocument.ingest_status == "completed")
            .where(RagDocument.source_type != "seed")
            .order_by(RagDocument.created_at.desc())
        )
    )
    context, _usage_items = build_document_skill_context(
        session,
        document_ids=completed_upload_ids or None,
        enabled=True,
    )
    if not context.get("documents"):
        raise HTTPException(
            status_code=409,
            detail="アップロード教材のingestまたはDocument Skill抽出が未完了です。教材アップロード後にingest完了を確認してください。",
        )
    return context


def _generate_assessment_content(
    session: Session,
    run: StudyRun,
    assessment_type: str,
    cycle_index: int | None,
) -> dict:
    document_skill_context = _require_study_document_skill_context(session)
    material_text: str | None = None
    if assessment_type == "mini_test" and cycle_index is not None:
        material = session.execute(
            select(StudyMaterial).where(StudyMaterial.run_id == run.id, StudyMaterial.cycle_index == cycle_index)
        ).scalars().first()
        material_text = material.content_text if material else None
    provider = get_generation_provider(get_settings())
    assessment, _meta = provider.generate_assessment(
        assessment_type=assessment_type,
        cycle_index=cycle_index,
        material_text=material_text,
        document_skill_context=document_skill_context,
        skill_profile={},
        skills_enabled=run.skills_enabled,
    )
    return _normalize_assessment_content(assessment, assessment_type, cycle_index)


def _normalize_assessment_content(assessment: dict, assessment_type: str, cycle_index: int | None) -> dict:
    questions = []
    prefix = "Pre" if assessment_type == "pre_test" else "Post" if assessment_type == "post_test" else f"Mini{cycle_index}"
    for index, question in enumerate(assessment.get("questions", []), start=1):
        choices = [str(choice) for choice in question.get("choices", [])][:4]
        while len(choices) < 4:
            choices.append(f"選択肢{len(choices) + 1}")
        correct_choice_index = int(question.get("correct_choice_index", 0))
        if correct_choice_index < 0 or correct_choice_index >= len(choices):
            correct_choice_index = 0
        questions.append(
            {
                "question_id": str(question.get("question_id") or f"{prefix}_q{index}"),
                "stem": str(question.get("stem") or "教材内容に基づいて正しい選択肢を選んでください。"),
                "choices": choices,
                "correct_choice_index": correct_choice_index,
            }
        )
    if not questions:
        return _default_assessment_content(assessment_type, cycle_index)
    return {"questions": questions}


def _default_assessment_content(assessment_type: str, cycle_index: int | None) -> dict:
    # MVP placeholder content. Later: generate via provider.
    prefix = "Pre" if assessment_type == "pre_test" else "Post" if assessment_type == "post_test" else f"Mini{cycle_index}"
    return {
        "questions": [
            {
                "question_id": f"{prefix}_q1",
                "stem": "次のうち正しいものを1つ選んでください。",
                "choices": ["選択肢A", "選択肢B", "選択肢C", "選択肢D"],
                "correct_choice_index": 0,
            },
            {
                "question_id": f"{prefix}_q2",
                "stem": "理解度チェック（ダミー）: もっとも適切な選択肢を選んでください。",
                "choices": ["1", "2", "3", "4"],
                "correct_choice_index": 1,
            },
        ]
    }


def _score_mcq(assessment_content: dict, answers: list[dict]) -> tuple[int, int, list[dict]]:
    questions = {q["question_id"]: q for q in assessment_content.get("questions", [])}
    max_score = len(questions)
    score = 0
    per_question: list[dict] = []
    for answer in answers:
        qid = answer["question_id"]
        choice = int(answer["choice_index"])
        q = questions.get(qid)
        is_correct = bool(q and choice == int(q.get("correct_choice_index")))
        if is_correct:
            score += 1
        per_question.append({"question_id": qid, "is_correct": is_correct})
    return score, max_score, per_question
