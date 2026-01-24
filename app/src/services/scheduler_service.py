"""
Playlist refresh scheduler service.

Automatically triggers playlist refreshes based on configured schedules.
Supports:
- Cron-based scheduling per playlist
- Auto-commit workflow (or manual approval required)
- Manual trigger for testing
- Comprehensive logging
"""

import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy.orm import Session

from src.db.session import SessionLocal
from src.db.models import Playlist, Run, RunStatus
from src.services.refresh_service import create_refresh_preview, commit_refresh
from src.spotify_client import SpotifyClient

# Configure logging
logger = logging.getLogger(__name__)


class PlaylistScheduler:
    """
    Manages automatic playlist refresh scheduling.

    Uses APScheduler to run periodic refreshes based on each playlist's
    refresh_schedule (cron expression).
    """

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._jobs = {}  # playlist_key -> job_id mapping

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Playlist scheduler started")

    def shutdown(self):
        """Shutdown the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Playlist scheduler stopped")

    def add_playlist_job(self, playlist_key: str, cron_expression: str, is_auto_commit: bool = False):
        """
        Add or update a scheduled job for a playlist.

        Args:
            playlist_key: Playlist key
            cron_expression: Cron expression (e.g., "0 2 * * 1" for Monday 2:00 AM)
            is_auto_commit: If True, automatically commit approved changes
        """
        # Remove existing job if present
        self.remove_playlist_job(playlist_key)

        try:
            # Parse cron expression
            # Format: "minute hour day month day_of_week"
            trigger = CronTrigger.from_crontab(cron_expression)

            # Add job
            job = self.scheduler.add_job(
                func=self._execute_scheduled_refresh,
                trigger=trigger,
                args=[playlist_key, is_auto_commit],
                id=f"playlist_{playlist_key}",
                name=f"Refresh {playlist_key}",
                replace_existing=True,
            )

            self._jobs[playlist_key] = job.id
            logger.info(f"Scheduled refresh for '{playlist_key}': {cron_expression} (auto_commit={is_auto_commit})")

        except Exception as e:
            logger.error(f"Failed to schedule refresh for '{playlist_key}': {e}")
            raise ValueError(f"Invalid cron expression: {cron_expression}")

    def remove_playlist_job(self, playlist_key: str):
        """Remove a scheduled job for a playlist."""
        job_id = self._jobs.get(playlist_key)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                del self._jobs[playlist_key]
                logger.info(f"Removed scheduled refresh for '{playlist_key}'")
            except JobLookupError:
                logger.warning(f"Job for '{playlist_key}' not found")

    def reload_from_database(self):
        """
        Reload all active playlists from database and schedule their refreshes.

        Should be called on startup and when playlists are updated.
        """
        db = SessionLocal()
        try:
            # Get all active playlists with refresh schedules
            playlists = db.query(Playlist).filter(
                Playlist.is_active == True,
                Playlist.refresh_schedule.isnot(None)
            ).all()

            logger.info(f"Reloading schedules for {len(playlists)} active playlists")

            for playlist in playlists:
                try:
                    self.add_playlist_job(
                        playlist.key,
                        playlist.refresh_schedule,
                        playlist.is_auto_commit
                    )
                except Exception as e:
                    logger.error(f"Failed to schedule playlist '{playlist.key}': {e}")

            logger.info(f"Scheduler reload complete. {len(self._jobs)} jobs scheduled.")

        finally:
            db.close()

    def _execute_scheduled_refresh(self, playlist_key: str, is_auto_commit: bool):
        """
        Execute a scheduled refresh for a playlist.

        This is called by APScheduler when a scheduled time is reached.

        Args:
            playlist_key: Playlist to refresh
            is_auto_commit: If True, automatically commit the refresh
        """
        logger.info(f"=== Executing scheduled refresh for '{playlist_key}' (auto_commit={is_auto_commit}) ===")

        db = SessionLocal()
        try:
            spotify_client = SpotifyClient()

            # Step 1: Create preview
            logger.info(f"Creating refresh preview for '{playlist_key}'...")
            run, remove_changes, add_changes = create_refresh_preview(
                db=db,
                playlist_key=playlist_key,
                spotify_client=spotify_client,
                scheduled_at=datetime.utcnow(),
            )

            logger.info(f"Preview created: run_id={run.id}, removes={len(remove_changes)}, adds={len(add_changes)}")

            # Step 2: If auto-commit, approve all ADD changes and commit
            if is_auto_commit:
                logger.info(f"Auto-commit enabled. Approving all {len(add_changes)} ADD changes...")

                # Approve all ADD changes
                for change in add_changes:
                    change.is_approved = True

                db.commit()

                # Commit the run
                logger.info(f"Committing run {run.id}...")
                summary = commit_refresh(db, run.id, spotify_client)

                logger.info(f"✅ Auto-commit successful for '{playlist_key}'")
                logger.info(f"   Removed block {summary['removed_block_index']}: {len(summary['removed_tracks'])} tracks")
                logger.info(f"   Added block {summary['added_block_index']}: {len(summary['added_tracks'])} tracks")

            else:
                logger.info(f"⏸️ Manual approval required for '{playlist_key}'. Run {run.id} is in PREVIEW status.")
                logger.info(f"   Review and approve via: GET /runs/{run.id}/changes")

        except Exception as e:
            logger.error(f"❌ Scheduled refresh failed for '{playlist_key}': {e}", exc_info=True)
            db.rollback()

        finally:
            db.close()

    def trigger_manual_refresh(self, playlist_key: str, is_auto_commit: bool = False) -> dict:
        """
        Manually trigger a refresh for testing.

        Args:
            playlist_key: Playlist to refresh
            is_auto_commit: If True, automatically commit the refresh

        Returns:
            Dict with summary of the refresh
        """
        logger.info(f"Manual refresh triggered for '{playlist_key}' (auto_commit={is_auto_commit})")

        db = SessionLocal()
        try:
            spotify_client = SpotifyClient()

            # Create preview
            run, remove_changes, add_changes = create_refresh_preview(
                db=db,
                playlist_key=playlist_key,
                spotify_client=spotify_client,
                scheduled_at=datetime.utcnow(),
            )

            if is_auto_commit:
                # Approve all ADD changes
                for change in add_changes:
                    change.is_approved = True
                db.commit()

                # Commit the run
                summary = commit_refresh(db, run.id, spotify_client)

                return {
                    "success": True,
                    "message": f"Manual refresh completed with auto-commit",
                    "run_id": run.id,
                    "status": "committed",
                    **summary
                }
            else:
                return {
                    "success": True,
                    "message": f"Manual refresh preview created",
                    "run_id": run.id,
                    "status": "preview",
                    "remove_count": len(remove_changes),
                    "add_count": len(add_changes),
                }

        except Exception as e:
            logger.error(f"Manual refresh failed for '{playlist_key}': {e}", exc_info=True)
            db.rollback()
            return {
                "success": False,
                "message": f"Manual refresh failed: {str(e)}",
            }

        finally:
            db.close()

    def get_scheduled_jobs(self) -> list:
        """
        Get list of all scheduled jobs.

        Returns:
            List of dicts with job information
        """
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return jobs


# Global scheduler instance
_scheduler: Optional[PlaylistScheduler] = None


def get_scheduler() -> PlaylistScheduler:
    """Get the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = PlaylistScheduler()
    return _scheduler


def start_scheduler():
    """Start the global scheduler and load playlists from database."""
    scheduler = get_scheduler()
    scheduler.start()
    scheduler.reload_from_database()
    logger.info("Playlist scheduler initialized and loaded")


def shutdown_scheduler():
    """Shutdown the global scheduler."""
    scheduler = get_scheduler()
    scheduler.shutdown()
