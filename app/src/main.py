from __future__ import annotations

import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional

from src.db.session import SessionLocal
from src.logging_config import setup_logging

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

# Scheduler service
try:
    from src.services.scheduler_service import (
        start_scheduler,
        shutdown_scheduler,
        get_scheduler,
    )
    SCHEDULER_ENABLED = True
except Exception as e:
    print(f"Scheduler service not available: {e}")
    SCHEDULER_ENABLED = False


app = FastAPI(title="Wissellijst API")

# Mount static files (frontend)
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    print(f"✅ Static files mounted from: {static_dir}")


# Startup event: Initialize scheduler
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    # Setup logging
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_file = os.getenv("LOG_FILE", None)
    setup_logging(level=log_level, log_file=log_file)

    print(f"✅ Logging configured: level={log_level}")

    # Start scheduler
    if SCHEDULER_ENABLED:
        try:
            start_scheduler()
            print("✅ Playlist scheduler started")
        except Exception as e:
            print(f"⚠️  Failed to start scheduler: {e}")


# Shutdown event: Stop scheduler
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if SCHEDULER_ENABLED:
        try:
            shutdown_scheduler()
            print("✅ Playlist scheduler stopped")
        except Exception as e:
            print(f"⚠️  Failed to stop scheduler: {e}")


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


@app.get("/")
def root():
    """Redirect to frontend dashboard"""
    return RedirectResponse(url="/static/index.html")


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


@app.get("/spotify/playlists")
def spotify_playlists():
    """Get all Spotify playlists of the current user"""
    sp = SpotifyClient()
    return sp.get_user_playlists()


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
            "name": r.name,
            "spotify_playlist_id": r.spotify_playlist_id,
            "vibe": getattr(r, "vibe", None),
            "refresh_schedule": r.refresh_schedule,
            "is_auto_commit": r.is_auto_commit,
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


# ============================================================
# Scheduler Endpoints (Sprint 3)
# ============================================================

if SCHEDULER_ENABLED:

    @app.post("/scheduler/refresh/{playlist_key}")
    def manual_refresh_trigger(
        playlist_key: str,
        auto_commit: bool = False,
        db: Session = Depends(get_db)
    ):
        """
        Manually trigger a refresh for a playlist.

        This is useful for testing scheduled refreshes without waiting for cron.

        Query params:
            auto_commit: If True, automatically commit approved changes (default: False)
        """
        # Verify playlist exists
        pl = get_playlist_or_404(db, playlist_key)

        # Trigger refresh
        scheduler = get_scheduler()
        result = scheduler.trigger_manual_refresh(playlist_key, auto_commit)

        return result


    @app.get("/scheduler/jobs")
    def get_scheduled_jobs():
        """Get all scheduled jobs with next run times."""
        scheduler = get_scheduler()
        jobs = scheduler.get_scheduled_jobs()

        return {
            "total": len(jobs),
            "jobs": jobs,
        }


    @app.post("/scheduler/reload")
    def reload_scheduler(db: Session = Depends(get_db)):
        """
        Reload scheduler from database.

        This re-reads all active playlists and updates their scheduled jobs.
        Useful after updating playlist schedules.
        """
        scheduler = get_scheduler()
        scheduler.reload_from_database()

        jobs = scheduler.get_scheduled_jobs()

        return {
            "success": True,
            "message": f"Scheduler reloaded with {len(jobs)} jobs",
            "jobs": jobs,
        }


    @app.patch("/playlists/{playlist_key}/schedule")
    def update_playlist_schedule(
        playlist_key: str,
        refresh_schedule: Optional[str] = None,
        is_auto_commit: Optional[bool] = None,
        db: Session = Depends(get_db)
    ):
        """
        Update a playlist's refresh schedule.

        Body:
            refresh_schedule: Cron expression (e.g., "0 2 * * 1" for Monday 2:00 AM)
                             Set to null to disable scheduling
            is_auto_commit: If True, automatically commit refreshes (optional)
        """
        pl = get_playlist_or_404(db, playlist_key)

        # Update database
        if refresh_schedule is not None:
            pl.refresh_schedule = refresh_schedule

        if is_auto_commit is not None:
            pl.is_auto_commit = is_auto_commit

        db.commit()

        # Update scheduler
        scheduler = get_scheduler()

        if pl.refresh_schedule:
            try:
                scheduler.add_playlist_job(
                    pl.key,
                    pl.refresh_schedule,
                    pl.is_auto_commit
                )
                message = f"Schedule updated: {pl.refresh_schedule} (auto_commit={pl.is_auto_commit})"
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
        else:
            scheduler.remove_playlist_job(pl.key)
            message = "Scheduling disabled"

        return {
            "success": True,
            "message": message,
            "playlist_key": pl.key,
            "refresh_schedule": pl.refresh_schedule,
            "is_auto_commit": pl.is_auto_commit,
        }
