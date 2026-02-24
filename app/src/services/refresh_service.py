"""
Playlist refresh service.

Handles the complete workflow for refreshing playlists:
1. Preview: Generate AI candidates, validate policies, create Run with changes
2. Commit: Apply approved changes to playlist and Spotify
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from src.db.models import (
    Playlist, PlaylistBlock, BlockTrack, PlaylistTrackHistory,
    Run, RunChange, RunStatus, ChangeType
)
from src.validators.policy_validator import PolicyValidator
from src.ai_candidates import build_candidates_ai
from src.spotify_candidates import build_candidates as build_candidates_spotify


def _get_oldest_block(playlist: Playlist) -> Optional[PlaylistBlock]:
    """
    Get the oldest active block based on created_at timestamp.

    Args:
        playlist: Playlist model instance

    Returns:
        Oldest PlaylistBlock or None if no blocks exist
    """
    active_blocks = [b for b in playlist.blocks if b.is_active]

    if not active_blocks:
        return None

    # Sort by created_at (oldest first)
    active_blocks.sort(key=lambda b: b.created_at)

    return active_blocks[0]


def _block_to_dict_list(block: PlaylistBlock) -> List[Dict[str, Any]]:
    """
    Convert a block's tracks to a list of dicts for validation.
    """
    tracks = []
    for track in block.tracks:
        tracks.append({
            "spotify_track_id": track.spotify_track_id,
            "artist": track.artist,
            "title": track.title,
            "year": track.year,
            "decade": track.decade,
            "language": track.language,
            "genre_tags": track.genre_tags or {},
        })
    return tracks


def _get_current_tracks(playlist: Playlist) -> List[Dict[str, Any]]:
    """
    Get all current tracks from all active blocks.
    """
    tracks = []
    for block in playlist.blocks:
        if block.is_active:
            tracks.extend(_block_to_dict_list(block))
    return tracks


def _get_track_history(db: Session, playlist_id: int) -> List[Dict[str, Any]]:
    """
    Get track history for history validation.
    """
    history_records = db.query(PlaylistTrackHistory).filter(
        PlaylistTrackHistory.playlist_id == playlist_id
    ).all()

    history = []
    for record in history_records:
        history.append({
            "spotify_track_id": record.spotify_track_id,
            "first_added_at": record.first_added_at,
            "last_removed_at": record.last_removed_at,
        })

    return history


def create_refresh_preview(
    db: Session,
    playlist_key: str,
    spotify_client,
    scheduled_at: Optional[datetime] = None,
) -> Tuple[Run, List[RunChange], List[RunChange]]:
    """
    Create a preview of what would happen in a refresh.

    This function:
    1. Identifies the oldest block to remove
    2. Generates AI + Spotify candidate tracks
    3. Validates candidates against policies
    4. Creates a Run with status=PREVIEW
    5. Creates RunChanges for removes and adds

    Args:
        db: Database session
        playlist_key: Playlist key
        spotify_client: SpotifyClient instance
        scheduled_at: Optional scheduled time for the refresh

    Returns:
        Tuple of (Run, remove_changes, add_changes)

    Raises:
        ValueError: If playlist not found or has no rules
    """
    # Fetch playlist with relationships
    playlist = db.query(Playlist).filter(Playlist.key == playlist_key).first()
    if not playlist:
        raise ValueError(f"Playlist '{playlist_key}' not found")

    if not playlist.rules:
        raise ValueError(f"Playlist '{playlist_key}' has no rules configured")

    # Get oldest block to remove
    oldest_block = _get_oldest_block(playlist)
    if not oldest_block:
        raise ValueError(f"Playlist '{playlist_key}' has no active blocks")

    # Get current tracks (for AI context and validation)
    current_tracks = _get_current_tracks(playlist)

    # Get track history
    history = _get_track_history(db, playlist.id)

    # Build rules dict for validation
    rules = {
        "max_tracks_per_artist": playlist.rules.max_tracks_per_artist,
        "no_repeat_ever": playlist.rules.no_repeat_ever,
        "candidate_policies": playlist.rules.candidate_policies,
    }

    # Generate candidates using AI
    print(f"Generating AI candidates for '{playlist_key}'...")
    ai_candidates = build_candidates_ai(
        vibe=playlist.vibe or "General music playlist",
        current_tracks=current_tracks,
        n_candidates=playlist.rules.block_size * 3,  # Generate 3x to have options
        rules=playlist.rules,
        playlist_key=playlist_key,
        spotify_client=spotify_client,
    )

    # If AI fails or returns too few, supplement with Spotify candidates
    if len(ai_candidates) < playlist.rules.block_size:
        print(f"AI returned only {len(ai_candidates)} candidates, supplementing with Spotify...")
        spotify_candidates = build_candidates_spotify(
            playlist_key=playlist_key,
            vibe=playlist.vibe,
            current_tracks=current_tracks,
            limit=playlist.rules.block_size * 2,
            spotify_client=spotify_client,
        )
        # Merge candidates (AI first, then Spotify)
        all_candidates = ai_candidates + spotify_candidates
    else:
        all_candidates = ai_candidates

    # Remove duplicates and tracks already in playlist
    current_track_ids = {t["spotify_track_id"] for t in current_tracks}
    unique_candidates = []
    seen_ids = set()

    for candidate in all_candidates:
        track_id = candidate["spotify_track_id"]
        if track_id not in current_track_ids and track_id not in seen_ids:
            unique_candidates.append(candidate)
            seen_ids.add(track_id)

    print(f"After deduplication: {len(unique_candidates)} unique candidates")

    # Validate candidates and select best block_size
    print(f"Validating candidates against policies...")
    selected_candidates = []

    # Try different combinations to find valid set
    # For now, simple approach: take first block_size that passes validation
    for i in range(len(unique_candidates) - playlist.rules.block_size + 1):
        batch = unique_candidates[i:i + playlist.rules.block_size]

        errors = PolicyValidator.validate_all(batch, current_tracks, history, rules)

        if not errors:
            selected_candidates = batch
            print(f"Found valid set of {len(selected_candidates)} candidates")
            break

    # If no perfect match found, take best effort
    if not selected_candidates:
        print("Warning: No perfectly valid set found, using best effort...")
        selected_candidates = unique_candidates[:playlist.rules.block_size]

        # Log validation errors for debugging
        errors = PolicyValidator.validate_all(selected_candidates, current_tracks, history, rules)
        for error in errors:
            print(f"  Validation warning: {error.message}")

    # Create Run
    run = Run(
        playlist_id=playlist.id,
        status=RunStatus.PREVIEW,
        scheduled_at=scheduled_at or datetime.utcnow(),
    )
    db.add(run)
    db.flush()  # Get run.id

    # Create RunChanges for removals
    remove_changes = []
    for position, track in enumerate(oldest_block.tracks):
        change = RunChange(
            run_id=run.id,
            change_type=ChangeType.REMOVE,
            spotify_track_id=track.spotify_track_id,
            artist=track.artist,
            title=track.title,
            block_index=oldest_block.block_index,
            position_in_block=position,
            year=track.year,
            decade=track.decade,
            language=track.language,
            genre_tags=track.genre_tags,
            is_ai_suggested=False,
            is_approved=True,  # Removals are auto-approved
            suggested_reason=f"Removing oldest block (index {oldest_block.block_index})",
        )
        db.add(change)
        remove_changes.append(change)

    # Create RunChanges for additions
    add_changes = []
    # New block index is max + 1
    new_block_index = max([b.block_index for b in playlist.blocks]) + 1

    for position, candidate in enumerate(selected_candidates):
        change = RunChange(
            run_id=run.id,
            change_type=ChangeType.ADD,
            spotify_track_id=candidate["spotify_track_id"],
            artist=candidate["artist"],
            title=candidate["title"],
            block_index=new_block_index,
            position_in_block=position,
            year=candidate.get("year"),
            decade=candidate.get("decade"),
            language=candidate.get("language"),
            genre_tags=candidate.get("genre_tags"),
            is_ai_suggested=True,
            is_approved=False,  # Requires manual approval
            suggested_reason=candidate.get("reason", "AI suggested track"),
        )
        db.add(change)
        add_changes.append(change)

    db.commit()

    print(f"Created run {run.id} with {len(remove_changes)} removes and {len(add_changes)} adds")

    return run, remove_changes, add_changes


def commit_refresh(
    db: Session,
    run_id: int,
    spotify_client,
) -> Dict[str, Any]:
    """
    Commit an approved refresh run.

    This function:
    1. Validates that run is in PREVIEW status
    2. Checks that all ADD changes are approved
    3. Removes the old block from database
    4. Adds new block with approved tracks
    5. Updates Spotify playlist
    6. Updates track history
    7. Sets run status to COMMITTED

    Args:
        db: Database session
        run_id: Run ID to commit
        spotify_client: SpotifyClient instance

    Returns:
        Dict with summary of what was changed

    Raises:
        ValueError: If run not found, not in preview, or has unapproved changes
    """
    # Fetch run with all relationships
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    if run.status != RunStatus.PREVIEW:
        raise ValueError(f"Run {run_id} is not in preview status (current: {run.status})")

    playlist = run.playlist

    # Check that all ADD changes are approved
    unapproved = [c for c in run.changes if c.change_type == ChangeType.ADD and not c.is_approved]
    if unapproved:
        raise ValueError(f"Run {run_id} has {len(unapproved)} unapproved ADD changes")

    # Separate changes
    remove_changes = [c for c in run.changes if c.change_type == ChangeType.REMOVE]
    add_changes = [c for c in run.changes if c.change_type == ChangeType.ADD and c.is_approved]

    if not remove_changes or not add_changes:
        raise ValueError(f"Run {run_id} has no changes to apply")

    # Get the block to remove
    block_to_remove_index = remove_changes[0].block_index
    block_to_remove = next(
        (b for b in playlist.blocks if b.block_index == block_to_remove_index and b.is_active),
        None
    )

    if not block_to_remove:
        raise ValueError(f"Block index {block_to_remove_index} not found or not active")

    # Mark old block as inactive
    block_to_remove.is_active = False

    # Create new block
    new_block_index = add_changes[0].block_index
    new_block = PlaylistBlock(
        playlist_id=playlist.id,
        block_index=new_block_index,
        is_active=True,
    )
    db.add(new_block)
    db.flush()  # Get new_block.id

    # Add tracks to new block
    for change in add_changes:
        track = BlockTrack(
            block_id=new_block.id,
            spotify_track_id=change.spotify_track_id,
            artist=change.artist,
            title=change.title,
            year=change.year,
            decade=change.decade,
            language=change.language,
            genre_tags=change.genre_tags,
            reason=change.suggested_reason,
            position_in_block=change.position_in_block,
        )
        db.add(track)

    # Update track history
    now = datetime.utcnow()

    # Mark removed tracks as last_removed_at
    for change in remove_changes:
        history = db.query(PlaylistTrackHistory).filter(
            PlaylistTrackHistory.playlist_id == playlist.id,
            PlaylistTrackHistory.spotify_track_id == change.spotify_track_id,
        ).first()

        if history:
            history.last_removed_at = now
        else:
            # Shouldn't happen but handle gracefully
            history = PlaylistTrackHistory(
                playlist_id=playlist.id,
                spotify_track_id=change.spotify_track_id,
                first_added_at=now,
                last_removed_at=now,
            )
            db.add(history)

    # Add new tracks to history
    for change in add_changes:
        history = db.query(PlaylistTrackHistory).filter(
            PlaylistTrackHistory.playlist_id == playlist.id,
            PlaylistTrackHistory.spotify_track_id == change.spotify_track_id,
        ).first()

        if not history:
            history = PlaylistTrackHistory(
                playlist_id=playlist.id,
                spotify_track_id=change.spotify_track_id,
                first_added_at=now,
            )
            db.add(history)

    # Update Spotify playlist
    try:
        sp = spotify_client.get_spotify_client()

        # Remove old tracks from Spotify
        remove_track_ids = [c.spotify_track_id for c in remove_changes]
        if remove_track_ids:
            sp.playlist_remove_all_occurrences_of_items(
                playlist.spotify_playlist_id,
                remove_track_ids
            )

        # Add new tracks to Spotify
        add_track_ids = [f"spotify:track:{c.spotify_track_id}" for c in add_changes]
        if add_track_ids:
            sp.playlist_add_items(playlist.spotify_playlist_id, add_track_ids)

        print(f"Updated Spotify playlist: removed {len(remove_track_ids)}, added {len(add_track_ids)}")

    except Exception as e:
        print(f"Error updating Spotify playlist: {e}")
        db.rollback()
        raise ValueError(f"Failed to update Spotify playlist: {e}")

    # Mark run as committed
    run.status = RunStatus.COMMITTED
    run.executed_at = now

    db.commit()

    # Return summary
    summary = {
        "run_id": run.id,
        "playlist_key": playlist.key,
        "removed_block_index": block_to_remove_index,
        "removed_tracks": [{"artist": c.artist, "title": c.title} for c in remove_changes],
        "added_block_index": new_block_index,
        "added_tracks": [{"artist": c.artist, "title": c.title} for c in add_changes],
        "executed_at": now.isoformat(),
    }

    return summary


def approve_change(
    db: Session,
    change_id: int,
    is_approved: bool,
) -> RunChange:
    """
    Approve or reject a RunChange.

    Args:
        db: Database session
        change_id: RunChange ID
        is_approved: True to approve, False to reject

    Returns:
        Updated RunChange

    Raises:
        ValueError: If change not found or run is not in preview status
    """
    change = db.query(RunChange).filter(RunChange.id == change_id).first()
    if not change:
        raise ValueError(f"RunChange {change_id} not found")

    run = change.run
    if run.status != RunStatus.PREVIEW:
        raise ValueError(f"Run {run.id} is not in preview status")

    change.is_approved = is_approved
    db.commit()

    return change


def cancel_run(
    db: Session,
    run_id: int,
) -> Run:
    """
    Cancel a preview run.

    Args:
        db: Database session
        run_id: Run ID to cancel

    Returns:
        Cancelled Run

    Raises:
        ValueError: If run not found or not in preview status
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise ValueError(f"Run {run_id} not found")

    if run.status != RunStatus.PREVIEW:
        raise ValueError(f"Run {run_id} is not in preview status")

    run.status = RunStatus.CANCELLED
    db.commit()

    return run
