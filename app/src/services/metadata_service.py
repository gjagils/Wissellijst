"""
Metadata enrichment service.

Enriches track data with metadata like:
- Year and decade from release date
- Language detection (Dutch/English/Other)
- Genre tagging and classification
"""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime


class MetadataService:
    """Service for enriching track metadata"""

    # Common Dutch words for language detection
    DUTCH_INDICATORS = {
        "de", "het", "een", "en", "van", "op", "in", "voor", "met", "dit",
        "dat", "als", "maar", "niet", "ook", "te", "aan", "door", "bij",
        "naar", "over", "er", "uit", "om", "nog", "want", "zo", "mijn"
    }

    # Genre mapping from Spotify genres to simplified tags
    GENRE_MAPPING = {
        "soul": ["soul", "neo soul", "neo-soul", "classic soul"],
        "indie": ["indie", "indie rock", "indie pop", "indie folk"],
        "pop": ["pop", "dance pop", "art pop", "electropop"],
        "rock": ["rock", "classic rock", "alternative rock", "indie rock"],
        "electronic": ["electronic", "house", "techno", "edm", "electro"],
        "jazz": ["jazz", "smooth jazz", "jazz fusion"],
        "folk": ["folk", "folk rock", "indie folk"],
        "r&b": ["r&b", "r-n-b", "contemporary r&b"],
        "hip-hop": ["hip hop", "rap", "hip-hop", "trap"],
        "dutch": ["nederpop", "dutch", "nederlandse"],
    }

    @staticmethod
    def extract_year_and_decade(release_date: str) -> tuple[Optional[int], Optional[int]]:
        """
        Extract year and decade from Spotify release date.

        Args:
            release_date: Date string in format YYYY-MM-DD, YYYY-MM, or YYYY

        Returns:
            Tuple of (year, decade) where decade is like 1980, 1990, etc.
        """
        if not release_date:
            return None, None

        # Extract year from various formats
        year_match = re.match(r"^(\d{4})", release_date)
        if not year_match:
            return None, None

        year = int(year_match.group(1))

        # Calculate decade (e.g., 1987 -> 1980)
        decade = (year // 10) * 10

        return year, decade

    @staticmethod
    def detect_language(
        track_name: str,
        artist_name: str,
        spotify_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Detect track language (nl/en/other).

        Uses heuristics:
        1. Check if track is from Netherlands market
        2. Check for Dutch words in title
        3. Check for known Dutch artists
        4. Default to 'en'

        Args:
            track_name: Track title
            artist_name: Artist name
            spotify_data: Optional Spotify track data with 'available_markets'

        Returns:
            Language code: 'nl', 'en', or 'other'
        """
        # Check markets
        if spotify_data:
            markets = spotify_data.get("available_markets", [])
            # If ONLY available in NL/BE, likely Dutch
            if markets and set(markets).issubset({"NL", "BE"}):
                return "nl"

        # Check for Dutch words in title (simple approach)
        title_lower = track_name.lower()
        words = set(re.findall(r'\b\w+\b', title_lower))

        dutch_word_count = len(words.intersection(MetadataService.DUTCH_INDICATORS))
        if dutch_word_count >= 2:
            return "nl"

        # Known Dutch artists (simplified - could be expanded)
        dutch_artists = {"acda en de munnik", "stef bos", "bente", "de dijk", "volumia"}
        if artist_name.lower() in dutch_artists:
            return "nl"

        # Default to English
        return "en"

    @staticmethod
    def classify_genres(spotify_genres: List[str]) -> Dict[str, bool]:
        """
        Classify Spotify genres into simplified tags.

        Args:
            spotify_genres: List of Spotify genre strings

        Returns:
            Dict mapping simplified genre tags to bool (present or not)
        """
        genre_tags = {}

        if not spotify_genres:
            return genre_tags

        # Normalize input genres
        normalized = [g.lower() for g in spotify_genres]

        # Check each simplified genre
        for simplified, keywords in MetadataService.GENRE_MAPPING.items():
            # Check if any keyword matches
            matched = any(
                keyword in genre
                for genre in normalized
                for keyword in keywords
            )
            if matched:
                genre_tags[simplified] = True

        return genre_tags

    @staticmethod
    def enrich_track(
        track_id: str,
        artist: str,
        title: str,
        spotify_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enrich a track with metadata.

        Args:
            track_id: Spotify track ID
            artist: Artist name
            title: Track title
            spotify_data: Full Spotify track object (optional but recommended)

        Returns:
            Dict with enriched metadata:
                - spotify_track_id
                - artist
                - title
                - year
                - decade
                - language
                - genre_tags
        """
        enriched = {
            "spotify_track_id": track_id,
            "artist": artist,
            "title": title,
            "year": None,
            "decade": None,
            "language": "en",
            "genre_tags": {},
        }

        if not spotify_data:
            return enriched

        # Extract year and decade
        album = spotify_data.get("album", {})
        release_date = album.get("release_date")
        if release_date:
            year, decade = MetadataService.extract_year_and_decade(release_date)
            enriched["year"] = year
            enriched["decade"] = decade

        # Detect language
        enriched["language"] = MetadataService.detect_language(
            title, artist, spotify_data
        )

        # Classify genres (from artist data if available)
        # Note: Track objects don't have genres, need to fetch artist separately
        # For now, we'll use album genres if available
        genres = album.get("genres", [])
        if not genres:
            # Try artists
            artists = spotify_data.get("artists", [])
            if artists and isinstance(artists[0], dict):
                genres = artists[0].get("genres", [])

        enriched["genre_tags"] = MetadataService.classify_genres(genres)

        return enriched

    @staticmethod
    async def enrich_from_spotify_client(
        track_id: str,
        artist: str,
        title: str,
        spotify_client
    ) -> Dict[str, Any]:
        """
        Enrich a track by fetching full data from Spotify.

        Args:
            track_id: Spotify track ID
            artist: Artist name
            title: Track title
            spotify_client: SpotifyClient instance

        Returns:
            Enriched metadata dict
        """
        try:
            # Fetch full track data
            sp = spotify_client.get_spotify_client()
            track_data = sp.track(track_id)

            return MetadataService.enrich_track(track_id, artist, title, track_data)
        except Exception as e:
            print(f"Error enriching track {track_id}: {e}")
            # Return basic enrichment
            return MetadataService.enrich_track(track_id, artist, title, None)

    @staticmethod
    def enrich_batch(
        tracks: List[Dict[str, Any]],
        spotify_client
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple tracks (batch operation).

        Args:
            tracks: List of track dicts with 'spotify_track_id', 'artist', 'title'
            spotify_client: SpotifyClient instance

        Returns:
            List of enriched track dicts
        """
        enriched_tracks = []

        sp = spotify_client.get_spotify_client()

        # Spotify allows max 50 tracks per request
        batch_size = 50
        for i in range(0, len(tracks), batch_size):
            batch = tracks[i:i + batch_size]
            track_ids = [t["spotify_track_id"] for t in batch]

            try:
                # Fetch batch
                spotify_tracks = sp.tracks(track_ids)["tracks"]

                # Enrich each track
                for track, spotify_data in zip(batch, spotify_tracks):
                    enriched = MetadataService.enrich_track(
                        track["spotify_track_id"],
                        track["artist"],
                        track["title"],
                        spotify_data
                    )
                    enriched_tracks.append(enriched)

            except Exception as e:
                print(f"Error enriching batch: {e}")
                # Fallback to basic enrichment
                for track in batch:
                    enriched = MetadataService.enrich_track(
                        track["spotify_track_id"],
                        track["artist"],
                        track["title"],
                        None
                    )
                    enriched_tracks.append(enriched)

        return enriched_tracks
