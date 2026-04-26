from __future__ import annotations

from io import BytesIO

from sqlalchemy import func, select

from app.models.entities import AuthSession, ChatMessage, IngestionJob, Skill, SkillRevision, User
from app.services.documents import process_ingestion_job


def test_register_creates_user_skill_revision_session_and_cookie(client, session) -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": "learner01", "password": "password123", "display_name": "Learner"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["username"] == "learner01"
    assert payload["display_name"] == "Learner"
    assert response.cookies.get("tutorbot_session")

    user_count = session.scalar(select(func.count()).select_from(User))
    skill_count = session.scalar(select(func.count()).select_from(Skill))
    revision_count = session.scalar(select(func.count()).select_from(SkillRevision))
    auth_session_count = session.scalar(select(func.count()).select_from(AuthSession))
    assert user_count == 1
    assert skill_count == 1
    assert revision_count == 1
    assert auth_session_count == 1


def test_register_duplicate_username_returns_409(client) -> None:
    payload = {"username": "learner02", "password": "password123"}
    assert client.post("/api/auth/register", json=payload).status_code == 200

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409


def test_login_logout_and_me(client) -> None:
    register_response = client.post("/api/auth/register", json={"username": "learner03", "password": "password123"})
    assert register_response.status_code == 200

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "learner03"

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 200
    assert client.get("/api/auth/me").status_code == 401

    failed_login_response = client.post("/api/auth/login", json={"username": "learner03", "password": "wrong"})
    assert failed_login_response.status_code == 401

    login_response = client.post("/api/auth/login", json={"username": "learner03", "password": "password123"})
    assert login_response.status_code == 200
    assert client.get("/api/auth/me").status_code == 200


def test_chat_requires_login(client) -> None:
    generate_response = client.post(
        "/api/chat/generate",
        json={"question": "Explain factoring.", "candidate_count": 3, "skills_enabled": True},
    )
    assert generate_response.status_code == 401

    select_response = client.post(
        "/api/chat/select",
        json={
            "chat_message_id": "missing",
            "selected_candidate_id": "missing",
            "satisfaction_score": 8,
            "clarity_score": 8,
        },
    )
    assert select_response.status_code == 401


def test_select_other_users_message_returns_403(client, session) -> None:
    register_response = client.post("/api/auth/register", json={"username": "owner", "password": "password123"})
    assert register_response.status_code == 200

    upload_response = client.post(
        "/api/documents/upload",
        files={"file": ("math.md", BytesIO(b"# Algebra\n\nQuadratic equations can be solved by factoring."), "text/markdown")},
    )
    document_id = upload_response.json()["document_id"]
    ingest_response = client.post(f"/api/documents/{document_id}/ingest")
    ingestion_job = session.get(IngestionJob, ingest_response.json()["ingestion_job_id"])
    process_ingestion_job(session, ingestion_job)

    generate_response = client.post(
        "/api/chat/generate",
        json={"question": "How do I solve x^2 + 5x + 6 = 0?", "candidate_count": 3, "skills_enabled": True},
    )
    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert session.get(ChatMessage, generated["chat_message_id"])

    assert client.post("/api/auth/logout").status_code == 200
    second_response = client.post("/api/auth/register", json={"username": "intruder", "password": "password123"})
    assert second_response.status_code == 200

    select_response = client.post(
        "/api/chat/select",
        json={
            "chat_message_id": generated["chat_message_id"],
            "selected_candidate_id": generated["candidates"][0]["candidate_id"],
            "satisfaction_score": 8,
            "clarity_score": 8,
        },
    )

    assert select_response.status_code == 403
