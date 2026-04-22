from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.entities import IngestionJob, RagDocument
from app.services.users import create_user


def main() -> None:
    session: Session = SessionLocal()
    try:
        user, revision = create_user(session, "Sample Learner")
        print(f"Seeded user: {user.id} active_skill_revision={revision.id}")
        docs = session.query(RagDocument).count()
        jobs = session.query(IngestionJob).count()
        print(f"Documents: {docs}, ingestion jobs: {jobs}")
    finally:
        session.close()


if __name__ == "__main__":
    main()

