from pydantic import BaseModel, Field
from typing import Literal, Optional, List, Dict, Any


class BootstrapPreviewRequest(BaseModel):
    playlist_key: str
    fill_mode: Literal["append", "replace"] = "append"
    target_total: int = Field(default=50, ge=1, le=500)
    block_size: int = Field(default=5, ge=1, le=50)

    # how many candidates to ask AI per round (if applicable)
    batch_size: int = Field(default=15, ge=5, le=100)

    # safety to prevent infinite loops
    max_rounds: int = Field(default=10, ge=1, le=50)


class BootstrapPreviewResponse(BaseModel):
    playlist_key: str
    current_count: int
    needed: int
    target_total: int
    block_size: int
    blocks: List[Dict[str, Any]]
    add: List[Dict[str, Any]]
    filtered: Dict[str, int]
