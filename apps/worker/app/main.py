from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.jobs import process_pending_jobs

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("Worker started")
    while True:
        session = SessionLocal()
        try:
            logger.info("Polling pending jobs")
            process_pending_jobs(session, settings.job_batch_size)
        except Exception:
            logger.exception("Worker polling loop failed")
        finally:
            session.close()
        time.sleep(settings.skill_updater_poll_interval_seconds)


if __name__ == "__main__":
    main()
