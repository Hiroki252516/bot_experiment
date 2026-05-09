from __future__ import annotations

import zipfile
from io import BytesIO

from sqlalchemy import select

from app.models.entities import (
    DocumentSkillEntry,
    DocumentSkillRevision,
    DocumentSkillUsageLog,
    Embedding,
    IngestionJob,
)
from app.services.documents import process_ingestion_job
from app.services.experiments import export_logs_zip


def _register_and_ingest_document(client, session) -> tuple[str, str]:
    register_response = client.post(
        "/api/auth/register",
        json={"username": "docskill-user", "password": "password123", "display_name": "Doc Skill User"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]
    upload_response = client.post(
        "/api/documents/upload",
        files={
            "file": (
                "programming.md",
                BytesIO("第1回課題\n\n01というフォルダを作成し、エディタで作成したHTMLファイルを提出する。拡張子は .html。".encode()),
                "text/markdown",
            )
        },
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]
    ingest_response = client.post(f"/api/documents/{document_id}/ingest")
    assert ingest_response.status_code == 200
    ingestion_job = session.get(IngestionJob, ingest_response.json()["ingestion_job_id"])
    process_ingestion_job(session, ingestion_job)
    return user_id, document_id


def test_ingestion_creates_document_skill_entries_without_embeddings(client, session) -> None:
    _user_id, document_id = _register_and_ingest_document(client, session)

    revisions = list(session.scalars(select(DocumentSkillRevision)))
    entries = list(session.scalars(select(DocumentSkillEntry)))
    assert len(revisions) == 1
    assert entries
    assert session.query(Embedding).count() == 0

    response = client.get(f"/api/documents/{document_id}/skill/entries")
    assert response.status_code == 200
    assert any("HTML" in entry["content"] for entry in response.json())


def test_chat_uses_document_skill_context_without_runtime_retrieval(client, session, monkeypatch) -> None:
    _user_id, document_id = _register_and_ingest_document(client, session)

    def forbidden(*args, **kwargs):
        raise AssertionError("legacy runtime retrieval/embedding must not be called")

    monkeypatch.setattr("app.embeddings.providers.get_embedding_provider", forbidden)
    monkeypatch.setattr("app.rag.retrieval.retrieve_chunks", forbidden)

    response = client.post(
        "/api/chat/generate",
        json={
            "question": "基礎プログラミング演習の第一回課題の内容を教えて",
            "candidate_count": 3,
            "skills_enabled": False,
            "document_skills_enabled": True,
            "document_ids": [document_id],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrievals"] == []
    assert payload["active_skill_revision_id"] is None
    assert payload["document_skill_contexts"][0]["document_id"] == document_id
    assert session.query(DocumentSkillUsageLog).count() > 0


def test_document_skills_disabled_omits_context_and_usage_logs(client, session) -> None:
    _user_id, document_id = _register_and_ingest_document(client, session)

    response = client.post(
        "/api/chat/generate",
        json={
            "question": "この教材の課題は？",
            "candidate_count": 3,
            "document_skills_enabled": False,
            "document_ids": [document_id],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_skill_contexts"] == []
    assert session.query(DocumentSkillUsageLog).count() == 0


def test_export_includes_document_skill_csvs(client, session) -> None:
    _user_id, document_id = _register_and_ingest_document(client, session)
    client.post(
        "/api/chat/generate",
        json={
            "question": "この教材の課題は？",
            "candidate_count": 3,
            "document_ids": [document_id],
        },
    )

    export_path = export_logs_zip(session)
    with zipfile.ZipFile(export_path) as archive:
        names = set(archive.namelist())
        assert "document_skill_revisions.csv" in names
        assert "document_skill_entries.csv" in names
        assert "document_skill_usage_logs.csv" in names
        assert "retrievals.csv" in names
        assert "deprecated" in archive.read("retrievals.csv").decode()


def test_study_material_and_assessment_use_uploaded_document_skill(client, session) -> None:
    user_id, _document_id = _register_and_ingest_document(client, session)
    run_response = client.post("/api/runs/start", json={"user_id": user_id, "group": "A", "cycle_count": 3})
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    material_response = client.post("/api/materials/next", json={"run_id": run_id, "cycle_index": 1})
    assert material_response.status_code == 200
    material_payload = material_response.json()
    assert "HTML" in material_payload["content_text"]

    pre_response = client.post(
        "/api/assessments/start",
        json={"run_id": run_id, "assessment_type": "pre_test", "cycle_index": None},
    )
    assert pre_response.status_code == 200
    pre_questions = pre_response.json()["content_json"]["questions"]
    assert pre_questions
    assert any("HTML" in choice for question in pre_questions for choice in question["choices"])

    mini_response = client.post(
        "/api/assessments/start",
        json={"run_id": run_id, "assessment_type": "mini_test", "cycle_index": 1},
    )
    assert mini_response.status_code == 200
    mini_questions = mini_response.json()["content_json"]["questions"]
    assert mini_questions
    assert all(len(question["choices"]) == 4 for question in mini_questions)


def test_study_material_requires_completed_document_skill_context(client) -> None:
    register_response = client.post(
        "/api/auth/register",
        json={"username": "study-no-doc", "password": "password123", "display_name": "No Doc"},
    )
    assert register_response.status_code == 200
    user_id = register_response.json()["user_id"]
    run_response = client.post("/api/runs/start", json={"user_id": user_id, "group": "A", "cycle_count": 3})
    assert run_response.status_code == 200

    material_response = client.post(
        "/api/materials/next",
        json={"run_id": run_response.json()["run_id"], "cycle_index": 1},
    )
    assert material_response.status_code == 409
    assert "Document Skill" in material_response.text
