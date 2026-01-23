from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.db import models
from src.ai_candidates import build_candidates_ai

Playlist = models.Playlist
PlaylistRules = models.PlaylistRules

# optional models (bestaan bij jou al volgens eerdere log)
PlaylistBlock = getattr(models, "PlaylistBlock", None)
BlockTrack = getattr(models, "BlockTrack", None)
PlaylistTrackHistory = getattr(models, "PlaylistTrackHistory", None)


def _to_track_out(t: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": t.get("id"),
        "artist": t.get("artist"),
        "title": t.get("title"),
        "popularity": t.get("popularity"),
        "reason": t.get("reason"),
        "decade": t.get("decade"),
    }


def _chunk(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def bootstrap_preview(
    db: Session,
    spotify: Any,
    playlist_key: str,
    target_total: int = 50,
    block_size: int = 5,
    fill_mode: str = "append",
    batch_size: int = 15,
    max_rounds: int = 10,
) -> Dict[str, Any]:
    pl = db.query(Playlist).filter(Playlist.key == playlist_key).first()
    if not pl:
        raise ValueError(f"Unknown playlist_key: {playlist_key}")

    rules = db.query(PlaylistRules).filter(PlaylistRules.playlist_id == pl.id).first()
    vibe = getattr(pl, "vibe", "") or ""
    max_tracks_per_artist = getattr(rules, "max_tracks_per_artist", 1) if rules else 1

    current_tracks = spotify.get_playlist_tracks(pl.spotify_playlist_id)
    if fill_mode == "replace":
        current_tracks = []

    current_count = len(current_tracks)
    needed = max(0, target_total - current_count)

    # early return
    if needed == 0:
        blocks = [{"index": i, "tracks": chunk} for i, chunk in enumerate(_chunk(current_tracks, block_size))]
        return {
            "playlist_key": playlist_key,
            "current_count": len(current_tracks),
            "needed": 0,
            "target_total": target_total,
            "block_size": block_size,
            "blocks": blocks,
            "add": [],
            "filtered": {"in_playlist": 0, "artist_limit": 0, "in_history": 0},
        }

    avoid = [{"artist": t["artist"], "title": t["title"]} for t in current_tracks]

    add: List[Dict[str, Any]] = []
    filtered_counts = {"in_playlist": 0, "artist_limit": 0, "in_history": 0}

    artist_counts: Dict[str, int] = {}
    for t in current_tracks:
        artist_counts[t["artist"]] = artist_counts.get(t["artist"], 0) + 1

    rounds = 0
    while len(add) < needed and rounds < max_rounds:
        rounds += 1

        candidates = build_candidates_ai(
            vibe=vibe,
            rules={
                "max_tracks_per_artist": max_tracks_per_artist,
                "no_duplicates": True,
            },
            current_playlist=avoid,
            spotify_client=spotify,
            n=batch_size,
        )

        for c in candidates:
            if len(add) >= needed:
                break

            key = (c["artist"].lower(), c["title"].lower())
            if any((t["artist"].lower(), t["title"].lower()) == key for t in current_tracks):
                filtered_counts["in_playlist"] += 1
                continue

            a = c["artist"]
            if artist_counts.get(a, 0) >= max_tracks_per_artist:
                filtered_counts["artist_limit"] += 1
                continue

            add.append(_to_track_out(c))
            artist_counts[a] = artist_counts.get(a, 0) + 1

        for t in add:
            avoid.append({"artist": t["artist"], "title": t["title"]})

    combined = current_tracks + add
    blocks = [{"index": i, "tracks": chunk} for i, chunk in enumerate(_chunk(combined, block_size))]

    return {
        "playlist_key": playlist_key,
        "current_count": len(current_tracks),
        "needed": needed,
        "target_total": target_total,
        "block_size": block_size,
        "blocks": blocks,
        "add": add,
        "filtered": filtered_counts,
    }


def bootstrap_commit(
    db: Session,
    spotify: Any,
    playlist_key: str,
    target_total: int = 50,
    block_size: int = 5,
    fill_mode: str = "replace",
    batch_size: int = 15,
    max_rounds: int = 10,
) -> Dict[str, Any]:
    if not PlaylistBlock or not BlockTrack or not PlaylistTrackHistory:
        raise RuntimeError("DB models missing: PlaylistBlock/BlockTrack/PlaylistTrackHistory")

    preview = bootstrap_preview(
        db=db,
        spotify=spotify,
        playlist_key=playlist_key,
        target_total=target_total,
        block_size=block_size,
        fill_mode=fill_mode,
        batch_size=batch_size,
        max_rounds=max_rounds,
    )

    pl = db.query(Playlist).filter(Playlist.key == playlist_key).first()
    if not pl:
        raise ValueError(f"Unknown playlist_key: {playlist_key}")

    now = datetime.now(timezone.utc)

    # wipe existing blocks for this playlist (safe for bootstrap "replace")
    db.query(BlockTrack).filter(BlockTrack.playlist_id == pl.id).delete()
    db.query(PlaylistBlock).filter(PlaylistBlock.playlist_id == pl.id).delete()

    # write blocks + block_tracks
    for b in preview["blocks"]:
        block = PlaylistBlock(
            playlist_id=pl.id,
            block_index=b["index"],
            created_at=now,
        )
        db.add(block)
        db.flush()  # get block.id

        for pos, t in enumerate(b["tracks"]):
            db.add(
                BlockTrack(
                    playlist_id=pl.id,
                    block_id=block.id,
                    position=pos,
                    spotify_track_id=t["id"],
                    artist=t.get("artist"),
                    title=t.get("title"),
                    popularity=t.get("popularity"),
                    reason=t.get("reason"),
                    created_at=now,
                )
            )

    # history: mark all current block tracks as "added"
    for b in preview["blocks"]:
        for t in b["tracks"]:
            db.add(
                PlaylistTrackHistory(
                    playlist_id=pl.id,
                    spotify_track_id=t["id"],
                    artist=t.get("artist"),
                    title=t.get("title"),
                    action="added",
                    at=now,
                )
            )

    db.commit()

    return {
        "playlist_key": playlist_key,
        "written_to_db": True,
        "target_total": preview["target_total"],
        "block_size": preview["block_size"],
        "blocks": preview["blocks"],
        "filtered": preview["filtered"],
    }
