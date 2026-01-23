from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class PlaylistTrackOut(BaseModel):
    track_id: str
    name: str
    artists: List[str]
    album: Optional[str] = None
    release_date: Optional[str] = None
    popularity: Optional[int] = None
    spotify_url: Optional[str] = None
    is_current: bool
    first_seen_at: Optional[str] = None
    last_seen_at: Optional[str] = None


class PlaylistTracksResponse(BaseModel):
    playlist_key: str
    playlist_id: str
    total_current: int
    items: List[PlaylistTrackOut]
