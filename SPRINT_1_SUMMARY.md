# Sprint 1: Foundation - Samenvatting

**Datum**: 24 januari 2026
**Status**: ✅ Voltooid

## Overzicht

Sprint 1 legt de foundation voor het playlist refresh systeem. Alle database modellen, validatie services en metadata enrichment zijn geïmplementeerd.

## Wat is toegevoegd

### 1. Database Modellen

#### Nieuwe Tabellen

**`runs`** - Tracking van wekelijkse refresh operaties
- `id`, `playlist_id`, `status` (preview/committed/cancelled)
- `scheduled_at`, `executed_at`
- `created_at`, `updated_at`

**`run_changes`** - Individuele track wijzigingen per run
- `id`, `run_id`, `change_type` (add/remove)
- Track info: `spotify_track_id`, `artist`, `title`
- Positie: `block_index`, `position_in_block`
- Metadata: `year`, `decade`, `language`, `genre_tags`
- AI tracking: `is_ai_suggested`, `is_approved`, `suggested_reason`

#### Uitgebreide Tabellen

**`playlists`** - Scheduling functionaliteit toegevoegd
- `refresh_schedule` - Cron expression voor automatische refreshes (bijv. "0 2 * * 1" voor maandag 2:00)
- `is_auto_commit` - Boolean voor auto-approve van AI suggesties

**`block_tracks`** - Metadata fields voor policy enforcement
- `year` - Release jaar (voor year_distribution policy)
- `language` - Taalcode: 'nl', 'en', 'other'
- `genre_tags` - JSONB met genre classificaties
- `added_at` - Timestamp (voor time-based deduplication)

### 2. Pydantic Schemas

Nieuwe/bijgewerkte schemas in `/app/src/schemas/`:

- **`runs.py`** - `RunCreate`, `RunOut`, `RunListOut`
- **`run_changes.py`** - `RunChangeOut`, `RunChangeUpdate`, `RunChangesResponse`
- **`playlists.py`** - `PlaylistCreate`, `PlaylistOut`, `PlaylistUpdate` (met vibe + scheduling)
- **`rules.py`** - `PlaylistRulesOut`, `PlaylistRulesUpdate`, `CandidatePolicies`

### 3. Validators

**`/app/src/validators/policy_validator.py`** - Policy validatie systeem

Validatie functies:
- `validate_decade_distribution()` - Controleert decade verdeling (bijv. 1 uit 80s, 1 uit 90s)
- `validate_language_policy()` - Controleert taal constraints (max Nederlands per blok)
- `validate_year_distribution()` - Controleert jaar verdeling (pre/post 2000)
- `validate_artist_limit()` - Voorkomt te veel tracks van zelfde artiest
- `validate_history()` - Controleert tegen track historie (no-repeat-ever of time-based)
- `validate_all()` - Voert alle validaties uit

### 4. Metadata Enrichment Service

**`/app/src/services/metadata_service.py`** - Track metadata verrijking

Functionaliteit:
- **Year/Decade extractie** - Van Spotify release date
- **Taal detectie** - Heuristics voor Nederlands/Engels/Anders:
  - Check Spotify markets
  - Analyse Nederlandse woorden in titel
  - Bekende Nederlandse artiesten
- **Genre classificatie** - Mappt Spotify genres naar simplified tags:
  - soul, indie, pop, rock, electronic, jazz, folk, r&b, hip-hop, dutch
- **Batch enrichment** - Verwerk max 50 tracks per Spotify API call

### 5. Database Migraties

**Alembic Setup** - `/app/alembic/`
- Configuratie voor PostgreSQL via `DATABASE_URL` env variable
- Auto-import van Base metadata voor schema detection

**Migratie** - `ac11471a3939_add_run_and_runchange_models_extend_.py`
- Upgrade: Voegt alle nieuwe tabellen en kolommen toe
- Downgrade: Verwijdert alle Sprint 1 wijzigingen

**Documentatie** - `/app/alembic/README_MIGRATIONS.md`
- Instructies voor migratie uitvoering
- Troubleshooting guide
- Rollback procedures

### 6. Dependencies

Toegevoegd aan `requirements.txt`:
- `alembic==1.13.1` - Database migraties

## Voorbeeld Configuraties

### "Door de tijd heen" Playlist

```json
{
  "name": "Door de tijd heen",
  "vibe": "Diverse hits spanning different decades from 80s to 2020s",
  "refresh_schedule": "0 2 * * 1",
  "is_auto_commit": false,
  "rules": {
    "block_size": 5,
    "max_tracks_per_artist": 1,
    "no_repeat_ever": true,
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
        "allow_dutch": true
      }
    }
  }
}
```

### "Met hart en Soul" Playlist

```json
{
  "name": "Met hart en Soul",
  "vibe": "Soulful tracks - neo soul, indie soul, easy listening. Artists like Jonathan Jeremiah, Olivia Dean, Amy Winehouse, Michael Bublé",
  "refresh_schedule": "0 2 * * 1",
  "is_auto_commit": false,
  "rules": {
    "block_size": 5,
    "max_tracks_per_artist": 1,
    "no_repeat_ever": false,
    "candidate_policies": {
      "history_window_months": 3,
      "language": {
        "allow_dutch": false
      },
      "genre_constraints": {
        "required": ["soul", "indie"]
      }
    }
  }
}
```

### "In je moerstaal" Playlist

```json
{
  "name": "In je moerstaal",
  "vibe": "Nederlandse pop door de jaren heen. Geen feest/carnaval/dialect. Denk aan Acda en de Munnik, Stef Bos, Bente, De Dijk, Volumia",
  "refresh_schedule": "0 2 * * 1",
  "is_auto_commit": false,
  "rules": {
    "block_size": 5,
    "max_tracks_per_artist": 1,
    "no_repeat_ever": false,
    "candidate_policies": {
      "history_window_months": 3,
      "language": {
        "allow_dutch": true
      },
      "year_distribution": {
        "pre_2000": 2,
        "post_2000": 2,
        "wildcard": 1
      }
    }
  }
}
```

## Bestanden Gewijzigd

```
app/
├── requirements.txt                          [UPDATED] +alembic
├── src/
│   ├── db/
│   │   └── models.py                         [UPDATED] +Run, +RunChange, +metadata fields
│   ├── schemas/
│   │   ├── runs.py                           [UPDATED]
│   │   ├── run_changes.py                    [UPDATED]
│   │   ├── playlists.py                      [UPDATED]
│   │   └── rules.py                          [UPDATED]
│   ├── services/
│   │   └── metadata_service.py               [NEW]
│   └── validators/
│       ├── __init__.py                       [NEW]
│       └── policy_validator.py               [NEW]
├── alembic/
│   ├── env.py                                [UPDATED]
│   ├── versions/
│   │   └── ac11471a3939_*.py                 [NEW]
│   └── README_MIGRATIONS.md                  [NEW]
└── alembic.ini                               [NEW]
```

## Database Migratie Uitvoeren

**BELANGRIJK**: Voor de changes effect hebben, moet de migratie uitgevoerd worden:

```bash
# Start de database (als deze nog niet draait)
docker compose up -d db

# Voer migratie uit
docker compose exec app alembic upgrade head
```

Of als je de app opnieuw start:

```bash
docker compose up -d --build
docker compose exec app alembic upgrade head
```

## Volgende Stappen (Sprint 2)

Nu de foundation klaar is, kunnen we verder met Sprint 2:

1. ✅ **OpenAI integratie** in `ai_candidates.py`
2. ✅ **Refresh service** met preview/commit workflow
3. ✅ **Run management endpoints**:
   - `POST /playlists/{key}/runs/preview`
   - `GET /runs/{run_id}`
   - `PATCH /runs/{run_id}/approve`
   - `POST /runs/{run_id}/commit`
4. ✅ **Testen** met voorbeeld playlists

## Testing

Na het uitvoeren van de migratie kun je testen of alles werkt:

```python
# Test in Python shell
from src.db.models import Run, RunChange
from src.validators import PolicyValidator
from src.services.metadata_service import MetadataService

# Validatie voorbeeld
candidates = [
    {"spotify_track_id": "123", "artist": "Queen", "decade": 1980, "language": "en"},
    # ... meer kandidaten
]

errors = PolicyValidator.validate_decade_distribution(
    candidates,
    {"1980s": 1, "1990s": 1}
)

# Metadata enrichment voorbeeld
enriched = MetadataService.extract_year_and_decade("1987-05-20")
# Returns: (1987, 1980)
```

## Conclusie

Sprint 1 is succesvol afgerond! Alle database modellen, schemas, validators en services zijn geïmplementeerd en klaar voor gebruik in Sprint 2.

De codebase heeft nu:
- ✅ Robuuste data modellen voor run tracking
- ✅ Flexibele policy validatie
- ✅ Metadata enrichment voor AI suggesties
- ✅ Database migratie systeem
- ✅ Documentatie

**Klaar voor Sprint 2: AI & Refresh Logic! 🚀**
