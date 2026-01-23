from pydantic import BaseModel
from typing import Optional, Dict, Any


class PlaylistRulesOut(BaseModel):
    playlist_key: str
    target_size: int
    swap_size: int
    max_tracks_per_artist: int
    decade_policy: Optional[Dict[str, Any]] = None
    exclude: Optional[Dict[str, Any]] = None


class PlaylistRulesUpdate(BaseModel):
    target_size: Optional[int] = None
    swap_size: Optional[int] = None
    max_tracks_per_artist: Optional[int] = None
    decade_policy: Optional[Dict[str, Any]] = None
    exclude: Optional[Dict[str, Any]] = None
