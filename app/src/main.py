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
from src.schemas.runs import RunCreate, RunOut, RunListOut
from src.schemas.run_changes import RunChangeOut, RunChangeUpdate, RunChangesResponse
from src.schemas.playlists import PlaylistCreate
from src.schemas.rules import PlaylistRulesOut, PlaylistRulesUpdate
from src.schemas.runs_preview import RunPreviewResponse
from src.schemas.tracks import PlaylistTracksResponse

# Refresh service
try:
    from src.services.refresh_service import (
        create_refresh_preview,
        commit_refresh,
        approve_change,
        cancel_run,
    )
    REFRESH_SERVICE_ENABLED = True
except Exception as e:
    print(f"Refresh service not available: {e}")
    REFRESH_SERVICE_ENABLED = False

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
        block_size=5,
        block_count=10,
        max_tracks_per_artist=1,
        no_repeat_ever=True,
        remove_policy={"type": "oldest_block"},
        candidate_policies={},
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
        name=payload.name,
        spotify_playlist_id=payload.spotify_playlist_id,
        vibe=payload.vibe,
        refresh_schedule=payload.refresh_schedule,
        is_auto_commit=payload.is_auto_commit,
        is_active=True,
    )
    db.add(pl)
    db.commit()
    db.refresh(pl)
    return {
        "id": pl.id,
        "key": pl.key,
        "name": pl.name,
        "spotify_playlist_id": pl.spotify_playlist_id,
        "vibe": pl.vibe,
    }


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


# ============================================================
# Run Management Endpoints (Sprint 2)
# ============================================================

if REFRESH_SERVICE_ENABLED:

    @app.post("/playlists/{playlist_key}/runs/preview")
    def create_run_preview(playlist_key: str, db: Session = Depends(get_db)):
        """
        Create a refresh preview for a playlist.

        This generates AI candidates, validates them, and creates a Run in PREVIEW status.
        """
        try:
            sp = SpotifyClient()
            run, remove_changes, add_changes = create_refresh_preview(
                db=db,
                playlist_key=playlist_key,
                spotify_client=sp,
            )

            return {
                "run_id": run.id,
                "playlist_key": playlist_key,
                "status": run.status.value,
                "scheduled_at": run.scheduled_at.isoformat() if run.scheduled_at else None,
                "remove_count": len(remove_changes),
                "add_count": len(add_changes),
                "message": f"Created preview run {run.id} with {len(remove_changes)} removes and {len(add_changes)} adds",
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create refresh preview: {str(e)}")


    @app.get("/runs/{run_id}", response_model=RunOut)
    def get_run(run_id: int, db: Session = Depends(get_db)):
        """Get details of a specific run."""
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        return run


    @app.get("/runs/{run_id}/changes", response_model=RunChangesResponse)
    def get_run_changes(run_id: int, db: Session = Depends(get_db)):
        """Get all changes (adds and removes) for a run."""
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        from src.db.models import ChangeType

        remove_changes = [c for c in run.changes if c.change_type == ChangeType.REMOVE]
        add_changes = [c for c in run.changes if c.change_type == ChangeType.ADD]

        return RunChangesResponse(
            run_id=run.id,
            playlist_key=run.playlist.key,
            adds=[RunChangeOut.model_validate(c) for c in add_changes],
            removes=[RunChangeOut.model_validate(c) for c in remove_changes],
        )


    @app.patch("/runs/{run_id}/changes/{change_id}/approve", response_model=RunChangeOut)
    def approve_run_change(
        run_id: int,
        change_id: int,
        update: RunChangeUpdate,
        db: Session = Depends(get_db)
    ):
        """Approve or reject a specific change."""
        try:
            if update.is_approved is not None:
                change = approve_change(db, change_id, update.is_approved)
                return RunChangeOut.model_validate(change)
            else:
                raise HTTPException(status_code=400, detail="is_approved must be provided")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


    @app.post("/runs/{run_id}/commit")
    def commit_run(run_id: int, db: Session = Depends(get_db)):
        """Commit an approved run, applying changes to playlist and Spotify."""
        try:
            sp = SpotifyClient()
            summary = commit_refresh(db, run_id, sp)
            return {
                "success": True,
                "message": f"Run {run_id} committed successfully",
                **summary
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to commit run: {str(e)}")


    @app.delete("/runs/{run_id}")
    def cancel_run_endpoint(run_id: int, db: Session = Depends(get_db)):
        """Cancel a preview run."""
        try:
            run = cancel_run(db, run_id)
            return {
                "success": True,
                "message": f"Run {run_id} cancelled",
                "run_id": run.id,
                "status": run.status.value,
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))


    @app.get("/playlists/{playlist_key}/runs", response_model=RunListOut)
    def get_playlist_runs(
        playlist_key: str,
        limit: int = 10,
        db: Session = Depends(get_db)
    ):
        """Get run history for a playlist."""
        pl = get_playlist_or_404(db, playlist_key)

        runs = (
            db.query(Run)
            .filter(Run.playlist_id == pl.id)
            .order_by(Run.created_at.desc())
            .limit(limit)
            .all()
        )

        return RunListOut(
            runs=[RunOut.model_validate(r) for r in runs],
            total=len(runs)
        )


# Old stub endpoint (keep for backwards compatibility but mark as deprecated)
@app.post("/runs/preview", response_model=RunPreviewResponse, deprecated=True)
def runs_preview_deprecated(payload: RunCreate, db: Session = Depends(get_db)):
    """
    DEPRECATED: Use POST /playlists/{playlist_key}/runs/preview instead.
    """
    pl = get_playlist_or_404(db, payload.playlist_key)
    rules = get_or_create_rules(db, pl)

    return {
        "run_id": 0,
        "playlist_key": payload.playlist_key,
        "playlist_id": pl.spotify_playlist_id,
        "rules": {
            "target_size": getattr(rules, "block_size", 5) * getattr(rules, "block_count", 10),
            "swap_size": getattr(rules, "block_size", 5),
            "max_tracks_per_artist": getattr(rules, "max_tracks_per_artist", 1),
            "decade_policy": getattr(rules, "candidate_policies", {}).get("decade_distribution"),
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
