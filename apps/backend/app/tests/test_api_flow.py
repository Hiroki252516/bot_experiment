from io import BytesIO

from app.models.entities import IngestionJob
from app.services.documents import process_ingestion_job


def test_full_chat_flow(client, session) -> None:
    create_user_response = client.post("/api/users", json={"display_name": "Tester"})
    assert create_user_response.status_code == 200
    user_id = create_user_response.json()["user_id"]

    upload_response = client.post(
        "/api/documents/upload",
        files={"file": ("math.md", BytesIO(b"# Algebra\n\nQuadratic equations can be solved by factoring."), "text/markdown")},
    )
    assert upload_response.status_code == 200
    document_id = upload_response.json()["document_id"]

    ingest_response = client.post(f"/api/documents/{document_id}/ingest")
    assert ingest_response.status_code == 200
    ingestion_job = session.get(IngestionJob, ingest_response.json()["ingestion_job_id"])
    process_ingestion_job(session, ingestion_job)

    generate_response = client.post(
        "/api/chat/generate",
        json={
            "user_id": user_id,
            "question": "How do I solve x^2 + 5x + 6 = 0?",
            "candidate_count": 3,
            "skills_enabled": True,
        },
    )
    assert generate_response.status_code == 200
    payload = generate_response.json()
    assert len(payload["candidates"]) == 3
    assert payload["skills_enabled"] is True
    assert len(payload["retrievals"]) == 1

    selected_candidate_id = payload["candidates"][1]["candidate_id"]
    select_response = client.post(
        "/api/chat/select",
        json={
            "chat_message_id": payload["chat_message_id"],
            "selected_candidate_id": selected_candidate_id,
            "satisfaction_score": 8,
            "clarity_score": 9,
            "comment": "Examples help.",
        },
    )
    assert select_response.status_code == 200
    selection_payload = select_response.json()
    assert selection_payload["status"] == "accepted"

    logs_response = client.get(f"/api/chat/logs/{user_id}")
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["messages"][0]["selection"]["selected_candidate_id"] == selected_candidate_id
