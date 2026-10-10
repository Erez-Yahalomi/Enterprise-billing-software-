import os

# Hermetic tests: real environment variables outrank .env in pydantic-settings, so pin the
# AI/infra settings here before the app (and its cached settings) are imported. Otherwise a
# developer's .env (AI_PROVIDER=gemini + real key) would make the suite call live Gemini.
os.environ.update({"AI_PROVIDER": "mock", "GEMINI_API_KEY": "", "USAGE_PIPELINE": "sync", "OPA_MODE": "embedded"})

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import model_registry  # noqa: F401  (registers all models on Base.metadata)
from app.core.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def isolated_lake(tmp_path, monkeypatch):
    # The sync usage publisher writes Parquet files; keep them out of the real ./data/lake.
    from app.core.config import get_settings

    monkeypatch.setenv("LAKE_PATH", str(tmp_path / "lake"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    # StaticPool: every session must share the same underlying connection, otherwise
    # each new connection to sqlite:///:memory: would see a separate, empty database.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        test_client.session_factory = TestingSessionLocal
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
