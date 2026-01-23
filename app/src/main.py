from __future__ import annotations

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from src.db.session import SessionLocal

import src.db.models as models

# Required models (present in your models.py)
Playlist = getattr(models, "Playlist", None)
PlaylistRules = getattr(models, "PlaylistRules", None)
PlaylistTrackHistory = getattr(models, "PlaylistTrackHistory", None)
PlaylistBlock = getattr(models, "PlaylistBlock", None)
BlockTrack = getattr(models, "BlockTrack", None)

missing_required = [
    name
    for name, val in [
        ("Playlist", Playlist),
        ("PlaylistRules", PlaylistRules),
        ("PlaylistTrackHistory", PlaylistTrackHistory),
        ("PlaylistBlock", PlaylistBlock),
        ("BlockTrack", BlockTrack),
    ]
    if val is None
]
if missing_required:
    available = [n for n in dir(models) if n and n[0].isupper()]
    raise ImportError(
        f"Missing required model classes: {missing_required}. "
        f"Available in src.db.models: {available}"
    )

# Optional models (may be added later)
Run = getattr(models, "Run", None)
RunChange = getattr(models, "RunChange", None)

from src.spotify_client import SpotifyClient

# If these schemas don't exist in your repo yet, comment the related endpoints below.
from src.schemas.runs import RunCreate
from src.schemas.playlists import PlaylistCreate
from src.schemas.rules import PlaylistRulesOut, PlaylistRulesUpdate
from src.schemas.runs_preview import RunPreviewResponse
from src.schemas.tracks import PlaylistTracksResponse

# Bootstrap (if present)
try:
    from src.schemas.bootstrap import BootstrapPreviewRequest, BootstrapPreviewResponse
    from src.services.bootstrap_service import bootstrap_preview, bootstrap_commit
    BOOTSTRAP_ENABLED = True
except Exception:
    BOOTSTRAP_ENABLED = False


app = FastAPI(title="Wissellijst API")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_playlist_or_404(db: Session, playlist_key: str):
    pl = db.query(Playlist).filter(Playlist.key == playlist_key).first()
    if not pl:
        raise HTTPException(status_code=404, detail=f"Unknown playlist_key: {playlist_key}")
    return pl


def get_or_create_rules(db: Session, playlist: Any):
    rules = db.query(PlaylistRules).filter(PlaylistRules.playlist_id == playlist.id).first()
    if rules:
        return rules

    rules = PlaylistRules(
        playlist_id=playlist.id,
        target_size=50,
        swap_size=5,
        max_tracks_per_artist=1,
        decade_policy=None,
        exclude=None,
    )
    db.add(rules)
    db.commit()
    db.refresh(rules)
    return rules


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/spotify/login")
def spotify_login():
    from src.spotify_client import get_auth_url
    return RedirectResponse(get_auth_url())


@app.get("/spotify/callback")
def spotify_callback(code: str):
    from src.spotify_client import handle_callback
    handle_callback(code)
    return {"ok": True}


@app.get("/spotify/me")
def spotify_me():
    sp = SpotifyClient()
    me = sp.sp.me()
    return {"id": me.get("id"), "display_name": me.get("display_name"), "email": me.get("email")}


@app.post("/playlists", response_model=Dict[str, Any])
def create_playlist(payload: PlaylistCreate, db: Session = Depends(get_db)):
    pl = Playlist(
        key=payload.key,
        spotify_playlist_id=payload.spotify_playlist_id,
        vibe=payload.vibe,
        is_active=True,
    )
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return {"id": pl.id, "key": pl.key, "spotify_playlist_id": pl.spotify_playlist_id}


@app.get("/playlists", response_model=List[Dict[str, Any]])
def list_playlists(db: Session = Depends(get_db)):
    rows = db.query(Playlist).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "spotify_playlist_id": r.spotify_playlist_id,
            "vibe": getattr(r, "vibe", None),
        }
        for r in rows
    ]


@app.get("/playlists/{playlist_key}/rules", response_model=PlaylistRulesOut)
def get_rules(playlist_key: str, db: Session = Depends(get_db)):
    pl = get_playlist_or_404(db, playlist_key)
    rules = get_or_create_rules(db, pl)
    return rules


@app.patch("/playlists/{playlist_key}/rules", response_model=PlaylistRulesOut)
def update_rules(playlist_key: str, patch: PlaylistRulesUpdate, db: Session = Depends(get_db)):
    pl = get_playlist_or_404(db, playlist_key)
    rules = get_or_create_rules(db, pl)

    data = patch.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(rules, k, v)

    db.add(rules)
    db.commit()
    db.refresh(rules)
    return rules


@app.get("/playlists/{playlist_key}/tracks", response_model=PlaylistTracksResponse)
def playlist_tracks(playlist_key: str, db: Session = Depends(get_db)):
    pl = get_playlist_or_404(db, playlist_key)
    sp = SpotifyClient()
    tracks = sp.get_playlist_tracks(pl.spotify_playlist_id)
    return {
        "playlist_key": playlist_key,
        "playlist_id": pl.spotify_playlist_id,
        "count": len(tracks),
        "tracks": tracks,
    }


@app.get("/playlists/{playlist_key}/history")
def playlist_history(
    playlist_key: str,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """
    Simple history for UI:
    returns most recent events from PlaylistTrackHistory.
    """
    pl = get_playlist_or_404(db, playlist_key)

    # We assume these columns exist based on our earlier commit code:
    # playlist_id, spotify_track_id, artist, title, action, at
    q = (
        db.query(PlaylistTrackHistory)
        .filter(PlaylistTrackHistory.playlist_id == pl.id)
        .order_by(PlaylistTrackHistory.at.desc())
        .limit(limit)
    )
    rows = q.all()

    out = []
    for r in rows:
        out.append(
            {
                "spotify_track_id": getattr(r, "spotify_track_id", None),
                "artist": getattr(r, "artist", None),
                "title": getattr(r, "title", None),
                "action": getattr(r, "action", None),
                "at": getattr(r, "at", None).isoformat() if getattr(r, "at", None) else None,
            }
        )

    return {"playlist_key": playlist_key, "count": len(out), "items": out}


@app.post("/runs/preview", response_model=RunPreviewResponse)
def runs_preview(payload: RunCreate, db: Session = Depends(get_db)):
    # Leave your existing working preview implementation here.
    # This placeholder avoids crashing while we stabilize startup.
    pl = get_playlist_or_404(db, payload.playlist_key)
    rules = get_or_create_rules(db, pl)

    return {
        "run_id": 0,
        "playlist_key": payload.playlist_key,
        "playlist_id": pl.spotify_playlist_id,
        "rules": {
            "target_size": getattr(rules, "target_size", 50),
            "swap_size": getattr(rules, "swap_size", 5),
            "max_tracks_per_artist": getattr(rules, "max_tracks_per_artist", 1),
            "decade_policy": getattr(rules, "decade_policy", None),
        },
        "remove": [],
        "add": [],
        "candidates_considered": 0,
    }


if BOOTSTRAP_ENABLED:

    @app.post("/playlists/bootstrap/preview", response_model=BootstrapPreviewResponse)
    def playlists_bootstrap_preview(req: BootstrapPreviewRequest, db: Session = Depends(get_db)):
        sp = SpotifyClient()
        return bootstrap_preview(
            db=db,
            spotify=sp,
            playlist_key=req.playlist_key,
            target_total=req.target_total,
            block_size=req.block_size,
            fill_mode=req.fill_mode,
            batch_size=req.batch_size,
            max_rounds=req.max_rounds,
        )

    @app.post("/playlists/bootstrap/commit")
    def playlists_bootstrap_commit(req: BootstrapPreviewRequest, db: Session = Depends(get_db)):
        sp = SpotifyClient()
        return bootstrap_commit(
            db=db,
            spotify=sp,
            playlist_key=req.playlist_key,
            target_total=req.target_total,
            block_size=req.block_size,
            fill_mode=req.fill_mode,
            batch_size=req.batch_size,
            max_rounds=req.max_rounds,
        )
