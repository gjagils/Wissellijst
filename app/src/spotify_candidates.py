from typing import List, Dict, Any, Tuple

raw_collected_count = 0
top_tracks_calls = 0
top_tracks_total_seen = 0

from spotipy.exceptions import SpotifyException

def _safe_track(sp, track_id: str, market: str | None):
    """
    Try with market first. If 404, retry WITHOUT any market parameter using sp._get.
    Returns dict or None if truly not found.
    """
    try:
        if market:
            return sp.track(track_id, market=market)
        # also avoid sp.track(track_id) because spotipy sends market=None
        return sp._get("tracks/" + track_id)
    except SpotifyException as e:
        if getattr(e, "http_status", None) == 404 and market:
            try:
                # No market parameter at all:
                return sp._get("tracks/" + track_id)
            except SpotifyException as e2:
                if getattr(e2, "http_status", None) == 404:
                    return None
                raise
        raise



def _collect_playlist_track_ids(sp, playlist_id: str) -> set[str]:
    ids = set()
    offset = 0
    while True:
        data = sp.playlist_items(
            playlist_id,
            limit=100,
            offset=offset,
            additional_types=("track",),
        )
        for it in data.get("items", []):
            t = it.get("track")
            if t and t.get("id"):
                ids.add(t["id"])
        if not data.get("next"):
            break
        offset += 100
    return ids



def build_candidates(
    sp,
    playlist_id: str,
    seed_tracks: List[str],
    market: str = "NL",
    max_seed_artists_per_track: int = 2,
    max_related_per_seed_artist: int = 8,
    top_tracks_per_related_artist: int = 5,
    max_candidates: int = 200,
):
    """
    Discovery flow:
      seed tracks -> seed artists -> related artists -> top tracks
    """

    if not seed_tracks:
        return [], {
            "excluded_existing_count": 0,
            "raw_collected_count": 0,
            "unique_count": 0,
        }
    existing_ids = _collect_playlist_track_ids(sp, playlist_id)
    seed_ids = set(seed_tracks)

    # -------------------------------------------------
    # 1) seed tracks -> seed artists
    # -------------------------------------------------
    seed_artist_pairs: List[Tuple[str, str]] = []
    invalid_seed_tracks: List[str] = []

    for tid in seed_tracks:
        try:
            tr = _safe_track(sp, tid, market)
            if tr is None:
                invalid_seed_tracks.append(tid)
                continue

        except SpotifyException as e:
            # Fallback: sommige tracks geven 404 per market maar bestaan wel
            if getattr(e, "http_status", None) == 404 and market:
                try:
                    tr = sp.track(tid)  # zonder market
                except SpotifyException as e2:
                    if getattr(e2, "http_status", None) == 404:
                        invalid_seed_tracks.append(tid)
                        continue
                    else:
                        raise
            else:
                raise

        artists = tr.get("artists") or []
        for a in artists[:max_seed_artists_per_track]:
            if a.get("id"):
                seed_artist_pairs.append((tid, a["id"]))

    # Guard: geen geldige seeds
    if not seed_artist_pairs:
        return [], {
            "excluded_existing_count": 0,
            "raw_collected_count": 0,
            "unique_count": 0,
            "invalid_seed_tracks": invalid_seed_tracks,
        }

    # -------------------------------------------------
    # 2) seed artists -> related artists
    # -------------------------------------------------
    related_artist_ids: List[str] = []

    for _, seed_artist_id in seed_artist_pairs:
        rel = sp.artist_related_artists(seed_artist_id)
        artists = (rel.get("artists") or [])[:max_related_per_seed_artist]

        for ra in artists:
            if ra.get("id"):
                related_artist_ids.append(ra["id"])

    # Fallback: geen related artists → gebruik seed artists zelf
    if not related_artist_ids:
        related_artist_ids = list({aid for _, aid in seed_artist_pairs})


    # -------------------------------------------------
    # 3) related artists -> top tracks
    # -------------------------------------------------
    seen = set()
    candidates: List[Dict[str, Any]] = []

    for artist_id in related_artist_ids:
        tops = sp.artist_top_tracks(artist_id, country=market)
        for t in tops.get("tracks", [])[:top_tracks_per_related_artist]:
            tid = t.get("id")
            if (
                not tid
                or tid in seen
                or tid in existing_ids   # al in playlist
                or tid in seed_ids       # seed zelf
            ):
                continue

            top_tracks_calls += 1
            tracks = tops.get("tracks", [])[:top_tracks_per_related_artist]
            top_tracks_total_seen += len(tracks)
            for t in tracks:
                ...
                raw_collected_count += 1



            seen.add(tid)
            candidates.append({
                "track_id": tid,
                "name": t.get("name"),
                "artists": [a.get("name") for a in t.get("artists", [])],
                "popularity": t.get("popularity"),
                "spotify_url": (t.get("external_urls") or {}).get("spotify"),
            })

            if len(candidates) >= max_candidates:
                break

    return candidates, {
        "excluded_existing_count": len(existing_ids),
        "raw_collected_count": raw_collected_count,
        "unique_count": len(candidates),
        "invalid_seed_tracks": invalid_seed_tracks,
        "seed_artist_pairs_count": len(seed_artist_pairs),
        "related_artist_ids_count": len(related_artist_ids),
        "top_tracks_calls": top_tracks_calls,
        "top_tracks_total_seen": top_tracks_total_seen,
    }
