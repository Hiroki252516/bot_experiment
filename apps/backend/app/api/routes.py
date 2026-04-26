from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.core.config import get_settings
from app.llm.providers import get_generation_model_name
from app.models.entities import User
from app.schemas.admin import (
    AdminRecomputeResponse,
    ExperimentRunCreateRequest,
    ExperimentRunResponse,
    RuntimeProviderResponse,
    SkillHistoryResponse,
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
from app.services.documents import create_document, create_ingestion_job, delete_document, list_chunks, list_documents
from app.services.experiments import create_experiment_run, export_logs_zip, list_experiment_runs
from app.services.users import create_user, get_user_with_skill

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
    return DocumentResponse(
        document_id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        source_type=document.source_type,
        ingest_status=document.ingest_status,
        created_at=document.created_at,
    )


@router.post("/api/documents/{document_id}/ingest", response_model=IngestJobResponse)
def ingest_document_route(document_id: str, session: Session = Depends(get_session)) -> IngestJobResponse:
    job = create_ingestion_job(session, document_id)
    return IngestJobResponse(ingestion_job_id=job.id, status=job.status)


@router.get("/api/documents", response_model=list[DocumentResponse])
def list_documents_route(session: Session = Depends(get_session)) -> list[DocumentResponse]:
    return [
        DocumentResponse(
            document_id=document.id,
            filename=document.filename,
            mime_type=document.mime_type,
            source_type=document.source_type,
            ingest_status=document.ingest_status,
            created_at=document.created_at,
        )
        for document in list_documents(session)
    ]


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
