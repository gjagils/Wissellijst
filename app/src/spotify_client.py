import os
from typing import List, Dict, Optional

import spotipy
from spotipy.oauth2 import SpotifyOAuth


def _auth_manager() -> SpotifyOAuth:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Spotify credentials not set (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET)"
        )

    scope = "playlist-read-private playlist-modify-public playlist-modify-private user-read-email"

    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=scope,
        open_browser=False,
        cache_path="/app/.secrets/spotify_cache",
    )


def get_auth_url() -> str:
    return _auth_manager().get_authorize_url()


def handle_callback(code: str) -> None:
    _auth_manager().get_access_token(code, as_dict=False)


class SpotifyClient:
    def __init__(self) -> None:
        self.sp = spotipy.Spotify(auth_manager=_auth_manager())

    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        results: List[Dict] = []
        offset = 0
        limit = 100

        while True:
            page = self.sp.playlist_items(
                playlist_id,
                offset=offset,
                limit=limit,
                additional_types=["track"],
            )

            for item in page.get("items", []):
                track = item.get("track")
                if not track:
                    continue

                artists = track.get("artists") or []
                artist_name = artists[0]["name"] if artists else "Unknown"

                results.append(
                    {
                        "id": track["id"],
                        "artist": artist_name,
                        "title": track["name"],
                        "popularity": track.get("popularity"),
                    }
                )

            if page.get("next"):
                offset += limit
            else:
                break

        return results

    def search_track(self, artist: str, title: str) -> Optional[Dict]:
        q = f'artist:"{artist}" track:"{title}"'
        res = self.sp.search(q=q, type="track", limit=1)

        items = res.get("tracks", {}).get("items", [])
        if not items:
            return None

        track = items[0]
        artists = track.get("artists") or []
        artist_name = artists[0]["name"] if artists else "Unknown"

        return {
            "id": track["id"],
            "artist": artist_name,
            "title": track["name"],
            "popularity": track.get("popularity"),
        }

    def get_user_playlists(self) -> List[Dict]:
        """Get all playlists of the current user"""
        results: List[Dict] = []
        offset = 0
        limit = 50

        while True:
            page = self.sp.current_user_playlists(offset=offset, limit=limit)

            for item in page.get("items", []):
                results.append({
                    "id": item["id"],
                    "name": item["name"],
                    "description": item.get("description", ""),
                    "tracks_total": item.get("tracks", {}).get("total", 0),
                    "image_url": item["images"][0]["url"] if item.get("images") else None,
                    "owner": item.get("owner", {}).get("display_name", "Unknown"),
                })

            if page.get("next"):
                offset += limit
            else:
                break

        return results
