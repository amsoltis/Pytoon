"""Database models (SQLAlchemy) and session management."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    Boolean,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from pytoon.config import get_settings
from pytoon.models import JobStatus, SegmentStatus


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "jobs"

    id = Column(String(64), primary_key=True)
    status = Column(String(32), default=JobStatus.QUEUED.value, nullable=False)
    archetype = Column(String(32), nullable=False)
    preset_id = Column(String(64), nullable=False)
    brand_safe = Column(Boolean, default=True)
    engine_policy = Column(String(32), default="local_preferred")
    target_duration_seconds = Column(Integer, default=15)
    render_spec_json = Column(Text, default="{}")
    output_uri = Column(String(512), nullable=True)
    thumbnail_uri = Column(String(512), nullable=True)
    metadata_uri = Column(String(512), nullable=True)
    fallback_used = Column(Boolean, default=False)
    fallback_reason = Column(String(512), nullable=True)
    error = Column(Text, nullable=True)
    progress_pct = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class SegmentRow(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), nullable=False, index=True)
    index = Column(Integer, nullable=False)
    status = Column(String(32), default=SegmentStatus.PENDING.value)
    duration_seconds = Column(Float, default=3.0)
    prompt = Column(Text, default="")
    engine_used = Column(String(64), nullable=True)
    artifact_uri = Column(String(512), nullable=True)
    seed = Column(Integer, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


# ---------------------------------------------------------------------------
# Engine / session factory
# ---------------------------------------------------------------------------

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False}
            if settings.db_url.startswith("sqlite")
            else {},
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


def init_db():
    """Create all tables (idempotent)."""
    Base.metadata.create_all(bind=get_engine())


def get_db() -> Session:  # type: ignore[misc]
    """Dependency for FastAPI — yields a session then closes."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()
