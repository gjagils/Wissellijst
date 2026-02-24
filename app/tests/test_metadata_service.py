"""
Test script for MetadataService

Run this script to verify that the metadata enrichment service works correctly:
    python -m tests.test_metadata_service
"""

from src.services.metadata_service import MetadataService


def test_year_and_decade_extraction():
    """Test year and decade extraction from release dates"""
    print("\n=== Testing Year and Decade Extraction ===")

    test_cases = [
        ("1987-05-20", 1987, 1980),
        ("1999-12-31", 1999, 1990),
        ("2000-01-01", 2000, 2000),
        ("2015", 2015, 2010),
        ("2023-06", 2023, 2020),
        ("1975", 1975, 1970),
    ]

    all_passed = True
    for release_date, expected_year, expected_decade in test_cases:
        year, decade = MetadataService.extract_year_and_decade(release_date)

        if year == expected_year and decade == expected_decade:
            print(f"✅ PASS: {release_date} -> year={year}, decade={decade}")
        else:
            print(f"❌ FAIL: {release_date} -> Expected ({expected_year}, {expected_decade}), got ({year}, {decade})")
            all_passed = False

    # Test invalid dates
    year, decade = MetadataService.extract_year_and_decade("")
    if year is None and decade is None:
        print(f"✅ PASS: Empty string returns (None, None)")
    else:
        print(f"❌ FAIL: Empty string should return (None, None), got ({year}, {decade})")
        all_passed = False

    year, decade = MetadataService.extract_year_and_decade("invalid")
    if year is None and decade is None:
        print(f"✅ PASS: Invalid date returns (None, None)")
    else:
        print(f"❌ FAIL: Invalid date should return (None, None), got ({year}, {decade})")
        all_passed = False

    return all_passed


def test_language_detection():
    """Test language detection"""
    print("\n=== Testing Language Detection ===")

    test_cases = [
        # Dutch tracks
        ("Het Regent Zonnestralen", "Acda en de Munnik", "nl"),
        ("In Je Hoofd", "De Dijk", "nl"),
        ("Ik Heb Het Zo Gehad Met Jou", "Bente", "nl"),

        # English tracks
        ("Bohemian Rhapsody", "Queen", "en"),
        ("Yesterday", "The Beatles", "en"),
        ("Shape of You", "Ed Sheeran", "en"),

        # Known Dutch artists
        ("Mooi", "Stef Bos", "nl"),
    ]

    all_passed = True
    for track_name, artist_name, expected_lang in test_cases:
        detected_lang = MetadataService.detect_language(track_name, artist_name)

        if detected_lang == expected_lang:
            print(f"✅ PASS: '{track_name}' by {artist_name} -> {detected_lang}")
        else:
            print(f"❌ FAIL: '{track_name}' by {artist_name} -> Expected {expected_lang}, got {detected_lang}")
            all_passed = False

    return all_passed


def test_genre_classification():
    """Test genre classification"""
    print("\n=== Testing Genre Classification ===")

    test_cases = [
        # Soul genres
        (["soul", "neo soul"], {"soul"}),
        (["classic soul", "rhythm and blues"], {"soul"}),

        # Indie genres
        (["indie rock", "alternative"], {"indie", "rock"}),
        (["indie pop"], {"indie", "pop"}),

        # Pop genres
        (["pop", "dance pop"], {"pop"}),

        # Dutch
        (["nederpop", "dutch pop"], {"dutch", "pop"}),

        # Multiple genres
        (["indie folk", "folk rock"], {"indie", "folk", "rock"}),

        # Empty
        ([], set()),
    ]

    all_passed = True
    for spotify_genres, expected_tags in test_cases:
        result = MetadataService.classify_genres(spotify_genres)
        result_tags = set(result.keys())

        if result_tags == expected_tags:
            print(f"✅ PASS: {spotify_genres} -> {result_tags}")
        else:
            print(f"❌ FAIL: {spotify_genres} -> Expected {expected_tags}, got {result_tags}")
            all_passed = False

    return all_passed


def test_full_enrichment():
    """Test full track enrichment"""
    print("\n=== Testing Full Track Enrichment ===")

    # Test with mock Spotify data
    spotify_data = {
        "album": {
            "release_date": "1975-10-31",
            "genres": []
        },
        "artists": [
            {
                "name": "Queen",
                "genres": ["classic rock", "glam rock", "rock"]
            }
        ],
        "available_markets": ["US", "GB", "NL", "DE"]
    }

    enriched = MetadataService.enrich_track(
        track_id="abc123",
        artist="Queen",
        title="Bohemian Rhapsody",
        spotify_data=spotify_data
    )

    all_passed = True

    # Check year and decade
    if enriched["year"] == 1975 and enriched["decade"] == 1970:
        print(f"✅ PASS: Year and decade correctly extracted: {enriched['year']}, {enriched['decade']}s")
    else:
        print(f"❌ FAIL: Year/decade incorrect: {enriched['year']}, {enriched['decade']}")
        all_passed = False

    # Check language
    if enriched["language"] == "en":
        print(f"✅ PASS: Language correctly detected: {enriched['language']}")
    else:
        print(f"❌ FAIL: Language incorrect: {enriched['language']}")
        all_passed = False

    # Check genre tags
    if "rock" in enriched["genre_tags"]:
        print(f"✅ PASS: Genre tags correctly classified: {enriched['genre_tags']}")
    else:
        print(f"❌ FAIL: Genre tags incorrect: {enriched['genre_tags']}")
        all_passed = False

    # Test with Dutch track
    spotify_data_nl = {
        "album": {
            "release_date": "2020-03-15",
            "genres": ["nederpop", "dutch indie"]
        },
        "artists": [
            {
                "name": "Acda en de Munnik",
                "genres": ["nederpop"]
            }
        ],
        "available_markets": ["NL", "BE"]
    }

    enriched_nl = MetadataService.enrich_track(
        track_id="def456",
        artist="Acda en de Munnik",
        title="Het Regent Zonnestralen",
        spotify_data=spotify_data_nl
    )

    if enriched_nl["language"] == "nl":
        print(f"✅ PASS: Dutch track correctly detected: {enriched_nl['language']}")
    else:
        print(f"❌ FAIL: Dutch track not detected: {enriched_nl['language']}")
        all_passed = False

    if "dutch" in enriched_nl["genre_tags"]:
        print(f"✅ PASS: Dutch genre correctly classified")
    else:
        print(f"❌ FAIL: Dutch genre not detected: {enriched_nl['genre_tags']}")
        all_passed = False

    # Test without Spotify data (fallback)
    enriched_fallback = MetadataService.enrich_track(
        track_id="ghi789",
        artist="Unknown Artist",
        title="Unknown Title",
        spotify_data=None
    )

    if enriched_fallback["year"] is None and enriched_fallback["language"] == "en":
        print(f"✅ PASS: Fallback enrichment works correctly")
    else:
        print(f"❌ FAIL: Fallback enrichment incorrect")
        all_passed = False

    return all_passed


def test_example_playlists():
    """Test enrichment for example playlist tracks"""
    print("\n=== Testing Example Playlist Tracks ===")

    # "Door de tijd heen" example
    print("\n--- Door de tijd heen ---")
    tracks = [
        {
            "track_id": "1",
            "artist": "Survivor",
            "title": "Eye of the Tiger",
            "spotify_data": {
                "album": {"release_date": "1982-05-29"},
                "artists": [{"genres": ["rock", "hard rock"]}],
                "available_markets": ["US", "GB"]
            }
        },
        {
            "track_id": "2",
            "artist": "Alanis Morissette",
            "title": "Ironic",
            "spotify_data": {
                "album": {"release_date": "1995-06-13"},
                "artists": [{"genres": ["alternative rock", "pop rock"]}],
                "available_markets": ["US", "CA", "NL"]
            }
        },
        {
            "track_id": "3",
            "artist": "Coldplay",
            "title": "Viva La Vida",
            "spotify_data": {
                "album": {"release_date": "2008-06-12"},
                "artists": [{"genres": ["alternative rock", "indie rock"]}],
                "available_markets": ["GB", "US", "NL"]
            }
        },
    ]

    for track in tracks:
        enriched = MetadataService.enrich_track(
            track["track_id"],
            track["artist"],
            track["title"],
            track["spotify_data"]
        )
        print(f"  {enriched['artist']} - {enriched['title']}")
        print(f"    Year: {enriched['year']}, Decade: {enriched['decade']}s, Language: {enriched['language']}")
        print(f"    Genres: {list(enriched['genre_tags'].keys())}")

    # "In je moerstaal" example
    print("\n--- In je moerstaal ---")
    nl_tracks = [
        {
            "track_id": "4",
            "artist": "De Dijk",
            "title": "Bloedend Hart",
            "spotify_data": {
                "album": {"release_date": "1982-01-01"},
                "artists": [{"genres": ["nederpop", "dutch rock"]}],
                "available_markets": ["NL", "BE"]
            }
        },
        {
            "track_id": "5",
            "artist": "Bente",
            "title": "Zeg Me Wat Je Wilt",
            "spotify_data": {
                "album": {"release_date": "2019-09-20"},
                "artists": [{"genres": ["nederpop", "dutch pop"]}],
                "available_markets": ["NL", "BE"]
            }
        },
    ]

    for track in nl_tracks:
        enriched = MetadataService.enrich_track(
            track["track_id"],
            track["artist"],
            track["title"],
            track["spotify_data"]
        )
        print(f"  {enriched['artist']} - {enriched['title']}")
        print(f"    Year: {enriched['year']}, Decade: {enriched['decade']}s, Language: {enriched['language']}")
        print(f"    Genres: {list(enriched['genre_tags'].keys())}")


def run_all_tests():
    """Run all metadata service tests"""
    print("=" * 60)
    print("METADATA SERVICE TEST SUITE")
    print("=" * 60)

    results = []
    results.append(("Year/Decade Extraction", test_year_and_decade_extraction()))
    results.append(("Language Detection", test_language_detection()))
    results.append(("Genre Classification", test_genre_classification()))
    results.append(("Full Enrichment", test_full_enrichment()))

    test_example_playlists()

    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS FAILED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
