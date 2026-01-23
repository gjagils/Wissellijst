from datetime import datetime
from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base

class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    playlist_name: Mapped[str] = mapped_column(String(200), index=True)
    status: Mapped[str] = mapped_column(String(50), default="started", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from .session import Base

class Playlist(Base):
    __tablename__ = "playlists"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    spotify_playlist_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, ForeignKey, JSON
from sqlalchemy.orm import relationship

class PlaylistRule(Base):
    __tablename__ = "playlist_rules"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), unique=True, nullable=False)

    # configuratie / regels
    target_size = Column(Integer, default=50, nullable=False)
    swap_size = Column(Integer, default=5, nullable=False)
    max_tracks_per_artist = Column(Integer, default=1, nullable=False)

    # later uitbreidbaar (decade balans, blacklists, etc.)
    decade_policy = Column(JSON, nullable=True)     # bv {"70s":10,"80s":10,...}
    exclude = Column(JSON, nullable=True)           # bv {"track_ids":[...], "artist_ids":[...]}

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # optioneel (handig later)
    playlist = relationship("Playlist", backref="rules", uselist=False)


# -----------------------
# Playlist track cache + history
# -----------------------
from sqlalchemy import ForeignKey, JSON
from sqlalchemy.orm import relationship


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"

    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, ForeignKey("playlists.id"), index=True, nullable=False)

    track_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    artists = Column(JSON, nullable=False)  # list[str]
    album = Column(String, nullable=True)
    release_date = Column(String, nullable=True)
    popularity = Column(Integer, nullable=True)
    spotify_url = Column(String, nullable=True)

    is_current = Column(Boolean, default=True, index=True, nullable=False)

    first_seen_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    playlist = relationship("Playlist", backref="tracks")


# -----------------------
# Run changes (preview/commit audit trail)
# -----------------------
class RunChange(Base):
    __tablename__ = "run_changes"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), index=True, nullable=False)

    direction = Column(String, nullable=False)  # "IN" or "OUT"
    track_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    artists = Column(JSON, nullable=False)  # list[str]

    reason = Column(JSON, nullable=True)     # trace/explainability blob
    chosen_by = Column(String, default="auto", nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("Run", backref="changes")
