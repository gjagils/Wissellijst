from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Enum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


# ---------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------

class RunStatus(str, enum.Enum):
    """Status of a playlist refresh run"""
    PREVIEW = "preview"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class ChangeType(str, enum.Enum):
    """Type of change in a run"""
    ADD = "add"
    REMOVE = "remove"


# ---------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------

class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    spotify_playlist_id: Mapped[str] = mapped_column(String(128))

    name: Mapped[Optional[str]] = mapped_column(String(200))
    vibe: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Scheduling configuration
    refresh_schedule: Mapped[Optional[str]] = mapped_column(String(100))  # cron expression
    is_auto_commit: Mapped[bool] = mapped_column(Boolean, default=False)  # auto-approve runs

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    rules: Mapped["PlaylistRules"] = relationship(
        back_populates="playlist",
        uselist=False,
        cascade="all, delete-orphan",
    )

    blocks: Mapped[List["PlaylistBlock"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
    )

    runs: Mapped[List["Run"]] = relationship(
        back_populates="playlist",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------
# Playlist rules (generic + policies)
# ---------------------------------------------------------------------

class PlaylistRules(Base):
    __tablename__ = "playlist_rules"
    __table_args__ = (
        UniqueConstraint("playlist_id", name="uq_playlist_rules_playlist_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))

    block_size: Mapped[int] = mapped_column(Integer, default=5)
    block_count: Mapped[int] = mapped_column(Integer, default=10)

    max_tracks_per_artist: Mapped[int] = mapped_column(Integer, default=1)
    no_repeat_ever: Mapped[bool] = mapped_column(Boolean, default=True)

    remove_policy: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=lambda: {"type": "oldest_block"},
    )

    candidate_policies: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    playlist: Mapped["Playlist"] = relationship(back_populates="rules")


# ---------------------------------------------------------------------
# Blocks (10 blokjes van 5)
# ---------------------------------------------------------------------

class PlaylistBlock(Base):
    __tablename__ = "playlist_blocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))

    block_index: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    playlist: Mapped["Playlist"] = relationship(back_populates="blocks")
    tracks: Mapped[List["BlockTrack"]] = relationship(
        back_populates="block",
        cascade="all, delete-orphan",
    )


class BlockTrack(Base):
    __tablename__ = "block_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    block_id: Mapped[int] = mapped_column(ForeignKey("playlist_blocks.id", ondelete="CASCADE"))

    spotify_track_id: Mapped[str] = mapped_column(String(64))
    artist: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))

    # Metadata for policy enforcement
    decade: Mapped[Optional[int]] = mapped_column(Integer)
    year: Mapped[Optional[int]] = mapped_column(Integer)
    language: Mapped[Optional[str]] = mapped_column(String(10))  # 'nl', 'en', 'other'
    genre_tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    reason: Mapped[Optional[str]] = mapped_column(Text)
    position_in_block: Mapped[int] = mapped_column(Integer)

    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    block: Mapped["PlaylistBlock"] = relationship(back_populates="tracks")


# ---------------------------------------------------------------------
# Track history (no-repeat-ever)
# ---------------------------------------------------------------------

class PlaylistTrackHistory(Base):
    __tablename__ = "playlist_track_history"
    __table_args__ = (
        UniqueConstraint(
            "playlist_id",
            "spotify_track_id",
            name="uq_playlist_track_history",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))

    spotify_track_id: Mapped[str] = mapped_column(String(64))
    first_added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ---------------------------------------------------------------------
# Runs (weekly refresh tracking)
# ---------------------------------------------------------------------

class Run(Base):
    """Tracks a playlist refresh run (preview or committed)"""
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    playlist_id: Mapped[int] = mapped_column(ForeignKey("playlists.id", ondelete="CASCADE"))

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=20),
        default=RunStatus.PREVIEW,
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    playlist: Mapped["Playlist"] = relationship(back_populates="runs")
    changes: Mapped[List["RunChange"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class RunChange(Base):
    """Individual track change in a run (add or remove)"""
    __tablename__ = "run_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"))

    change_type: Mapped[ChangeType] = mapped_column(
        Enum(ChangeType, native_enum=False, length=20),
    )

    spotify_track_id: Mapped[str] = mapped_column(String(64))
    artist: Mapped[str] = mapped_column(String(256))
    title: Mapped[str] = mapped_column(String(256))

    # Position info for adds
    block_index: Mapped[Optional[int]] = mapped_column(Integer)
    position_in_block: Mapped[Optional[int]] = mapped_column(Integer)

    # Metadata
    year: Mapped[Optional[int]] = mapped_column(Integer)
    decade: Mapped[Optional[int]] = mapped_column(Integer)
    language: Mapped[Optional[str]] = mapped_column(String(10))
    genre_tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # AI and approval tracking
    is_ai_suggested: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_reason: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    run: Mapped["Run"] = relationship(back_populates="changes")

