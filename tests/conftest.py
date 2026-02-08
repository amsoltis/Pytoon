"""Shared test fixtures."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Override env before importing anything from pytoon
os.environ["DB_URL"] = "sqlite://"  # in-memory
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["API_KEY"] = "test-key"
os.environ["STORAGE_ROOT"] = tempfile.mkdtemp()
os.environ["COMFYUI_BASE_URL"] = "http://localhost:8188"

from pytoon.config import get_settings, Settings
from pytoon.db import Base, get_db
from pytoon.api_orchestrator.app import create_app
from pytoon.engine_adapters.base import SegmentResult


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db_engine) -> Generator[TestClient, None, None]:
    import pytoon.db as _db_mod

    # Patch the global db engine so init_db() and any internal usage
    # share the same in-memory database as the fixture
    old_engine = _db_mod._engine
    old_session = _db_mod._SessionLocal
    _db_mod._engine = db_engine
    _db_mod._SessionLocal = sessionmaker(bind=db_engine, expire_on_commit=False)

    app = create_app()
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    def _override_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db

    with TestClient(app) as c:
        yield c

    # Restore
    _db_mod._engine = old_engine
    _db_mod._SessionLocal = old_session


@pytest.fixture()
def auth_headers():
    return {"X-API-Key": "test-key"}


# ---------------------------------------------------------------------------
# Mock engine that always succeeds
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_engine_success(tmp_path):
    """An engine adapter mock that returns success with a fake video file."""
    fake_video = tmp_path / "fake_segment.mp4"
    fake_video.write_bytes(b"\x00" * 1024)  # fake bytes

    adapter = AsyncMock()
    adapter.name = "mock_engine"
    adapter.health_check = AsyncMock(return_value=True)
    adapter.render_segment = AsyncMock(return_value=SegmentResult(
        success=True,
        artifact_path=str(fake_video),
        engine_name="mock_engine",
        seed=42,
        elapsed_ms=100.0,
    ))
    adapter.get_capabilities = MagicMock(return_value={
        "name": "mock_engine",
        "type": "local",
        "archetypes": ["PRODUCT_HERO", "OVERLAY", "MEME_TEXT"],
        "max_segment_duration": 4,
    })
    return adapter


# ---------------------------------------------------------------------------
# Mock engine that always fails
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_engine_fail():
    adapter = AsyncMock()
    adapter.name = "mock_fail"
    adapter.health_check = AsyncMock(return_value=False)
    adapter.render_segment = AsyncMock(return_value=SegmentResult(
        success=False,
        engine_name="mock_fail",
        elapsed_ms=50.0,
        error="Engine unavailable",
    ))
    adapter.get_capabilities = MagicMock(return_value={
        "name": "mock_fail",
        "type": "local",
        "archetypes": [],
    })
    return adapter


# ---------------------------------------------------------------------------
# Storage helper
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage_root(tmp_path):
    root = tmp_path / "storage"
    root.mkdir()
    os.environ["STORAGE_ROOT"] = str(root)
    return root
