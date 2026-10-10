import os

# See tests/conftest.py: keep unit tests hermetic no matter what .env says.
os.environ.update({"AI_PROVIDER": "mock", "GEMINI_API_KEY": "", "USAGE_PIPELINE": "sync", "OPA_MODE": "embedded"})

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import model_registry  # noqa: F401
from app.core.db import Base


@pytest.fixture(autouse=True)
def isolated_lake(tmp_path, monkeypatch):
    # The sync usage publisher and demo seed now write Parquet files; keep them out of ./data/lake.
    from app.core.config import get_settings

    monkeypatch.setenv("LAKE_PATH", str(tmp_path / "lake"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
