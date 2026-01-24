from pydantic import BaseModel
from typing import Optional, Dict, Any


class PlaylistRulesOut(BaseModel):
    """Output schema for playlist rules"""
    playlist_key: str
    block_size: int
    block_count: int
    max_tracks_per_artist: int
    no_repeat_ever: bool
    remove_policy: Dict[str, Any]
    candidate_policies: Dict[str, Any]

    class Config:
        from_attributes = True


class PlaylistRulesUpdate(BaseModel):
    """Update playlist rules"""
    block_size: Optional[int] = None
    block_count: Optional[int] = None
    max_tracks_per_artist: Optional[int] = None
    no_repeat_ever: Optional[bool] = None
    remove_policy: Optional[Dict[str, Any]] = None
    candidate_policies: Optional[Dict[str, Any]] = None


class CandidatePolicies(BaseModel):
    """Structured candidate policies for validation"""
    decade_distribution: Optional[Dict[str, int]] = None  # e.g. {"1980s": 1, "1990s": 1}
    language: Optional[Dict[str, Any]] = None  # e.g. {"max_dutch_per_block": 1, "allow_dutch": true}
    history_window_months: Optional[int] = None  # e.g. 3 for 3-month deduplication
    year_distribution: Optional[Dict[str, int]] = None  # e.g. {"pre_2000": 2, "post_2000": 2, "wildcard": 1}
    genre_constraints: Optional[Dict[str, Any]] = None  # e.g. {"required": ["soul", "indie"]}
