from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class RunStatus(str, Enum):
    """Status of a playlist refresh run"""
    PREVIEW = "preview"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


class RunCreate(BaseModel):
    """Create a new run"""
    playlist_key: str
    scheduled_at: Optional[datetime] = None


class RunOut(BaseModel):
    """Output schema for a run"""
    id: int
    playlist_id: int
    status: RunStatus
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunListOut(BaseModel):
    """List of runs for a playlist"""
    runs: List[RunOut]
    total: int
