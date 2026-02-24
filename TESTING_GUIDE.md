# Testing Guide - Sprint 1

Deze guide helpt je om alle Sprint 1 functionaliteit te testen.

## Quick Start

### Automatisch testen met deployment script

```bash
# Op je Synology (of development machine)
cd /path/to/Wissellijst
./deploy_sprint1.sh
```

Dit script voert automatisch uit:
- Container rebuild
- Database migratie
- PolicyValidator tests
- MetadataService tests
- API health check

### Handmatig testen

Als je de tests handmatig wilt draaien:

```bash
# Start containers
docker compose up -d

# Voer migratie uit
docker compose exec app alembic upgrade head

# Run tests
docker compose exec app python -m tests.test_validators
docker compose exec app python -m tests.test_metadata_service
```

## Test Scenarios

### Scenario 1: "Door de tijd heen" Playlist Validatie

Test of een geldig blok voor "Door de tijd heen" geaccepteerd wordt.

**In Python shell:**

```bash
docker compose exec app python
```

```python
from src.validators.policy_validator import PolicyValidator

# Definieer kandidaten (1 per decennium, max 1 Nederlands)
candidates = [
    {
        "spotify_track_id": "1",
        "artist": "Queen",
        "title": "Bohemian Rhapsody",
        "decade": 1980,
        "language": "en"
    },
    {
        "spotify_track_id": "2",
        "artist": "Nirvana",
        "title": "Smells Like Teen Spirit",
        "decade": 1990,
        "language": "en"
    },
    {
        "spotify_track_id": "3",
        "artist": "Coldplay",
        "title": "Yellow",
        "decade": 2000,
        "language": "en"
    },
    {
        "spotify_track_id": "4",
        "artist": "Adele",
        "title": "Hello",
        "decade": 2010,
        "language": "en"
    },
    {
        "spotify_track_id": "5",
        "artist": "Acda en de Munnik",
        "title": "Het Regent Zonnestralen",
        "decade": 2020,
        "language": "nl"
    }
]

# Rules voor "Door de tijd heen"
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

# Valideer
errors = PolicyValidator.validate_all(candidates, [], [], rules)

# Controleer resultaat
if not errors:
    print("✅ VALID: Block is accepted!")
    for c in candidates:
        print(f"  - {c['artist']}: {c['title']} ({c['decade']}s, {c['language']})")
else:
    print("❌ INVALID:")
    for err in errors:
        print(f"  - {err.message}")
```

**Verwacht resultaat**: ✅ VALID

### Scenario 2: "In je moerstaal" Playlist Validatie

Test year distribution policy (2 pre-2000, 2 post-2000, 1 wildcard).

```python
from src.validators.policy_validator import PolicyValidator

candidates = [
    {"spotify_track_id": "1", "artist": "Acda en de Munnik", "year": 1997, "language": "nl"},
    {"spotify_track_id": "2", "artist": "De Dijk", "year": 1982, "language": "nl"},
    {"spotify_track_id": "3", "artist": "Bente", "year": 2019, "language": "nl"},
    {"spotify_track_id": "4", "artist": "Volumia", "year": 2015, "language": "nl"},
    {"spotify_track_id": "5", "artist": "Stef Bos", "year": 2005, "language": "nl"},  # wildcard
]

rules = {
    "max_tracks_per_artist": 1,
    "no_repeat_ever": False,
    "candidate_policies": {
        "history_window_months": 3,
        "language": {
            "allow_dutch": True
        },
        "year_distribution": {
            "pre_2000": 2,
            "post_2000": 2,
            "wildcard": 1
        }
    }
}

errors = PolicyValidator.validate_all(candidates, [], [], rules)

if not errors:
    print("✅ VALID: 'In je moerstaal' block accepted!")
else:
    print("❌ INVALID:")
    for err in errors:
        print(f"  - {err.message}")
```

**Verwacht resultaat**: ✅ VALID

### Scenario 3: "Met hart en Soul" Metadata Enrichment

Test metadata enrichment voor soul tracks.

```python
from src.services.metadata_service import MetadataService

# Mock Spotify data voor soul track
spotify_data = {
    "album": {
        "release_date": "2016-07-20",
        "genres": []
    },
    "artists": [
        {
            "name": "Michael Bublé",
            "genres": ["jazz", "traditional pop", "easy listening"]
        }
    ],
    "available_markets": ["US", "GB", "NL"]
}

enriched = MetadataService.enrich_track(
    track_id="abc123",
    artist="Michael Bublé",
    title="Feeling Good",
    spotify_data=spotify_data
)

print(f"Artist: {enriched['artist']}")
print(f"Title: {enriched['title']}")
print(f"Year: {enriched['year']} (Decade: {enriched['decade']}s)")
print(f"Language: {enriched['language']}")
print(f"Genres: {list(enriched['genre_tags'].keys())}")

# Expected:
# Year: 2016 (Decade: 2010s)
# Language: en
# Genres: ['jazz']
```

### Scenario 4: Artist Limit Violation

Test dat duplicate artists worden afgewezen.

```python
from src.validators.policy_validator import PolicyValidator

# Huidige playlist heeft al 1 Queen track
current_tracks = [
    {"artist": "Queen", "title": "Bohemian Rhapsody"}
]

# Probeer nóg een Queen track toe te voegen
candidates = [
    {"spotify_track_id": "1", "artist": "Queen", "title": "Another One Bites The Dust"}
]

errors = PolicyValidator.validate_artist_limit(
    candidates,
    current_tracks,
    max_per_artist=1
)

if errors:
    print(f"✅ CORRECTLY REJECTED: {errors[0].message}")
else:
    print("❌ ERROR: Should have been rejected!")

# Expected: ✅ CORRECTLY REJECTED: Artist 'Queen' would exceed limit
```

### Scenario 5: History Deduplication (No-Repeat-Ever)

Test dat tracks die al gespeeld zijn worden afgewezen.

```python
from src.validators.policy_validator import PolicyValidator
from datetime import datetime

# Track history
history = [
    {
        "spotify_track_id": "old_track_123",
        "first_added_at": datetime(2023, 1, 1),
        "last_removed_at": datetime(2023, 2, 1)
    }
]

# Probeer dezelfde track opnieuw toe te voegen
candidates = [
    {"spotify_track_id": "old_track_123", "artist": "Queen"}
]

errors = PolicyValidator.validate_history(
    candidates,
    history,
    no_repeat_ever=True,
    history_window_months=None
)

if errors:
    print(f"✅ CORRECTLY REJECTED: {errors[0].message}")
else:
    print("❌ ERROR: Should have been rejected!")

# Expected: ✅ CORRECTLY REJECTED: Track has been played before (no-repeat-ever policy)
```

### Scenario 6: Time-Based History (3 Maanden)

Test dat tracks na 3 maanden weer toegevoegd mogen worden.

```python
from src.validators.policy_validator import PolicyValidator
from datetime import datetime, timedelta

now = datetime.utcnow()

# Track was 4 maanden geleden verwijderd (oud genoeg)
history_old = [
    {
        "spotify_track_id": "old_track",
        "first_added_at": now - timedelta(days=150),
        "last_removed_at": now - timedelta(days=120)  # 4 maanden
    }
]

# Track was 2 maanden geleden verwijderd (te recent)
history_recent = [
    {
        "spotify_track_id": "recent_track",
        "first_added_at": now - timedelta(days=70),
        "last_removed_at": now - timedelta(days=60)  # 2 maanden
    }
]

# Test oude track (should be allowed)
candidates_old = [{"spotify_track_id": "old_track"}]
errors = PolicyValidator.validate_history(
    candidates_old,
    history_old,
    no_repeat_ever=False,
    history_window_months=3
)

if not errors:
    print("✅ CORRECT: Old track (4 months) is allowed")
else:
    print(f"❌ ERROR: Old track should be allowed but got: {errors}")

# Test recente track (should be rejected)
candidates_recent = [{"spotify_track_id": "recent_track"}]
errors = PolicyValidator.validate_history(
    candidates_recent,
    history_recent,
    no_repeat_ever=False,
    history_window_months=3
)

if errors:
    print(f"✅ CORRECT: Recent track (2 months) is rejected: {errors[0].message}")
else:
    print("❌ ERROR: Recent track should be rejected!")
```

## Database Verification

### Check Migration Status

```bash
docker compose exec app alembic current
```

**Verwacht**: `ac11471a3939 (head)`

### Verify Tables

```bash
docker compose exec db psql -U playlist -d playlistdb -c "\dt"
```

**Verwacht**:
- playlists
- playlist_rules
- playlist_blocks
- block_tracks
- playlist_track_history
- **runs** ← Nieuw
- **run_changes** ← Nieuw
- alembic_version

### Verify Columns

```bash
# Check playlists nieuwe kolommen
docker compose exec db psql -U playlist -d playlistdb -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'playlists' AND column_name IN ('refresh_schedule', 'is_auto_commit');"
```

**Verwacht**:
- refresh_schedule | character varying
- is_auto_commit | boolean

```bash
# Check block_tracks nieuwe kolommen
docker compose exec db psql -U playlist -d playlistdb -c "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'block_tracks' AND column_name IN ('year', 'language', 'genre_tags', 'added_at');"
```

**Verwacht**:
- year | integer
- language | character varying
- genre_tags | jsonb
- added_at | timestamp without time zone

### Run Full SQL Verification

```bash
docker compose exec -T db psql -U playlist -d playlistdb < app/verify_migration.sql
```

## Integration Tests (Later)

Deze tests worden relevant in Sprint 2 wanneer we de refresh service implementeren:

- [ ] Create a Run with preview status
- [ ] Add RunChanges (both ADD and REMOVE)
- [ ] Approve/reject individual changes
- [ ] Commit a Run and verify playlist updates
- [ ] Test auto-commit workflow
- [ ] Test scheduled runs (cron)

## Performance Tests (Later)

Voor productie gebruik:

- [ ] Test metadata enrichment met 1000+ tracks
- [ ] Test validation met grote playlists (50 blocks)
- [ ] Test concurrent run creation
- [ ] Database query performance met indices

## Acceptance Criteria Sprint 1

Sprint 1 is succesvol als:

- [x] ✅ Run en RunChange modellen bestaan in database
- [x] ✅ Metadata fields (year, language, genre_tags) bestaan
- [x] ✅ PolicyValidator kan alle policies valideren
- [x] ✅ MetadataService kan tracks verrijken met metadata
- [x] ✅ Alle unit tests slagen
- [x] ✅ Database migratie werkt zonder errors
- [x] ✅ API blijft werken na deployment

## Troubleshooting

### Tests falen met "ModuleNotFoundError"

```bash
# Herinstalleer dependencies
docker compose exec app pip install -r requirements.txt
```

### Database connection errors

```bash
# Check of database draait
docker compose ps

# Bekijk database logs
docker compose logs db

# Restart database
docker compose restart db
```

### Migratie errors

Zie `DEPLOYMENT_GUIDE.md` sectie "Troubleshooting"

---

**Happy Testing! 🧪**
