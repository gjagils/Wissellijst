"""
AI-driven candidate track builder using OpenAI.

This module generates candidate tracks for playlist rotation using:
1. OpenAI API for intelligent track suggestions based on vibe and policies
2. Spotify API for validation and metadata enrichment
3. Policy-aware suggestions (decade, language, year distributions)
"""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional
import openai
from openai import OpenAI

from src.services.metadata_service import MetadataService


def _rules_to_text(rules: Any) -> str:
    """
    Convert rules object/dict to human-readable prompt text.

    Works with:
      - SQLAlchemy model (attributes)
      - Pydantic model (attributes)
      - dict
      - None
    """
    if rules is None:
        return ""

    def get(name: str, default=None):
        if isinstance(rules, dict):
            return rules.get(name, default)
        return getattr(rules, name, default)

    parts: List[str] = []

    max_per_artist = get("max_tracks_per_artist", None)
    if max_per_artist is not None:
        parts.append(f"Max {max_per_artist} track(s) per artist in the active playlist.")

    no_repeat = get("no_repeat_ever", None)
    if no_repeat is True:
        parts.append("A track may never be repeated (no-repeat-ever).")

    candidate_policies = get("candidate_policies", None)
    if candidate_policies:
        if isinstance(candidate_policies, dict):
            # Decade distribution
            decade_dist = candidate_policies.get("decade_distribution")
            if decade_dist:
                decade_text = ", ".join([f"{count} from {decade}" for decade, count in decade_dist.items()])
                parts.append(f"Decade distribution: {decade_text}")

            # Language policy
            lang_policy = candidate_policies.get("language")
            if lang_policy:
                if isinstance(lang_policy, dict):
                    max_dutch = lang_policy.get("max_dutch_per_block")
                    allow_dutch = lang_policy.get("allow_dutch", True)

                    if not allow_dutch:
                        parts.append("NO Dutch language tracks allowed")
                    elif max_dutch is not None:
                        parts.append(f"Maximum {max_dutch} Dutch language track(s) per block")

            # Year distribution
            year_dist = candidate_policies.get("year_distribution")
            if year_dist:
                year_text = ", ".join([f"{count} from {period.replace('_', ' ')}" for period, count in year_dist.items()])
                parts.append(f"Year distribution: {year_text}")

            # History window
            history_months = candidate_policies.get("history_window_months")
            if history_months:
                parts.append(f"Tracks cannot repeat within {history_months} months")

            # Genre constraints
            genre_constraints = candidate_policies.get("genre_constraints")
            if genre_constraints:
                required_genres = genre_constraints.get("required", [])
                if required_genres:
                    parts.append(f"Required genres: {', '.join(required_genres)}")

    return "\n".join(parts) if parts else "No specific rules"


def _build_openai_prompt(
    vibe: str,
    current_tracks: List[Dict[str, Any]],
    n_candidates: int,
    rules: Any,
    playlist_key: Optional[str] = None,
) -> str:
    """
    Build a detailed prompt for OpenAI to generate track suggestions.
    """
    rules_text = _rules_to_text(rules)

    # Extract current artists to avoid duplicates
    current_artists = list(set([track.get("artist", "") for track in current_tracks if track.get("artist")]))
    current_artists_text = ", ".join(current_artists[:20]) if current_artists else "None"

    prompt = f"""You are a music curator helping to select tracks for a playlist.

PLAYLIST VIBE:
{vibe}

RULES:
{rules_text}

CURRENT ARTISTS IN PLAYLIST (avoid these):
{current_artists_text}

TASK:
Suggest exactly {n_candidates} tracks that match the vibe and follow the rules.

REQUIREMENTS:
1. Provide diverse tracks that fit the vibe
2. DO NOT suggest artists that are already in the playlist
3. Follow ALL the rules specified above (decade distribution, language policy, etc.)
4. Provide well-known, verifiable tracks (must exist on Spotify)
5. Include a brief reason why each track fits

OUTPUT FORMAT (valid JSON array):
[
  {{
    "artist": "Artist Name",
    "title": "Track Title",
    "reason": "Brief explanation why this fits"
  }},
  ...
]

IMPORTANT: Output ONLY the JSON array, no additional text."""

    return prompt


def _parse_openai_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Parse OpenAI response and extract track suggestions.

    Handles:
    - Clean JSON arrays
    - JSON wrapped in markdown code blocks
    - Malformed responses
    """
    # Try to extract JSON from markdown code blocks
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        response_text = response_text[start:end].strip()

    try:
        suggestions = json.loads(response_text)
        if not isinstance(suggestions, list):
            return []

        # Validate structure
        valid_suggestions = []
        for suggestion in suggestions:
            if isinstance(suggestion, dict) and "artist" in suggestion and "title" in suggestion:
                valid_suggestions.append({
                    "artist": suggestion["artist"],
                    "title": suggestion["title"],
                    "reason": suggestion.get("reason", "AI suggested track"),
                })

        return valid_suggestions

    except json.JSONDecodeError:
        print(f"Failed to parse OpenAI response as JSON: {response_text[:200]}")
        return []


def _validate_with_spotify(
    suggestions: List[Dict[str, Any]],
    spotify_client,
) -> List[Dict[str, Any]]:
    """
    Validate AI suggestions against Spotify and enrich with metadata.

    Returns only tracks that exist on Spotify with full metadata.
    """
    validated_tracks = []

    sp = spotify_client.get_spotify_client()

    for suggestion in suggestions:
        artist = suggestion["artist"]
        title = suggestion["title"]
        reason = suggestion.get("reason", "AI suggested track")

        try:
            # Search for track on Spotify
            query = f"artist:{artist} track:{title}"
            results = sp.search(q=query, type="track", limit=1)

            if results["tracks"]["items"]:
                track = results["tracks"]["items"][0]

                # Extract basic info
                spotify_track_id = track["id"]
                artist_name = track["artists"][0]["name"]
                track_title = track["name"]

                # Enrich with metadata
                enriched = MetadataService.enrich_track(
                    spotify_track_id,
                    artist_name,
                    track_title,
                    track
                )

                # Add reason from AI
                enriched["reason"] = reason

                validated_tracks.append(enriched)
            else:
                print(f"Track not found on Spotify: {artist} - {title}")

        except Exception as e:
            print(f"Error validating track {artist} - {title}: {e}")
            continue

    return validated_tracks


def build_candidates_ai(
    *,
    vibe: str,
    current_tracks: List[Dict[str, Any]],
    n_candidates: int = 15,
    rules: Any = None,
    playlist_key: Optional[str] = None,
    spotify_client = None,
) -> List[Dict[str, Any]]:
    """
    AI-first candidate builder using OpenAI + Spotify validation.

    Args:
        vibe: Textual description of the playlist's musical taste
        current_tracks: List of tracks currently in the playlist
        n_candidates: Number of candidate tracks to generate
        rules: Playlist rules (can be dict, Pydantic model, or SQLAlchemy model)
        playlist_key: Optional playlist identifier for logging
        spotify_client: SpotifyClient instance for validation

    Returns:
        List of candidate track dicts with:
          - spotify_track_id
          - artist
          - title
          - year
          - decade
          - language
          - genre_tags
          - reason (why AI suggested this track)
    """

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    # Check for Spotify client
    if spotify_client is None:
        raise ValueError("spotify_client is required for validation")

    # Initialize OpenAI client
    client = OpenAI(api_key=api_key)

    # Build prompt
    prompt = _build_openai_prompt(vibe, current_tracks, n_candidates, rules, playlist_key)

    print(f"Requesting {n_candidates} AI suggestions for playlist '{playlist_key}'...")

    try:
        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional music curator with deep knowledge of music across all genres and decades."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.8,  # Some creativity but not too random
            max_tokens=2000,
        )

        # Extract response text
        response_text = response.choices[0].message.content

        # Parse suggestions
        suggestions = _parse_openai_response(response_text)

        print(f"OpenAI returned {len(suggestions)} suggestions")

        if not suggestions:
            print("Warning: No valid suggestions from OpenAI")
            return []

        # Validate with Spotify and enrich metadata
        validated_tracks = _validate_with_spotify(suggestions, spotify_client)

        print(f"Validated {len(validated_tracks)} tracks with Spotify")

        return validated_tracks

    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        # Fallback: return empty list (caller can use Spotify-based candidates)
        return []
