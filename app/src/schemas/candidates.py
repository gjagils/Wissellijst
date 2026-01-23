from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class CandidateReason(BaseModel):
    seed_track_id: str
    seed_track_name: Optional[str] = None

    seed_artist_id: str
    seed_artist_name: Optional[str] = None

    related_artist_id: str
    related_artist_name: Optional[str] = None

    via: str


class CandidateTrack(BaseModel):
    track_id: str
    name: str
    artists: List[str]
    album: Optional[str] = None
    popularity: Optional[int] = None
    preview_url: Optional[str] = None
    external_url: Optional[str] = None

    reasons: List[CandidateReason]
    debug: Optional[Dict[str, Any]] = None


class CandidatesResponse(BaseModel):
    playlist_key: str
    playlist_id: str
    seed_tracks: List[str]
    candidates: List[CandidateTrack]
    excluded_existing_count: int
    raw_collected_count: int
    unique_count: int
