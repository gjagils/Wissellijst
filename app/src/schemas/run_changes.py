from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class RunChangeOut(BaseModel):
    direction: str  # "IN" or "OUT"
    track_id: str
    name: str
    artists: List[str]
    reason: Optional[Dict[str, Any]] = None
    chosen_by: str  # "auto" | "manual" | "pinned"


class RunChangesResponse(BaseModel):
    run_id: int
    playlist_key: str
    items: List[RunChangeOut]
