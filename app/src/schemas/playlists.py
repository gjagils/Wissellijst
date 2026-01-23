from pydantic import BaseModel


class PlaylistCreate(BaseModel):
    key: str
    name: str
    spotify_playlist_id: str
