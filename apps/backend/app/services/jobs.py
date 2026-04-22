from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import IngestionJob, SkillUpdateJob, utcnow
from app.services.documents import process_ingestion_job
from app.services.skills import process_skill_update_job

logger = logging.getLogger(__name__)


def process_pending_jobs(session: Session, batch_size: int) -> None:
    ingestion_jobs = list(
        session.scalars(
            select(IngestionJob)
            .where(IngestionJob.status == "pending")
            .order_by(IngestionJob.created_at.asc())
            .limit(batch_size)
        )
    )
    for job in ingestion_jobs:
        try:
            process_ingestion_job(session, job)
        except Exception as exc:
            session.rollback()
            failed_job = session.get(IngestionJob, job.id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)
                failed_job.updated_at = utcnow()
                session.commit()
            logger.exception("Failed ingestion job %s", job.id)

    skill_jobs = list(
        session.scalars(
            select(SkillUpdateJob)
            .where(SkillUpdateJob.status == "pending")
            .order_by(SkillUpdateJob.created_at.asc())
            .limit(batch_size)
        )
    )
    for job in skill_jobs:
        try:
            process_skill_update_job(session, job)
        except Exception as exc:
            session.rollback()
            failed_job = session.get(SkillUpdateJob, job.id)
            if failed_job:
                failed_job.status = "failed"
                failed_job.error_message = str(exc)
                failed_job.updated_at = utcnow()
                session.commit()
            logger.exception("Failed skill update job %s", job.id)

