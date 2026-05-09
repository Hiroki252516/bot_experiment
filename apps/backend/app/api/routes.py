from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.core.config import get_settings
from app.llm.providers import get_generation_model_name
from app.models.entities import StudyAssessment, StudyRun, User
from app.schemas.admin import (
    AdminRecomputeResponse,
    ExperimentRunCreateRequest,
    ExperimentRunResponse,
    RuntimeProviderResponse,
    SkillHistoryResponse,
)
from app.schemas.adaptive import (
    AdminDocumentResponse,
    AdminDocumentUploadResponse,
    AssessmentGenerateResponse,
    AssessmentSubmitRequestV2,
    AssessmentSubmitResponseV2,
    ExportJobResponse,
    ExtractSkillResponse,
    MaterialGenerateResponse,
    MaterialReadConfirmResponseV2,
    ResultResponse,
    RunStartRequestV2,
    RunStartResponseV2,
    RunStateResponse,
)
from app.schemas.auth import AuthLoginRequest, AuthRegisterRequest, AuthUserResponse
from app.schemas.chat import (
    ChatGenerateRequest,
    ChatGenerateResponse,
    ChatSelectRequest,
    ChatSelectResponse,
    SessionDetailResponse,
)
from app.schemas.common import HealthResponse
from app.schemas.document import DocumentChunkResponse, DocumentDeleteResponse, DocumentResponse, IngestJobResponse
from app.schemas.document_skill import (
    DocumentSkillEntryResponse,
    DocumentSkillResponse,
    DocumentSkillRevisionResponse,
)
from app.schemas.study import (
    AssessmentStartRequest,
    AssessmentStartResponse,
    AssessmentSubmitRequest,
    AssessmentSubmitResponse,
    ChatAskRequest,
    ChatAskResponse,
    MasteryEstimateRequest,
    MasteryEstimateResponse,
    MaterialNextRequest,
    MaterialReadConfirmRequest,
    MaterialReadConfirmResponse,
    MaterialResponse,
    RunFinishRequest,
    RunFinishResponse,
    RunStartRequest,
    RunStartResponse,
)
from app.schemas.user import SkillSummaryResponse, UserCreateRequest, UserResponse
from app.services.chat import (
    generate_candidates_for_chat,
    get_session_detail,
    get_skill_history,
    get_turn_detail,
    get_user_logs,
    select_candidate_for_chat,
)
from app.services.auth import (
    DuplicateUsernameError,
    InvalidCredentialsError,
    get_user_for_session_token,
    login_user,
    logout_session,
    register_user,
)
from app.services.documents import (
    create_document,
    create_ingestion_job,
    delete_document,
    get_document_skill,
    list_chunks,
    list_document_skill_entries,
    list_document_skill_revisions,
    list_documents,
)
from app.services.experiments import create_experiment_run, export_logs_zip, list_experiment_runs
from app.services.study import (
    chat_ask,
    confirm_material_read,
    estimate_mastery,
    finish_run,
    get_or_create_material,
    start_assessment,
    start_run,
    submit_assessment,
)
from app.services.users import create_user, get_user_with_skill
from app.services import adaptive as adaptive_service

router = APIRouter()


def _set_auth_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.auth_session_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(key=settings.auth_cookie_name, path="/", samesite="lax")


def _auth_user_response(user: User, active_skill_revision_id: str | None) -> AuthUserResponse:
    if not user.username:
        raise HTTPException(status_code=401, detail="Authenticated user has no username")
    return AuthUserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
        active_skill_revision_id=active_skill_revision_id,
    )


def require_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user, _revision = get_user_for_session_token(session, token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    session.execute(text("SELECT 1"))
    return HealthResponse(status="ok", database="ok", timestamp=datetime.now(timezone.utc))


# --- Adaptive learning MVP APIs (Document Agent Skill + 10 cycles, no runtime RAG) ---


@router.post("/api/admin/documents/upload", response_model=AdminDocumentUploadResponse)
def adaptive_upload_document_route(
    file: UploadFile = File(...),
    title: str = Form(""),
    description: str | None = Form(None),
    session: Session = Depends(get_session),
) -> AdminDocumentUploadResponse:
    document = adaptive_service.save_source_document(session, file, title=title or (file.filename or "教材"), description=description)
    return AdminDocumentUploadResponse(
        document_id=document.id,
        status=document.status,
        title=document.title,
        created_at=document.created_at,
    )


@router.get("/api/admin/documents", response_model=list[AdminDocumentResponse])
def adaptive_list_documents_route(session: Session = Depends(get_session)) -> list[AdminDocumentResponse]:
    return [
        AdminDocumentResponse(
            document_id=document.id,
            title=document.title,
            description=document.description,
            filename=document.filename,
            mime_type=document.mime_type,
            status=document.status,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        for document in adaptive_service.list_source_documents(session)
    ]


@router.delete("/api/admin/documents/{document_id}")
def adaptive_delete_document_route(document_id: str, session: Session = Depends(get_session)) -> dict:
    hard_deleted = adaptive_service.delete_source_document(session, document_id)
    return {"document_id": document_id, "deleted": True, "hard_deleted": hard_deleted}


@router.post("/api/admin/documents/{document_id}/extract-skill", response_model=ExtractSkillResponse)
def adaptive_extract_document_skill_route(document_id: str, session: Session = Depends(get_session)) -> ExtractSkillResponse:
    document, revision, entry_count = adaptive_service.extract_document_skill(session, document_id)
    return ExtractSkillResponse(
        document_id=document.id,
        document_skill_revision_id=revision.id,
        status=document.status,
        entry_count=entry_count,
    )


@router.post("/api/runs/start")
def adaptive_start_run_route(payload: dict = Body(...), session: Session = Depends(get_session)) -> dict:
    if "document_id" not in payload:
        # Legacy study-flow compatibility. New adaptive UI always sends document_id.
        legacy_run = start_run(
            session,
            user_id=payload["user_id"],
            group=payload.get("group", "A"),
            cycle_count=int(payload.get("cycle_count", 3)),
        )
        return {
            "run_id": legacy_run.id,
            "user_id": legacy_run.user_id,
            "group": legacy_run.group,
            "skills_enabled": legacy_run.skills_enabled,
            "cycle_count": legacy_run.cycle_count,
            "created_at": legacy_run.created_at,
        }
    parsed = RunStartRequestV2.model_validate(payload)
    run = adaptive_service.start_run(session, parsed.user_id, parsed.document_id, parsed.cycle_count)
    return RunStartResponseV2(run_id=run.id, state=run.state, cycle_count=run.cycle_count).model_dump(mode="json")


@router.get("/api/runs/{run_id}/state", response_model=RunStateResponse)
def adaptive_run_state_route(run_id: str, session: Session = Depends(get_session)) -> RunStateResponse:
    return RunStateResponse(**adaptive_service.get_run_state(session, run_id))


@router.post("/api/runs/{run_id}/initial-test/generate", response_model=AssessmentGenerateResponse)
def adaptive_generate_initial_test_route(run_id: str, session: Session = Depends(get_session)) -> AssessmentGenerateResponse:
    assessment = adaptive_service.generate_initial_test(session, run_id)
    return AssessmentGenerateResponse(
        assessment_id=assessment.id,
        assessment_type=assessment.assessment_type,
        question_count=len(assessment.questions_json.get("questions", [])),
        state="INITIAL_TEST_GENERATED",
    )


@router.get("/api/runs/{run_id}/initial-test")
def adaptive_get_initial_test_route(run_id: str, session: Session = Depends(get_session)) -> dict:
    assessment = adaptive_service._latest_assessment(session, run_id, "initial", None)
    return {"assessment_id": assessment.id, **assessment.questions_json}


@router.post("/api/runs/{run_id}/initial-test/submit", response_model=AssessmentSubmitResponseV2)
def adaptive_submit_initial_test_route(
    run_id: str,
    payload: AssessmentSubmitRequestV2,
    session: Session = Depends(get_session),
) -> AssessmentSubmitResponseV2:
    attempt, revision = adaptive_service.submit_initial_test(
        session,
        run_id,
        [answer.model_dump() for answer in payload.answers],
        payload.submitted_at,
    )
    return AssessmentSubmitResponseV2(
        attempt_id=attempt.id,
        score=attempt.score or 0,
        max_score=attempt.max_score or 0,
        learner_skill_revision_id=revision.id,
        state="INITIAL_TEST_SUBMITTED",
        next_cycle_index=1,
    )


@router.post("/api/runs/{run_id}/cycles/{cycle_index}/material/generate", response_model=MaterialGenerateResponse)
def adaptive_generate_material_route(run_id: str, cycle_index: int, session: Session = Depends(get_session)) -> MaterialGenerateResponse:
    material = adaptive_service.generate_cycle_material(session, run_id, cycle_index)
    return MaterialGenerateResponse(
        material_id=material.id,
        cycle_index=material.cycle_index,
        title=material.title,
        state="CYCLE_MATERIAL_GENERATED",
    )


@router.get("/api/runs/{run_id}/cycles/{cycle_index}/material")
def adaptive_get_material_route(run_id: str, cycle_index: int, session: Session = Depends(get_session)) -> dict:
    material = adaptive_service._latest_material(session, run_id, cycle_index)
    return {
        "material_id": material.id,
        "run_id": material.run_id,
        "cycle_index": material.cycle_index,
        "title": material.title,
        "content_markdown": material.content_markdown,
        "focus_topics": material.focus_topics_json,
        "created_at": material.created_at,
    }


@router.post("/api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm", response_model=MaterialReadConfirmResponseV2)
def adaptive_confirm_material_read_route(run_id: str, cycle_index: int, session: Session = Depends(get_session)) -> MaterialReadConfirmResponseV2:
    read = adaptive_service.confirm_material_read(session, run_id, cycle_index)
    return MaterialReadConfirmResponseV2(
        material_read_id=read.id,
        read_duration_seconds=read.read_duration_seconds,
        state="CYCLE_MATERIAL_READ",
    )


@router.post("/api/runs/{run_id}/cycles/{cycle_index}/test/generate", response_model=AssessmentGenerateResponse)
def adaptive_generate_cycle_test_route(run_id: str, cycle_index: int, session: Session = Depends(get_session)) -> AssessmentGenerateResponse:
    assessment = adaptive_service.generate_cycle_test(session, run_id, cycle_index)
    return AssessmentGenerateResponse(
        assessment_id=assessment.id,
        assessment_type=assessment.assessment_type,
        cycle_index=assessment.cycle_index,
        question_count=len(assessment.questions_json.get("questions", [])),
        state="CYCLE_TEST_GENERATED",
    )


@router.get("/api/runs/{run_id}/cycles/{cycle_index}/test")
def adaptive_get_cycle_test_route(run_id: str, cycle_index: int, session: Session = Depends(get_session)) -> dict:
    assessment = adaptive_service._latest_assessment(session, run_id, "cycle", cycle_index)
    return {"assessment_id": assessment.id, "cycle_index": cycle_index, **assessment.questions_json}


@router.post("/api/runs/{run_id}/cycles/{cycle_index}/test/submit", response_model=AssessmentSubmitResponseV2)
def adaptive_submit_cycle_test_route(
    run_id: str,
    cycle_index: int,
    payload: AssessmentSubmitRequestV2,
    session: Session = Depends(get_session),
) -> AssessmentSubmitResponseV2:
    attempt, revision = adaptive_service.submit_cycle_test(
        session,
        run_id,
        cycle_index,
        [answer.model_dump() for answer in payload.answers],
        payload.submitted_at,
    )
    return AssessmentSubmitResponseV2(
        attempt_id=attempt.id,
        score=attempt.score or 0,
        max_score=attempt.max_score or 0,
        learner_skill_revision_id=revision.id,
        state="CYCLE_TEST_SUBMITTED",
        next_cycle_index=cycle_index + 1 if cycle_index < 10 else None,
    )


@router.post("/api/runs/{run_id}/final-test/generate", response_model=AssessmentGenerateResponse)
def adaptive_generate_final_test_route(run_id: str, session: Session = Depends(get_session)) -> AssessmentGenerateResponse:
    assessment = adaptive_service.generate_final_test(session, run_id)
    return AssessmentGenerateResponse(
        assessment_id=assessment.id,
        assessment_type=assessment.assessment_type,
        question_count=len(assessment.questions_json.get("questions", [])),
        state="FINAL_TEST_GENERATED",
    )


@router.get("/api/runs/{run_id}/final-test")
def adaptive_get_final_test_route(run_id: str, session: Session = Depends(get_session)) -> dict:
    assessment = adaptive_service._latest_assessment(session, run_id, "final", None)
    return {"assessment_id": assessment.id, **assessment.questions_json}


@router.post("/api/runs/{run_id}/final-test/submit", response_model=AssessmentSubmitResponseV2)
def adaptive_submit_final_test_route(
    run_id: str,
    payload: AssessmentSubmitRequestV2,
    session: Session = Depends(get_session),
) -> AssessmentSubmitResponseV2:
    attempt, _summary = adaptive_service.submit_final_test(
        session,
        run_id,
        [answer.model_dump() for answer in payload.answers],
        payload.submitted_at,
    )
    return AssessmentSubmitResponseV2(
        attempt_id=attempt.id,
        score=attempt.score or 0,
        max_score=attempt.max_score or 0,
        learner_skill_revision_id=None,
        state="RESULT_READY",
    )


@router.get("/api/runs/{run_id}/results", response_model=ResultResponse)
def adaptive_results_route(run_id: str, session: Session = Depends(get_session)) -> ResultResponse:
    summary = adaptive_service.get_results(session, run_id)
    return ResultResponse(
        run_id=summary.run_id,
        initial_score=summary.initial_score,
        final_score=summary.final_score,
        gain_score=summary.gain_score,
        gain_rate=summary.gain_rate,
        initial_accuracy=summary.initial_accuracy,
        final_accuracy=summary.final_accuracy,
        accuracy_gain=summary.accuracy_gain,
        cycle_score_trend=summary.cycle_score_trend,
        improved_topics=summary.improved_topics,
        remaining_weak_topics=summary.remaining_weak_topics,
        ai_summary=summary.ai_summary,
    )


@router.post("/api/admin/exports/runs/{run_id}", response_model=ExportJobResponse)
def adaptive_export_run_route(run_id: str, session: Session = Depends(get_session)) -> ExportJobResponse:
    job = adaptive_service.export_run_zip(session, run_id)
    return ExportJobResponse(export_job_id=job.id, status=job.status, file_path=job.file_path)


@router.get("/api/admin/exports/{export_job_id}", response_model=ExportJobResponse)
def adaptive_get_export_route(export_job_id: str, session: Session = Depends(get_session)) -> ExportJobResponse:
    job = adaptive_service.get_export_job(session, export_job_id)
    return ExportJobResponse(export_job_id=job.id, status=job.status, file_path=job.file_path)


# --- Study flow APIs (Pre → Cycle1..3 → Post) ---


@router.post("/api/runs/start", response_model=RunStartResponse)
def start_run_route(payload: RunStartRequest, session: Session = Depends(get_session)) -> RunStartResponse:
    run = start_run(session, user_id=payload.user_id, group=payload.group, cycle_count=payload.cycle_count)
    return RunStartResponse(
        run_id=run.id,
        user_id=run.user_id,
        group=run.group,
        skills_enabled=run.skills_enabled,
        cycle_count=run.cycle_count,
        created_at=run.created_at,
    )


@router.post("/api/runs/finish", response_model=RunFinishResponse)
def finish_run_route(payload: RunFinishRequest, session: Session = Depends(get_session)) -> RunFinishResponse:
    run = finish_run(session, payload.run_id)
    if not run.finished_at:
        raise HTTPException(status_code=500, detail="Run finish failed")
    return RunFinishResponse(run_id=run.id, finished_at=run.finished_at)


@router.post("/api/materials/next", response_model=MaterialResponse)
def material_next_route(payload: MaterialNextRequest, session: Session = Depends(get_session)) -> MaterialResponse:
    study_run = session.get(StudyRun, payload.run_id)
    if not study_run:
        raise HTTPException(status_code=404, detail="Run not found")
    material = get_or_create_material(session, study_run, payload.cycle_index)
    return MaterialResponse(
        material_id=material.id,
        run_id=material.run_id,
        cycle_index=material.cycle_index,
        group=study_run.group,
        source_type=material.source_type,  # type: ignore[arg-type]
        content_text=material.content_text,
        difficulty=material.difficulty,
        created_at=material.created_at,
    )


@router.post("/api/materials/read_confirm", response_model=MaterialReadConfirmResponse)
def material_read_confirm_route(
    payload: MaterialReadConfirmRequest, session: Session = Depends(get_session)
) -> MaterialReadConfirmResponse:
    read = confirm_material_read(
        session,
        run_id=payload.run_id,
        material_id=payload.material_id,
        presented_at=payload.presented_at,
        read_confirmed_at=payload.read_confirmed_at,
    )
    return MaterialReadConfirmResponse(material_read_id=read.id, duration_seconds=read.duration_seconds)


@router.post("/api/assessments/start", response_model=AssessmentStartResponse)
def assessment_start_route(payload: AssessmentStartRequest, session: Session = Depends(get_session)) -> AssessmentStartResponse:
    attempt = start_assessment(session, payload.run_id, payload.assessment_type, payload.cycle_index)
    assessment = session.get(StudyAssessment, attempt.assessment_id)
    if not assessment:
        raise HTTPException(status_code=500, detail="Assessment missing")
    return AssessmentStartResponse(
        assessment_attempt_id=attempt.id,
        assessment_id=attempt.assessment_id,
        assessment_type=attempt.assessment_type,  # type: ignore[arg-type]
        cycle_index=attempt.cycle_index,
        started_at=attempt.started_at,
        content_json=assessment.content_json,
    )


@router.post("/api/assessments/submit", response_model=AssessmentSubmitResponse)
def assessment_submit_route(
    payload: AssessmentSubmitRequest, session: Session = Depends(get_session)
) -> AssessmentSubmitResponse:
    attempt = submit_assessment(
        session,
        attempt_id=payload.assessment_attempt_id,
        submitted_at=payload.submitted_at,
        answers=[answer.model_dump() for answer in payload.answers],
    )
    per_question = attempt.result_json.get("per_question_correct", [])
    return AssessmentSubmitResponse(
        assessment_attempt_id=attempt.id,
        submitted_at=attempt.submitted_at or payload.submitted_at,
        duration_seconds=attempt.duration_seconds or 0,
        score=attempt.score or 0,
        max_score=attempt.max_score or 0,
        per_question_correct=per_question,
    )


@router.post("/api/mastery/estimate", response_model=MasteryEstimateResponse)
def mastery_estimate_route(
    payload: MasteryEstimateRequest, session: Session = Depends(get_session)
) -> MasteryEstimateResponse:
    estimate = estimate_mastery(session, payload.run_id, payload.cycle_index)
    return MasteryEstimateResponse(
        mastery_estimate_id=estimate.id,
        run_id=estimate.run_id,
        cycle_index=estimate.cycle_index,
        estimate_json=estimate.estimate_json,
        created_at=estimate.created_at,
    )


@router.post("/api/chat/ask", response_model=ChatAskResponse)
def chat_ask_route(payload: ChatAskRequest, session: Session = Depends(get_session)) -> ChatAskResponse:
    turn = chat_ask(session, payload.run_id, payload.material_id, payload.question_text)
    return ChatAskResponse(chat_turn_id=turn.id, answer_text=turn.answer_text, created_at=turn.created_at)


@router.post("/api/auth/register", response_model=AuthUserResponse)
def register_route(payload: AuthRegisterRequest, response: Response, session: Session = Depends(get_session)) -> AuthUserResponse:
    try:
        user, revision, token = register_user(
            session,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
            settings=get_settings(),
        )
    except DuplicateUsernameError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_auth_cookie(response, token)
    return _auth_user_response(user, revision.id)


@router.post("/api/auth/login", response_model=AuthUserResponse)
def login_route(payload: AuthLoginRequest, response: Response, session: Session = Depends(get_session)) -> AuthUserResponse:
    try:
        user, revision, token = login_user(session, username=payload.username, password=payload.password, settings=get_settings())
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_auth_cookie(response, token)
    return _auth_user_response(user, revision.id if revision else None)


@router.get("/api/auth/me", response_model=AuthUserResponse)
def me_route(current_user: User = Depends(require_current_user), session: Session = Depends(get_session)) -> AuthUserResponse:
    _user, _skill, revision = get_user_with_skill(session, current_user.id)
    return _auth_user_response(current_user, revision.id if revision else None)


@router.post("/api/auth/logout")
def logout_route(request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    settings = get_settings()
    token = request.cookies.get(settings.auth_cookie_name)
    if token:
        logout_session(session, token)
    _clear_auth_cookie(response)
    return {"status": "ok"}


@router.post("/api/users", response_model=UserResponse)
def create_user_route(payload: UserCreateRequest, session: Session = Depends(get_session)) -> UserResponse:
    user, revision = create_user(session, payload.display_name)
    return UserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
        active_skill_revision_id=revision.id,
    )


@router.get("/api/users/{user_id}", response_model=UserResponse)
def get_user_route(user_id: str, session: Session = Depends(get_session)) -> UserResponse:
    user, _skill, revision = get_user_with_skill(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
        active_skill_revision_id=revision.id if revision else None,
    )


@router.get("/api/users/{user_id}/skills", response_model=SkillSummaryResponse)
def get_user_skills_route(user_id: str, session: Session = Depends(get_session)) -> SkillSummaryResponse:
    user, skill, revision = get_user_with_skill(session, user_id)
    if not user or not skill:
        raise HTTPException(status_code=404, detail="User not found")
    revisions = get_skill_history(session, user_id)
    return SkillSummaryResponse(
        skill_id=skill.id,
        active_revision_id=skill.active_revision_id,
        active_profile=revision.profile_json if revision else {},
        revisions=[
            {
                "revision_id": item.id,
                "revision_number": item.revision_number,
                "summary_rule": item.summary_rule,
                "update_reason": item.update_reason,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
    )


@router.post("/api/documents/upload", response_model=DocumentResponse)
def upload_document_route(file: UploadFile = File(...), session: Session = Depends(get_session)) -> DocumentResponse:
    document = create_document(session, file)
    return _document_response(session, document)


@router.post("/api/documents/{document_id}/ingest", response_model=IngestJobResponse)
def ingest_document_route(document_id: str, session: Session = Depends(get_session)) -> IngestJobResponse:
    job = create_ingestion_job(session, document_id)
    return IngestJobResponse(ingestion_job_id=job.id, status=job.status)


@router.get("/api/documents", response_model=list[DocumentResponse])
def list_documents_route(session: Session = Depends(get_session)) -> list[DocumentResponse]:
    return [_document_response(session, document) for document in list_documents(session)]


@router.get("/api/documents/{document_id}/chunks", response_model=list[DocumentChunkResponse])
def list_document_chunks_route(document_id: str, session: Session = Depends(get_session)) -> list[DocumentChunkResponse]:
    return [
        DocumentChunkResponse(
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            metadata=chunk.metadata_json,
            has_embedding=has_embedding,
        )
        for chunk, has_embedding in list_chunks(session, document_id)
    ]


@router.get("/api/documents/{document_id}/skill", response_model=DocumentSkillResponse)
def get_document_skill_route(document_id: str, session: Session = Depends(get_session)) -> DocumentSkillResponse:
    try:
        document, document_skill, revision = get_document_skill(session, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    entries_count = len(list_document_skill_entries(session, document_id)) if revision else 0
    return DocumentSkillResponse(
        document_id=document.id,
        filename=document.filename,
        document_skill_id=document_skill.id if document_skill else None,
        active_revision_id=revision.id if revision else None,
        status=document_skill.status if document_skill else None,
        revision_number=revision.revision_number if revision else None,
        profile_json=revision.profile_json if revision else None,
        entries_count=entries_count,
        updated_at=document_skill.updated_at if document_skill else None,
    )


@router.get("/api/documents/{document_id}/skill/revisions", response_model=list[DocumentSkillRevisionResponse])
def list_document_skill_revisions_route(
    document_id: str,
    session: Session = Depends(get_session),
) -> list[DocumentSkillRevisionResponse]:
    try:
        revisions = list_document_skill_revisions(session, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        DocumentSkillRevisionResponse(
            revision_id=revision.id,
            revision_number=revision.revision_number,
            summary=revision.summary,
            extraction_model_name=revision.extraction_model_name,
            prompt_version=revision.prompt_version,
            source_digest=revision.source_digest,
            update_reason=revision.update_reason,
            created_at=revision.created_at,
        )
        for revision in revisions
    ]


@router.get("/api/documents/{document_id}/skill/entries", response_model=list[DocumentSkillEntryResponse])
def list_document_skill_entries_route(
    document_id: str,
    session: Session = Depends(get_session),
) -> list[DocumentSkillEntryResponse]:
    try:
        entries = list_document_skill_entries(session, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [
        DocumentSkillEntryResponse(
            entry_id=entry.id,
            revision_id=entry.document_skill_revision_id,
            entry_type=entry.entry_type,
            title=entry.title,
            content=entry.content,
            source_page=entry.source_page,
            source_span=entry.source_span,
            confidence=entry.confidence,
            metadata=entry.metadata_json,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.delete("/api/documents/{document_id}", response_model=DocumentDeleteResponse)
def delete_document_route(document_id: str, session: Session = Depends(get_session)) -> DocumentDeleteResponse:
    try:
        delete_document(session, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete document file: {exc}") from exc
    return DocumentDeleteResponse(document_id=document_id, deleted=True)


@router.post("/api/chat/generate", response_model=ChatGenerateResponse)
def generate_chat_route(
    payload: ChatGenerateRequest,
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session),
) -> ChatGenerateResponse:
    try:
        result = generate_candidates_for_chat(session, payload, authenticated_user_id=current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatGenerateResponse(
        session_id=result["session_id"],
        chat_message_id=result["chat_message_id"],
        generation_run_id=result["generation_run_id"],
        skills_enabled=result["skills_enabled"],
        active_skill_revision_id=result["active_skill_revision_id"],
        retrievals=[
            {
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "filename": row["filename"],
                "chunk_index": row["chunk_index"],
                "score": row["score"],
                "text": row["text"],
            }
            for row in result["retrievals"]
        ],
        document_skill_contexts=result["document_skill_contexts"],
        candidates=[
            {
                "candidate_id": candidate.id,
                "title": candidate.title,
                "style_tags": candidate.style_tags,
                "answer_text": candidate.answer_text,
                "rank": candidate.rank,
                "display_order": candidate.display_order,
            }
            for candidate in result["candidates"]
        ],
    )


@router.post("/api/chat/select", response_model=ChatSelectResponse)
def select_chat_route(
    payload: ChatSelectRequest,
    current_user: User = Depends(require_current_user),
    session: Session = Depends(get_session),
) -> ChatSelectResponse:
    try:
        result = select_candidate_for_chat(session, payload, authenticated_user_id=current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChatSelectResponse(**result)


@router.get("/api/chat/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session_route(session_id: str, session: Session = Depends(get_session)) -> SessionDetailResponse:
    try:
        detail = get_session_detail(session, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionDetailResponse(**detail)


@router.get("/api/chat/logs/{user_id}")
def get_logs_route(user_id: str, session: Session = Depends(get_session)):
    return get_user_logs(session, user_id)


@router.get("/api/chat/turns/{chat_message_id}")
def get_turn_route(chat_message_id: str, session: Session = Depends(get_session)):
    try:
        return get_turn_detail(session, chat_message_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/admin/skills/recompute/{user_id}", response_model=AdminRecomputeResponse)
def recompute_skills_route(user_id: str, session: Session = Depends(get_session)) -> AdminRecomputeResponse:
    user, _skill, _revision = get_user_with_skill(session, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    latest_selection = session.execute(
        text(
            """
            SELECT selection.id, message.id AS chat_message_id
            FROM answer_selections AS selection
            JOIN chat_messages AS message ON message.id = selection.chat_message_id
            WHERE message.user_id = :user_id
            ORDER BY selection.created_at DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    ).mappings().first()
    if not latest_selection:
        raise HTTPException(status_code=400, detail="No selection history available")
    from app.models.entities import SkillUpdateJob, utcnow

    new_job = SkillUpdateJob(
        user_id=user_id,
        chat_message_id=latest_selection["chat_message_id"],
        selection_id=latest_selection["id"],
        job_type="skill_update",
        status="pending",
        attempt_count=0,
        payload_json={"source": "admin_recompute"},
        updated_at=utcnow(),
    )
    session.add(new_job)
    session.commit()
    return AdminRecomputeResponse(skill_update_job_id=new_job.id, status=new_job.status)


@router.get("/api/admin/runtime", response_model=RuntimeProviderResponse)
def get_runtime_route() -> RuntimeProviderResponse:
    settings = get_settings()
    embedding_model = (
        settings.gemini_model_embed
        if settings.embedding_provider == "gemini"
        else settings.local_embed_model
        if settings.embedding_provider in {"local-sentence-transformers", "local-http"}
        else "mock-embedding"
    )
    return RuntimeProviderResponse(
        generation_provider=settings.active_generation_provider,
        embedding_provider=settings.embedding_provider,
        generation_model=get_generation_model_name(settings),
        embedding_model=embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        local_embed_device=settings.local_embed_device,
    )


@router.get("/api/admin/skills/history/{user_id}", response_model=SkillHistoryResponse)
def get_skill_history_route(user_id: str, session: Session = Depends(get_session)) -> SkillHistoryResponse:
    try:
        revisions = get_skill_history(session, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillHistoryResponse(
        user_id=user_id,
        revisions=[
            {
                "revision_id": item.id,
                "revision_number": item.revision_number,
                "summary_rule": item.summary_rule,
                "update_reason": item.update_reason,
                "profile_json": item.profile_json,
                "source_selection_id": item.source_selection_id,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
    )


@router.post("/api/experiments/runs", response_model=ExperimentRunResponse)
def create_experiment_run_route(payload: ExperimentRunCreateRequest, session: Session = Depends(get_session)) -> ExperimentRunResponse:
    run = create_experiment_run(session, payload)
    return ExperimentRunResponse(
        run_id=run.id,
        user_id=run.user_id,
        chat_message_id=run.chat_message_id,
        condition_name=run.condition_name,
        skills_enabled=run.skills_enabled,
        candidate_count=run.candidate_count,
        notes=run.notes,
        created_at=run.created_at,
    )


@router.get("/api/experiments/runs", response_model=list[ExperimentRunResponse])
def list_experiment_runs_route(session: Session = Depends(get_session)) -> list[ExperimentRunResponse]:
    runs = list_experiment_runs(session)
    return [
        ExperimentRunResponse(
            run_id=run.id,
            user_id=run.user_id,
            chat_message_id=run.chat_message_id,
            condition_name=run.condition_name,
            skills_enabled=run.skills_enabled,
            candidate_count=run.candidate_count,
            notes=run.notes,
            created_at=run.created_at,
        )
        for run in runs
    ]


@router.get("/api/experiments/runs/{run_id}", response_model=ExperimentRunResponse)
def get_experiment_run_route(run_id: str, session: Session = Depends(get_session)) -> ExperimentRunResponse:
    runs = {run.id: run for run in list_experiment_runs(session)}
    run = runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Experiment run not found")
    return ExperimentRunResponse(
        run_id=run.id,
        user_id=run.user_id,
        chat_message_id=run.chat_message_id,
        condition_name=run.condition_name,
        skills_enabled=run.skills_enabled,
        candidate_count=run.candidate_count,
        notes=run.notes,
        created_at=run.created_at,
    )


@router.get("/api/experiments/exports/logs.zip")
def export_logs_route(session: Session = Depends(get_session)):
    path = export_logs_zip(session)
    return FileResponse(path, media_type="application/zip", filename="logs_export.zip")


def _document_response(session: Session, document) -> DocumentResponse:
    try:
        _document, document_skill, revision = get_document_skill(session, document.id)
        entries_count = len(list_document_skill_entries(session, document.id)) if revision else 0
    except ValueError:
        document_skill = None
        revision = None
        entries_count = 0
    return DocumentResponse(
        document_id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        source_type=document.source_type,
        ingest_status=document.ingest_status,
        created_at=document.created_at,
        document_skill_status=document_skill.status if document_skill else None,
        active_document_skill_revision_id=revision.id if revision else None,
        document_skill_revision_number=revision.revision_number if revision else None,
        document_skill_entries_count=entries_count,
        document_skill_updated_at=document_skill.updated_at if document_skill else None,
    )
