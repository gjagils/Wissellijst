from pydantic import BaseModel
from typing import List, Dict, Any

from .rules import PlaylistRulesOut


class RunPreviewResponse(BaseModel):
    run_id: int
    playlist_key: str
    playlist_id: str
    seed_tracks: List[str]
    rules: PlaylistRulesOut
    remove: List[Dict[str, Any]]
    add: List[Dict[str, Any]]
    candidates_considered: int
