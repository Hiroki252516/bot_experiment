from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["GENERATION_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["UPLOAD_DIR"] = "/tmp/tutorbot-test/uploads"
os.environ["EXPORT_DIR"] = "/tmp/tutorbot-test/exports"
os.environ["HF_HOME"] = "/tmp/tutorbot-test/model_cache/huggingface"
os.environ["TRANSFORMERS_CACHE"] = "/tmp/tutorbot-test/model_cache/huggingface/transformers"
os.environ["SENTENCE_TRANSFORMERS_HOME"] = "/tmp/tutorbot-test/model_cache/sentence-transformers"

from app.db.base import Base
from app.db.session import get_session
from app.main import create_app


@pytest.fixture()
def session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(session: Session) -> TestClient:
    app = create_app()

    def override_get_session():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


@pytest.fixture(autouse=True)
def ensure_dirs() -> None:
    Path("/tmp/tutorbot-test/uploads").mkdir(parents=True, exist_ok=True)
    Path("/tmp/tutorbot-test/exports").mkdir(parents=True, exist_ok=True)
    Path("/tmp/tutorbot-test/model_cache/huggingface/transformers").mkdir(parents=True, exist_ok=True)
    Path("/tmp/tutorbot-test/model_cache/sentence-transformers").mkdir(parents=True, exist_ok=True)
