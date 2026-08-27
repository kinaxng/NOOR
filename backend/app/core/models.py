"""Database entities and API data models.

Reconstructed from the preserved Python 3.13 bytecode.  SQLAlchemy table and
column definitions intentionally match the existing SQLite database exactly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.tasks.job_phases import get_phase_group


def utcnow() -> datetime:
    """Return a UTC timestamp stored as a timezone-naive SQLite value."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type: Mapped[str] = mapped_column(String(32), default="lada")
    emby_item_id: Mapped[str] = mapped_column(String(64), nullable=False)
    emby_item_name: Mapped[str] = mapped_column(String(512), nullable=False)
    input_path: Mapped[str] = mapped_column(Text, nullable=False)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    phase_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    phase_label: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phase_progress: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chain_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    depends_on_task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=True
    )
    parent_task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("jobs.id"), nullable=True
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    result_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    @property
    def phase_group(self) -> Optional[str]:
        return get_phase_group(self.phase_key)


class EmbyItemCache(Base):
    """Persistent SQLite cache for Emby library items.

    Survives process restarts unlike in-memory dict.
    """

    __tablename__ = "emby_item_cache"

    library_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    items_json: Mapped[str] = mapped_column(Text, nullable=False)


class InstallStatus(Base):
    """Singleton table to track background installation status."""

    __tablename__ = "install_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    status: Mapped[str] = mapped_column(String(32), default="idle")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class JobSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    detection_model: str = "v4-fast"
    restoration_model: str = "basicvsrpp-v1.2"
    encoding_preset: str = "hevc-nvidia-gpu-hq"


class JobCreate(BaseModel):
    emby_item_id: str
    emby_item_name: str
    input_path: str
    settings: JobSettings = Field(default_factory=JobSettings)
    job_type: Optional[str] = None
    chain_id: Optional[str] = None
    depends_on_task_id: Optional[str] = None
    parent_task_id: Optional[str] = None


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str = "lada"
    emby_item_id: str
    emby_item_name: str
    input_path: str
    output_path: Optional[str] = None
    status: str
    progress: int = 0
    phase_key: Optional[str] = None
    phase_group: Optional[str] = None
    phase_label: Optional[str] = None
    phase_progress: Optional[int] = None
    detail: Optional[str] = None
    error_message: Optional[str] = None
    chain_id: Optional[str] = None
    depends_on_task_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    settings: dict = {}
    result_metadata: Optional[dict] = None
    logs: list = []
    created_at: datetime
    completed_at: Optional[datetime] = None

    @field_validator("created_at", "completed_at", mode="before")
    @classmethod
    def ensure_utc(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int


class EmbyNFO(BaseModel):
    """NFO metadata model."""

    title: Optional[str] = None
    originaltitle: Optional[str] = None
    sorttitle: Optional[str] = None
    year: Optional[str] = None
    premiered: Optional[str] = None
    studio: Optional[str] = None
    plot: Optional[str] = None
    outline: Optional[str] = None
    genres: list[str] = []
    actors: list[dict] = []
    director: Optional[str] = None
    rating: Optional[str] = None
    set: Optional[str] = None
    id: Optional[str] = None
    tag: Optional[str] = None
    maker: Optional[str] = None
    publisher: Optional[str] = None
    label: Optional[str] = None
    num: Optional[str] = None


class FileTags(BaseModel):
    """File tag information parsed from filename."""

    is_uncensored: bool = False  # 片商/目录等结构性来源判定的无码
    has_chinese: bool = False    # -c 中文
    is_cracked: bool = False     # 破解/去码版本
    is_leaked: bool = False      # 流出
    release_type: Optional[str] = None  # 流出 / 无码
    release_type_key: Optional[str] = None  # leaked / uncensored


class EmbyLibrary(BaseModel):
    id: str
    name: str
    type: str
    poster_path: Optional[str] = None


class EmbyItem(BaseModel):
    id: str
    name: str
    type: str
    media_type: Optional[str] = None
    poster_path: Optional[str] = None
    date_created: Optional[str] = None
    path: Optional[str] = None
    nfo: Optional[EmbyNFO] = None
    tags: FileTags = Field(default_factory=FileTags)
    subtitle_count: int = 0


class SiblingItem(BaseModel):
    """A sibling video file in the same folder (CD1/CD2, etc.)."""

    label: str = ""
    file_path: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    poster_path: Optional[str] = None


class EmbyItemDetail(BaseModel):
    id: str
    name: str
    media_type: str
    file_path: Optional[str] = None
    stream_url: Optional[str] = None
    date_created: Optional[str] = None
    premiered: Optional[str] = None
    studios: list[str] = []
    genres: list[str] = []
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    nfo: Optional[EmbyNFO] = None
    siblings: list[SiblingItem] = []


class EmbyLibraryResponse(BaseModel):
    libraries: list[EmbyLibrary]


class EmbyItemListResponse(BaseModel):
    items: list[EmbyItem]
    total: int
