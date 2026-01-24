from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class ChangeType(str, Enum):
    """Type of change in a run"""
    ADD = "add"
    REMOVE = "remove"


class RunChangeOut(BaseModel):
    """Output schema for a run change"""
    id: int
    run_id: int
    change_type: ChangeType
    spotify_track_id: str
    artist: str
    title: str
    block_index: Optional[int] = None
    position_in_block: Optional[int] = None
    year: Optional[int] = None
    decade: Optional[int] = None
    language: Optional[str] = None
    genre_tags: Optional[Dict[str, Any]] = None
    is_ai_suggested: bool
    is_approved: bool
    suggested_reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RunChangeUpdate(BaseModel):
    """Update a run change (approve/reject, swap track)"""
    is_approved: Optional[bool] = None
    spotify_track_id: Optional[str] = None  # For manual override
    artist: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    decade: Optional[int] = None
    language: Optional[str] = None
    suggested_reason: Optional[str] = None


class RunChangesResponse(BaseModel):
    """Response with all changes for a run"""
    run_id: int
    playlist_key: str
    adds: List[RunChangeOut]
    removes: List[RunChangeOut]
