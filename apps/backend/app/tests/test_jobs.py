from __future__ import annotations

from app.models.entities import IngestionJob, RagDocument
from app.services import jobs


def test_failed_ingestion_job_marks_document_failed(session, monkeypatch) -> None:
    document = RagDocument(
        filename="failed.pdf",
        mime_type="application/pdf",
        source_type="test",
        storage_path="/tmp/failed.pdf",
        sha256="0" * 64,
        ingest_status="pending",
    )
    session.add(document)
    session.flush()
    job = IngestionJob(document_id=document.id, status="pending")
    session.add(job)
    session.commit()

    def fail_ingestion(_session, _job) -> None:
        raise RuntimeError("embedding failed")

    monkeypatch.setattr(jobs, "process_ingestion_job", fail_ingestion)

    jobs.process_pending_jobs(session, batch_size=10)

    session.refresh(job)
    session.refresh(document)
    assert job.status == "failed"
    assert job.error_message == "embedding failed"
    assert document.ingest_status == "failed"
