"""
Test fixtures. Each test run uses a fresh, isolated SQLite file
(not the dev database), so tests never pollute real data.
"""
import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///./test_guardianai.db"

_test_media_dir = tempfile.mkdtemp(prefix="guardianai_test_media_")
os.environ["UPLOAD_DIR"] = os.path.join(_test_media_dir, "uploads")
os.environ["EVIDENCE_DIR"] = os.path.join(_test_media_dir, "evidence")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_registry import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_guardianai.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def _fresh_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def db_session():
    """A raw DB session for tests that need to directly inspect/mutate rows
    (e.g. backdating an emergency's created_at to test escalation timing)
    without going through the HTTP API. Points at the same test SQLite file
    the app uses, so commits from either side are visible to the other.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
