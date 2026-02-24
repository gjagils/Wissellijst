"""
Test script for PolicyValidator

Run this script to verify that the policy validator works correctly:
    python -m tests.test_validators
"""

from src.validators.policy_validator import PolicyValidator
from datetime import datetime, timedelta


def test_decade_distribution():
    """Test decade distribution validation"""
    print("\n=== Testing Decade Distribution ===")

    # Valid case: correct distribution
    candidates = [
        {"spotify_track_id": "1", "artist": "Queen", "title": "Bohemian Rhapsody", "decade": 1970},
        {"spotify_track_id": "2", "artist": "Nirvana", "title": "Smells Like Teen Spirit", "decade": 1990},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "decade": 2000},
    ]

    policy = {"1970s": 1, "1990s": 1, "2000s": 1}
    errors = PolicyValidator.validate_decade_distribution(candidates, policy)

    if not errors:
        print("✅ PASS: Valid decade distribution accepted")
    else:
        print(f"❌ FAIL: Expected no errors but got: {errors}")

    # Invalid case: wrong distribution
    candidates_invalid = [
        {"spotify_track_id": "1", "artist": "Queen", "title": "Bohemian Rhapsody", "decade": 1970},
        {"spotify_track_id": "2", "artist": "Queen", "title": "Another One Bites The Dust", "decade": 1970},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "decade": 2000},
    ]

    errors = PolicyValidator.validate_decade_distribution(candidates_invalid, policy)

    if errors and len(errors) == 2:  # 2 errors: 1970s has 2, 1990s has 0
        print(f"✅ PASS: Invalid decade distribution rejected with {len(errors)} errors")
        for err in errors:
            print(f"    - {err.message}")
    else:
        print(f"❌ FAIL: Expected 2 errors but got: {errors}")


def test_language_policy():
    """Test language policy validation"""
    print("\n=== Testing Language Policy ===")

    # Valid case: max 1 Dutch
    candidates = [
        {"spotify_track_id": "1", "artist": "Acda en de Munnik", "title": "Het Regent Zonnestralen", "language": "nl"},
        {"spotify_track_id": "2", "artist": "The Beatles", "title": "Yesterday", "language": "en"},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "language": "en"},
    ]

    policy = {"max_dutch_per_block": 1, "allow_dutch": True}
    errors = PolicyValidator.validate_language_policy(candidates, policy)

    if not errors:
        print("✅ PASS: Valid language policy accepted")
    else:
        print(f"❌ FAIL: Expected no errors but got: {errors}")

    # Invalid case: too many Dutch
    candidates_invalid = [
        {"spotify_track_id": "1", "artist": "Acda en de Munnik", "title": "Het Regent Zonnestralen", "language": "nl"},
        {"spotify_track_id": "2", "artist": "De Dijk", "title": "Bloedend Hart", "language": "nl"},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "language": "en"},
    ]

    errors = PolicyValidator.validate_language_policy(candidates_invalid, policy)

    if errors and "Too many Dutch tracks" in errors[0].message:
        print(f"✅ PASS: Too many Dutch tracks rejected: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected Dutch count error but got: {errors}")

    # Invalid case: Dutch not allowed
    policy_no_dutch = {"allow_dutch": False}
    errors = PolicyValidator.validate_language_policy(candidates, policy_no_dutch)

    if errors and "not allowed" in errors[0].message:
        print(f"✅ PASS: Dutch not allowed policy works: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected 'not allowed' error but got: {errors}")


def test_year_distribution():
    """Test year distribution validation"""
    print("\n=== Testing Year Distribution ===")

    # Valid case: 2 pre-2000, 2 post-2000, 1 wildcard
    candidates = [
        {"spotify_track_id": "1", "artist": "Queen", "title": "Bohemian Rhapsody", "year": 1975},
        {"spotify_track_id": "2", "artist": "Nirvana", "title": "Smells Like Teen Spirit", "year": 1991},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "year": 2000},
        {"spotify_track_id": "4", "artist": "Adele", "title": "Hello", "year": 2015},
        {"spotify_track_id": "5", "artist": "The Weeknd", "title": "Blinding Lights", "year": 2019},
    ]

    policy = {"pre_2000": 2, "post_2000": 2, "wildcard": 1}
    errors = PolicyValidator.validate_year_distribution(candidates, policy)

    if not errors:
        print("✅ PASS: Valid year distribution accepted")
    else:
        print(f"❌ FAIL: Expected no errors but got: {errors}")

    # Invalid case: not enough pre-2000
    candidates_invalid = [
        {"spotify_track_id": "1", "artist": "Queen", "title": "Bohemian Rhapsody", "year": 1975},
        {"spotify_track_id": "2", "artist": "Coldplay", "title": "Yellow", "year": 2000},
        {"spotify_track_id": "3", "artist": "Adele", "title": "Hello", "year": 2015},
        {"spotify_track_id": "4", "artist": "The Weeknd", "title": "Blinding Lights", "year": 2019},
        {"spotify_track_id": "5", "artist": "Ed Sheeran", "title": "Shape of You", "year": 2017},
    ]

    errors = PolicyValidator.validate_year_distribution(candidates_invalid, policy)

    if errors and "Not enough pre-2000" in errors[0].message:
        print(f"✅ PASS: Insufficient pre-2000 tracks rejected: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected pre-2000 error but got: {errors}")


def test_artist_limit():
    """Test artist limit validation"""
    print("\n=== Testing Artist Limit ===")

    # Valid case: max 1 per artist
    candidates = [
        {"spotify_track_id": "1", "artist": "Queen"},
        {"spotify_track_id": "2", "artist": "Nirvana"},
        {"spotify_track_id": "3", "artist": "Coldplay"},
    ]

    current_tracks = [
        {"artist": "The Beatles"},
        {"artist": "Pink Floyd"},
    ]

    errors = PolicyValidator.validate_artist_limit(candidates, current_tracks, max_per_artist=1)

    if not errors:
        print("✅ PASS: Valid artist limit accepted")
    else:
        print(f"❌ FAIL: Expected no errors but got: {errors}")

    # Invalid case: artist already in playlist
    candidates_invalid = [
        {"spotify_track_id": "1", "artist": "Queen"},
        {"spotify_track_id": "2", "artist": "The Beatles"},  # Already in playlist!
    ]

    errors = PolicyValidator.validate_artist_limit(candidates_invalid, current_tracks, max_per_artist=1)

    if errors and "The Beatles" in errors[0].message:
        print(f"✅ PASS: Duplicate artist rejected: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected duplicate artist error but got: {errors}")

    # Invalid case: duplicate artist in candidates
    candidates_dup = [
        {"spotify_track_id": "1", "artist": "Queen"},
        {"spotify_track_id": "2", "artist": "Queen"},  # Duplicate!
    ]

    errors = PolicyValidator.validate_artist_limit(candidates_dup, current_tracks, max_per_artist=1)

    if errors and "Queen" in errors[0].message:
        print(f"✅ PASS: Duplicate in candidates rejected: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected duplicate in candidates error but got: {errors}")


def test_history_validation():
    """Test history validation (no-repeat-ever and time-based)"""
    print("\n=== Testing History Validation ===")

    # Setup history
    now = datetime.utcnow()
    history = [
        {
            "spotify_track_id": "old_track_1",
            "first_added_at": now - timedelta(days=100),
            "last_removed_at": now - timedelta(days=95)
        },
        {
            "spotify_track_id": "recent_track_1",
            "first_added_at": now - timedelta(days=30),
            "last_removed_at": now - timedelta(days=25)
        },
    ]

    # Test no-repeat-ever
    candidates = [
        {"spotify_track_id": "new_track", "artist": "New Artist"},
        {"spotify_track_id": "old_track_1", "artist": "Old Artist"},  # In history!
    ]

    errors = PolicyValidator.validate_history(
        candidates, history, no_repeat_ever=True, history_window_months=None
    )

    if errors and "no-repeat-ever" in errors[0].message:
        print(f"✅ PASS: No-repeat-ever policy works: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected no-repeat-ever error but got: {errors}")

    # Test time-based (3 months)
    candidates_recent = [
        {"spotify_track_id": "new_track", "artist": "New Artist"},
        {"spotify_track_id": "recent_track_1", "artist": "Recent Artist"},  # Recent!
    ]

    errors = PolicyValidator.validate_history(
        candidates_recent, history, no_repeat_ever=False, history_window_months=3
    )

    if errors and "3 months" in errors[0].message:
        print(f"✅ PASS: Time-based history works: {errors[0].message}")
    else:
        print(f"❌ FAIL: Expected time-based error but got: {errors}")

    # Test time-based - old track should be allowed
    candidates_old = [
        {"spotify_track_id": "new_track", "artist": "New Artist"},
        {"spotify_track_id": "old_track_1", "artist": "Old Artist"},  # Old enough!
    ]

    errors = PolicyValidator.validate_history(
        candidates_old, history, no_repeat_ever=False, history_window_months=3
    )

    if not errors:
        print("✅ PASS: Old track allowed with time-based policy")
    else:
        print(f"❌ FAIL: Expected no errors for old track but got: {errors}")


def test_validate_all():
    """Test the validate_all function with a complete scenario"""
    print("\n=== Testing Complete Validation (Door de tijd heen example) ===")

    candidates = [
        {"spotify_track_id": "1", "artist": "Queen", "title": "Bohemian Rhapsody", "decade": 1980, "year": 1985, "language": "en"},
        {"spotify_track_id": "2", "artist": "Nirvana", "title": "Smells Like Teen Spirit", "decade": 1990, "year": 1991, "language": "en"},
        {"spotify_track_id": "3", "artist": "Coldplay", "title": "Yellow", "decade": 2000, "year": 2000, "language": "en"},
        {"spotify_track_id": "4", "artist": "Adele", "title": "Hello", "decade": 2010, "year": 2015, "language": "en"},
        {"spotify_track_id": "5", "artist": "Acda en de Munnik", "title": "Het Regent Zonnestralen", "decade": 2020, "year": 2020, "language": "nl"},
    ]

    current_tracks = []
    history = []

    rules = {
        "max_tracks_per_artist": 1,
        "no_repeat_ever": True,
        "candidate_policies": {
            "decade_distribution": {
                "1980s": 1,
                "1990s": 1,
                "2000s": 1,
                "2010s": 1,
                "2020s": 1
            },
            "language": {
                "max_dutch_per_block": 1,
                "allow_dutch": True
            }
        }
    }

    errors = PolicyValidator.validate_all(candidates, current_tracks, history, rules)

    if not errors:
        print("✅ PASS: Valid 'Door de tijd heen' block accepted")
        print("   Candidates:")
        for c in candidates:
            print(f"   - {c['artist']} - {c['title']} ({c['decade']}s, {c['language']})")
    else:
        print(f"❌ FAIL: Expected no errors but got: {errors}")


def run_all_tests():
    """Run all validator tests"""
    print("=" * 60)
    print("POLICY VALIDATOR TEST SUITE")
    print("=" * 60)

    test_decade_distribution()
    test_language_policy()
    test_year_distribution()
    test_artist_limit()
    test_history_validation()
    test_validate_all()

    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
