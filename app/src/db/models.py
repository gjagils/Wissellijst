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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.utcnow()


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

    decade: Mapped[Optional[int]] = mapped_column(Integer)
    reason: Mapped[Optional[str]] = mapped_column(Text)

    position_in_block: Mapped[int] = mapped_column(Integer)

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

