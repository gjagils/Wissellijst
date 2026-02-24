from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PlaylistCreate(BaseModel):
    """Create a new playlist"""
    key: str
    name: str
    spotify_playlist_id: str
    vibe: Optional[str] = None
    refresh_schedule: Optional[str] = None  # cron expression
    is_auto_commit: bool = False


class PlaylistOut(BaseModel):
    """Output schema for a playlist"""
    id: int
    key: str
    spotify_playlist_id: str
    name: Optional[str] = None
    vibe: Optional[str] = None
    is_active: bool
    refresh_schedule: Optional[str] = None
    is_auto_commit: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PlaylistUpdate(BaseModel):
    """Update a playlist"""
    name: Optional[str] = None
    vibe: Optional[str] = None
    is_active: Optional[bool] = None
    refresh_schedule: Optional[str] = None
    is_auto_commit: Optional[bool] = None
