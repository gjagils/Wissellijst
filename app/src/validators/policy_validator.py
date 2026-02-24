"""
Policy validator for playlist refresh rules.

Validates candidate tracks against playlist rules like:
- Decade distribution (e.g., 1 from 80s, 1 from 90s, etc.)
- Language policies (max Dutch per block)
- Year distribution (pre/post 2000)
- Artist limits (max 1 track per artist)
- History deduplication (no repeat ever or time-based)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter


class ValidationError:
    """Represents a validation error"""

    def __init__(self, field: str, message: str, track_id: Optional[str] = None):
        self.field = field
        self.message = message
        self.track_id = track_id

    def __repr__(self):
        return f"ValidationError(field={self.field}, message={self.message}, track_id={self.track_id})"


class PolicyValidator:
    """Validates candidate tracks against playlist policies"""

    @staticmethod
    def validate_decade_distribution(
        candidates: List[Dict[str, Any]],
        policy: Dict[str, int]
    ) -> List[ValidationError]:
        """
        Validate that candidates match the decade distribution policy.

        Args:
            candidates: List of candidate tracks with 'decade' field
            policy: Dict mapping decade strings to required counts (e.g., {"1980s": 1, "1990s": 1})

        Returns:
            List of validation errors
        """
        errors = []

        if not policy:
            return errors

        # Count decades in candidates
        decade_counts = Counter()
        for candidate in candidates:
            decade = candidate.get("decade")
            if decade:
                # Convert decade int (1980) to string format (1980s)
                decade_str = f"{decade}s"
                decade_counts[decade_str] += 1

        # Check if distribution matches policy
        for decade, required_count in policy.items():
            actual_count = decade_counts.get(decade, 0)
            if actual_count != required_count:
                errors.append(
                    ValidationError(
                        field="decade_distribution",
                        message=f"Expected {required_count} track(s) from {decade}, got {actual_count}"
                    )
                )

        return errors

    @staticmethod
    def validate_language_policy(
        candidates: List[Dict[str, Any]],
        policy: Dict[str, Any]
    ) -> List[ValidationError]:
        """
        Validate language constraints.

        Args:
            candidates: List of candidate tracks with 'language' field
            policy: Dict with keys like:
                - "max_dutch_per_block": int
                - "allow_dutch": bool

        Returns:
            List of validation errors
        """
        errors = []

        if not policy:
            return errors

        dutch_count = sum(1 for c in candidates if c.get("language") == "nl")

        # Check if Dutch is allowed at all
        if not policy.get("allow_dutch", True) and dutch_count > 0:
            errors.append(
                ValidationError(
                    field="language",
                    message="Dutch language tracks not allowed"
                )
            )

        # Check max Dutch per block
        max_dutch = policy.get("max_dutch_per_block")
        if max_dutch is not None and dutch_count > max_dutch:
            errors.append(
                ValidationError(
                    field="language",
                    message=f"Too many Dutch tracks: {dutch_count} (max: {max_dutch})"
                )
            )

        return errors

    @staticmethod
    def validate_year_distribution(
        candidates: List[Dict[str, Any]],
        policy: Dict[str, int]
    ) -> List[ValidationError]:
        """
        Validate year distribution (e.g., 2 from pre-2000, 2 from post-2000, 1 wildcard).

        Args:
            candidates: List of candidate tracks with 'year' field
            policy: Dict with keys like:
                - "pre_2000": int
                - "post_2000": int
                - "wildcard": int

        Returns:
            List of validation errors
        """
        errors = []

        if not policy:
            return errors

        pre_2000_count = sum(1 for c in candidates if c.get("year") and c["year"] < 2000)
        post_2000_count = sum(1 for c in candidates if c.get("year") and c["year"] >= 2000)

        required_pre = policy.get("pre_2000", 0)
        required_post = policy.get("post_2000", 0)
        required_wildcard = policy.get("wildcard", 0)

        total_required = required_pre + required_post + required_wildcard

        # Check if we have enough tracks
        if len(candidates) < total_required:
            errors.append(
                ValidationError(
                    field="year_distribution",
                    message=f"Not enough candidates: {len(candidates)} (required: {total_required})"
                )
            )
            return errors

        # Check minimum requirements (wildcard can fill gaps)
        if pre_2000_count < required_pre:
            deficit = required_pre - pre_2000_count
            errors.append(
                ValidationError(
                    field="year_distribution",
                    message=f"Not enough pre-2000 tracks: {pre_2000_count} (required: {required_pre})"
                )
            )

        if post_2000_count < required_post:
            deficit = required_post - post_2000_count
            errors.append(
                ValidationError(
                    field="year_distribution",
                    message=f"Not enough post-2000 tracks: {post_2000_count} (required: {required_post})"
                )
            )

        return errors

    @staticmethod
    def validate_artist_limit(
        candidates: List[Dict[str, Any]],
        current_tracks: List[Dict[str, Any]],
        max_per_artist: int
    ) -> List[ValidationError]:
        """
        Validate that no artist appears more than max_per_artist times.

        Args:
            candidates: List of candidate tracks with 'artist' field
            current_tracks: List of current tracks in the playlist
            max_per_artist: Maximum tracks per artist

        Returns:
            List of validation errors
        """
        errors = []

        # Count artists in current playlist
        artist_counts = Counter(track.get("artist") for track in current_tracks)

        # Check candidates
        for candidate in candidates:
            artist = candidate.get("artist")
            if not artist:
                continue

            # Increment count with this candidate
            new_count = artist_counts.get(artist, 0) + 1

            if new_count > max_per_artist:
                errors.append(
                    ValidationError(
                        field="artist_limit",
                        message=f"Artist '{artist}' would exceed limit ({new_count} > {max_per_artist})",
                        track_id=candidate.get("spotify_track_id")
                    )
                )
            else:
                # Add to count for next candidates
                artist_counts[artist] = new_count

        return errors

    @staticmethod
    def validate_history(
        candidates: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        no_repeat_ever: bool,
        history_window_months: Optional[int] = None
    ) -> List[ValidationError]:
        """
        Validate against track history (no-repeat-ever or time-based).

        Args:
            candidates: List of candidate tracks with 'spotify_track_id'
            history: List of historical tracks with 'spotify_track_id', 'first_added_at', 'last_removed_at'
            no_repeat_ever: If True, tracks can never be repeated
            history_window_months: If set, tracks can't repeat within X months

        Returns:
            List of validation errors
        """
        errors = []

        if not history:
            return errors

        # Build set of blocked track IDs
        blocked_tracks = set()

        if no_repeat_ever:
            # All historical tracks are blocked
            blocked_tracks = {h["spotify_track_id"] for h in history}
        elif history_window_months:
            # Only recent tracks are blocked
            cutoff_date = datetime.utcnow() - timedelta(days=history_window_months * 30)
            for h in history:
                last_removed = h.get("last_removed_at")
                if last_removed and last_removed > cutoff_date:
                    blocked_tracks.add(h["spotify_track_id"])

        # Check candidates
        for candidate in candidates:
            track_id = candidate.get("spotify_track_id")
            if track_id in blocked_tracks:
                if no_repeat_ever:
                    errors.append(
                        ValidationError(
                            field="history",
                            message=f"Track has been played before (no-repeat-ever policy)",
                            track_id=track_id
                        )
                    )
                else:
                    errors.append(
                        ValidationError(
                            field="history",
                            message=f"Track played within last {history_window_months} months",
                            track_id=track_id
                        )
                    )

        return errors

    @staticmethod
    def validate_all(
        candidates: List[Dict[str, Any]],
        current_tracks: List[Dict[str, Any]],
        history: List[Dict[str, Any]],
        rules: Dict[str, Any]
    ) -> List[ValidationError]:
        """
        Run all validations.

        Args:
            candidates: List of candidate tracks
            current_tracks: List of current tracks in playlist
            history: List of historical tracks
            rules: Playlist rules dict with:
                - max_tracks_per_artist: int
                - no_repeat_ever: bool
                - candidate_policies: Dict with decade_distribution, language, etc.

        Returns:
            List of all validation errors
        """
        all_errors = []

        # Extract policies
        candidate_policies = rules.get("candidate_policies", {})

        # Validate decade distribution
        decade_policy = candidate_policies.get("decade_distribution")
        if decade_policy:
            all_errors.extend(
                PolicyValidator.validate_decade_distribution(candidates, decade_policy)
            )

        # Validate language
        language_policy = candidate_policies.get("language")
        if language_policy:
            all_errors.extend(
                PolicyValidator.validate_language_policy(candidates, language_policy)
            )

        # Validate year distribution
        year_policy = candidate_policies.get("year_distribution")
        if year_policy:
            all_errors.extend(
                PolicyValidator.validate_year_distribution(candidates, year_policy)
            )

        # Validate artist limit
        max_per_artist = rules.get("max_tracks_per_artist", 1)
        all_errors.extend(
            PolicyValidator.validate_artist_limit(candidates, current_tracks, max_per_artist)
        )

        # Validate history
        no_repeat_ever = rules.get("no_repeat_ever", True)
        history_window_months = candidate_policies.get("history_window_months")
        all_errors.extend(
            PolicyValidator.validate_history(
                candidates, history, no_repeat_ever, history_window_months
            )
        )

        return all_errors
