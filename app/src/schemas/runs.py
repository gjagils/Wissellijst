from pydantic import BaseModel


class RunCreate(BaseModel):
    playlist_name: str
    status: str = "started"
