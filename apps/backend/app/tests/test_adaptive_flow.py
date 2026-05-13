from __future__ import annotations

from io import BytesIO

from app.models.entities import Embedding, GenerationLog, RetrievalLog


def _answer_all_correct(client, path: str) -> list[dict]:
    response = client.get(path)
    assert response.status_code == 200
    payload = response.json()
    return [
        {"question_id": question["question_id"], "answer": question["correct_answer"]}
        for question in payload["questions"]
    ]


def test_adaptive_e2e_flow_without_runtime_retrieval(client, session) -> None:
    register = client.post(
        "/api/auth/register",
        json={"username": "adaptive", "password": "password123", "display_name": "Adaptive"},
    )
    assert register.status_code == 200
    user_id = register.json()["user_id"]

    upload = client.post(
        "/api/admin/documents/upload",
        data={"title": "代数教材"},
        files={
            "file": (
                "algebra.txt",
                BytesIO(("一次方程式と二次方程式を学ぶ教材です。" * 20).encode()),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    extract = client.post(f"/api/admin/documents/{document_id}/extract-skill")
    assert extract.status_code == 200
    assert extract.json()["entry_count"] > 0

    run = client.post("/api/runs/start", json={"user_id": user_id, "document_id": document_id, "cycle_count": 10})
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    initial_generate = client.post(f"/api/runs/{run_id}/initial-test/generate")
    assert initial_generate.status_code == 200
    assert initial_generate.json()["question_count"] == 20
    initial_answers = _answer_all_correct(client, f"/api/runs/{run_id}/initial-test")
    initial_submit = client.post(f"/api/runs/{run_id}/initial-test/submit", json={"answers": initial_answers})
    assert initial_submit.status_code == 200
    assert initial_submit.json()["learner_skill_revision_id"]

    seen_fingerprints: set[str] = set()
    for cycle_index in range(1, 11):
        material_generate = client.post(f"/api/runs/{run_id}/cycles/{cycle_index}/material/generate")
        assert material_generate.status_code == 200
        read = client.post(f"/api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm")
        assert read.status_code == 200
        test_generate = client.post(f"/api/runs/{run_id}/cycles/{cycle_index}/test/generate")
        assert test_generate.status_code == 200
        assert test_generate.json()["question_count"] == 10
        test_payload = client.get(f"/api/runs/{run_id}/cycles/{cycle_index}/test").json()
        fingerprints = {question["fingerprint"] for question in test_payload["questions"]}
        assert not (fingerprints & seen_fingerprints)
        seen_fingerprints.update(fingerprints)
        answers = [{"question_id": q["question_id"], "answer": q["correct_answer"]} for q in test_payload["questions"]]
        submit = client.post(f"/api/runs/{run_id}/cycles/{cycle_index}/test/submit", json={"answers": answers})
        assert submit.status_code == 200

    final_generate = client.post(f"/api/runs/{run_id}/final-test/generate")
    assert final_generate.status_code == 200
    assert final_generate.json()["question_count"] == 20
    final_answers = _answer_all_correct(client, f"/api/runs/{run_id}/final-test")
    final_submit = client.post(f"/api/runs/{run_id}/final-test/submit", json={"answers": final_answers})
    assert final_submit.status_code == 200
    assert final_submit.json()["state"] == "RESULT_READY"

    results = client.get(f"/api/runs/{run_id}/results")
    assert results.status_code == 200
    assert results.json()["final_score"] == 20

    export = client.post(f"/api/admin/exports/runs/{run_id}")
    assert export.status_code == 200
    assert export.json()["status"] == "completed"

    invalid = client.post(f"/api/runs/{run_id}/final-test/generate")
    assert invalid.status_code == 409
    assert session.query(Embedding).count() == 0
    assert session.query(RetrievalLog).count() == 0
    assert session.query(GenerationLog).count() > 0


def test_document_skill_extraction_rejects_unextractable_pdf_text(client) -> None:
    upload = client.post(
        "/api/admin/documents/upload",
        data={"title": "空PDF相当"},
        files={"file": ("empty.txt", BytesIO(b""), "text/plain")},
    )
    assert upload.status_code == 200
    document_id = upload.json()["document_id"]

    extract = client.post(f"/api/admin/documents/{document_id}/extract-skill")
    assert extract.status_code == 422
    assert "十分なテキスト" in extract.text
