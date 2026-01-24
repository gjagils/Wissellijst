# Sprint 2: AI & Refresh Logic - Samenvatting

**Datum**: 24 januari 2026
**Status**: ✅ Voltooid

## Overzicht

Sprint 2 implementeert het volledige AI-gestuurde playlist refresh systeem met preview/commit workflow. Gebruikers kunnen nu AI-gegenereerde track suggesties bekijken, handmatig aanpassen, en toepassen op hun Spotify playlists.

## Wat is geïmplementeerd

### 1. OpenAI Integration (`ai_candidates.py`)

**Volledige AI-gestuurde track suggestie systeem**

#### Features:
- **Intelligente prompts**: Bouwt context-rijke prompts op basis van:
  - Playlist vibe
  - Alle candidate policies (decade, language, year distribution)
  - Huidige artiesten in playlist (om duplicates te voorkomen)
  - Track history

- **Policy-aware suggesties**: AI krijgt instructies mee zoals:
  - "Decade distribution: 1 from 1980s, 1 from 1990s..."
  - "Maximum 1 Dutch language track(s) per block"
  - "NO Dutch language tracks allowed"
  - "Year distribution: 2 from pre 2000, 2 from post 2000, 1 from wildcard"

- **Spotify validatie**: Alle AI suggesties worden gevalideerd:
  - Zoekt track op Spotify via `artist:{name} track:{title}`
  - Haalt volledige track metadata op
  - Verrijkt met MetadataService (year, decade, language, genre_tags)
  - Voegt AI reasoning toe ("why this track fits")

- **Error handling**: Graceful fallback naar Spotify-based candidates

#### Voorbeeld AI Prompt:

```
You are a music curator helping to select tracks for a playlist.

PLAYLIST VIBE:
Diverse hits spanning different decades from 80s to 2020s

RULES:
Max 1 track(s) per artist in the active playlist.
A track may never be repeated (no-repeat-ever).
Decade distribution: 1 from 1980s, 1 from 1990s, 1 from 2000s, 1 from 2010s, 1 from 2020s
Maximum 1 Dutch language track(s) per block

CURRENT ARTISTS IN PLAYLIST (avoid these):
Queen, Nirvana, Coldplay, [...]

TASK:
Suggest exactly 15 tracks that match the vibe and follow the rules.

OUTPUT FORMAT (valid JSON array):
[
  {
    "artist": "Artist Name",
    "title": "Track Title",
    "reason": "Brief explanation why this fits"
  },
  ...
]
```

#### Cost Optimization:
- Gebruikt `gpt-4o-mini` model (zeer kosteneffectief)
- Temperature 0.8 voor creativiteit met consistentie
- Max 2000 tokens voor antwoord

---

### 2. Refresh Service (`refresh_service.py`)

**Complete playlist rotation workflow met preview/commit pattern**

#### Core Functions:

**`create_refresh_preview()`**
- Identificeert oudste blok om te verwijderen
- Genereert AI kandidaten (3x block_size voor keuze)
- Valt terug op Spotify candidates indien AI faalt
- Verwijdert duplicates en huidige tracks
- Valideert kandidaten tegen alle policies met `PolicyValidator`
- Probeert verschillende combinaties om perfect valid set te vinden
- Maakt `Run` met status=PREVIEW
- Maakt `RunChange` records voor:
  - REMOVE changes (auto-approved)
  - ADD changes (requires manual approval)

**`commit_refresh()`**
- Valideert dat run in PREVIEW status is
- Checkt dat alle ADD changes approved zijn
- Markeert oude blok als inactive
- Maakt nieuw blok met approved tracks
- Update track history:
  - Removed tracks → `last_removed_at` gezet
  - Added tracks → toegevoegd aan history
- **Update Spotify playlist**:
  - `playlist_remove_all_occurrences_of_items()` voor oude tracks
  - `playlist_add_items()` voor nieuwe tracks
- Zet run status naar COMMITTED
- Return detailed summary

**`approve_change()`**
- Approve of reject een individuele RunChange
- Alleen toegestaan voor runs in PREVIEW status

**`cancel_run()`**
- Cancel een preview run
- Zet status naar CANCELLED

#### Error Handling:
- Graceful fallback als AI geen kandidaten genereert
- Validation warnings gelogd voor debugging
- Rollback bij Spotify update failures

---

### 3. API Endpoints (Sprint 2)

**7 nieuwe REST endpoints voor run management**

#### Playlist Refresh

**`POST /playlists/{playlist_key}/runs/preview`**
- Start nieuwe refresh preview
- Genereert AI kandidaten en validaties
- Returns: run_id, counts, status

```json
{
  "run_id": 123,
  "playlist_key": "door-de-tijd-heen",
  "status": "preview",
  "remove_count": 5,
  "add_count": 5,
  "message": "Created preview run 123 with 5 removes and 5 adds"
}
```

#### Run Details

**`GET /runs/{run_id}`**
- Haal run details op
- Returns: volledige Run object

**`GET /runs/{run_id}/changes`**
- Haal alle changes op (adds + removes)
- Returns: RunChangesResponse met gescheiden lijsten

```json
{
  "run_id": 123,
  "playlist_key": "door-de-tijd-heen",
  "adds": [
    {
      "id": 1,
      "spotify_track_id": "abc123",
      "artist": "Queen",
      "title": "Bohemian Rhapsody",
      "year": 1975,
      "decade": 1970,
      "language": "en",
      "is_ai_suggested": true,
      "is_approved": false,
      "suggested_reason": "Classic rock anthem that fits the diverse hits vibe"
    },
    ...
  ],
  "removes": [...]
}
```

#### Approval Workflow

**`PATCH /runs/{run_id}/changes/{change_id}/approve`**
- Approve of reject een change
- Body: `{"is_approved": true/false}`

**`POST /runs/{run_id}/commit`**
- Commit alle approved changes
- Updates database EN Spotify playlist
- Returns: detailed summary

```json
{
  "success": true,
  "message": "Run 123 committed successfully",
  "removed_block_index": 0,
  "removed_tracks": [...],
  "added_block_index": 11,
  "added_tracks": [...],
  "executed_at": "2026-01-24T13:45:00"
}
```

#### Run Management

**`DELETE /runs/{run_id}`**
- Cancel een preview run
- Zet status naar CANCELLED

**`GET /playlists/{playlist_key}/runs`**
- Haal run historie op
- Query param: `limit` (default 10)
- Gesorteerd op `created_at DESC`

---

### 4. Database Changes

**Geen nieuwe migraties nodig!**
Alle benodigde modellen (Run, RunChange) zijn al gemaakt in Sprint 1.

**Wel toegevoegd aan main.py**:
- Import van Run en RunChange modellen
- Conditional import van refresh service
- Error handling voor missing dependencies

---

## Workflow: Van Preview naar Commit

### Stap 1: Create Preview

```bash
POST /playlists/door-de-tijd-heen/runs/preview
```

**Wat gebeurt er:**
1. AI genereert 15 kandidaten (3x block_size)
2. Spotify valideert elke kandidaat
3. Metadata wordt toegevoegd (year, decade, language)
4. PolicyValidator checkt alle combinaties
5. Best valid set wordt geselecteerd
6. Run + RunChanges worden opgeslagen

### Stap 2: Review via Web UI (Sprint 4)

Gebruiker ziet:
- 5 tracks die verwijderd worden (auto-approved)
- 5 AI-gesuggereerde tracks om toe te voegen
  - Elk met artist, title, year, decade, language
  - Elk met AI reasoning ("why this fits")

### Stap 3: Manual Override (Optioneel)

```bash
# Reject een AI suggestie
PATCH /runs/123/changes/456/approve
{"is_approved": false}

# Of: search een alternatieve track en swap
# (Wordt geïmplementeerd in frontend)
```

### Stap 4: Commit

```bash
POST /runs/123/commit
```

**Wat gebeurt er:**
1. Validatie: alle ADD changes approved?
2. Database update:
   - Oude blok → inactive
   - Nieuw blok aangemaakt
   - Track history updated
3. Spotify update:
   - Verwijder 5 oude tracks
   - Voeg 5 nieuwe tracks toe
4. Run status → COMMITTED

---

## Voorbeeld: "Door de tijd heen" Refresh

### Initial State

Playlist heeft 10 blocks van 5 tracks (50 totaal).

### Preview Request

```bash
POST /playlists/door-de-tijd-heen/runs/preview
```

### AI Prompt

```
PLAYLIST VIBE:
Diverse hits spanning different decades from 80s to 2020s

RULES:
Decade distribution: 1 from 1980s, 1 from 1990s, 1 from 2000s, 1 from 2010s, 1 from 2020s
Maximum 1 Dutch language track(s) per block
Max 1 track(s) per artist
No repeat ever

CURRENT ARTISTS IN PLAYLIST (avoid these):
[... current 50 artists ...]

Suggest exactly 15 tracks
```

### AI Response (Voorbeeld)

```json
[
  {
    "artist": "Survivor",
    "title": "Eye of the Tiger",
    "reason": "Iconic 1980s rock anthem with energetic vibe"
  },
  {
    "artist": "Alanis Morissette",
    "title": "Ironic",
    "reason": "Classic 1990s alternative rock hit"
  },
  {
    "artist": "Coldplay",
    "title": "Viva La Vida",
    "reason": "2000s anthemic pop-rock"
  },
  {
    "artist": "Adele",
    "title": "Hello",
    "reason": "Powerful 2010s ballad"
  },
  {
    "artist": "Billie Eilish",
    "title": "bad guy",
    "reason": "Contemporary 2020s pop hit"
  },
  ...
]
```

### Validation

PolicyValidator checks:
- ✅ 1 from each decade
- ✅ Max 1 Dutch (of geen if all English)
- ✅ Alle artiesten uniek
- ✅ Geen tracks uit history

### RunChanges Created

**Removes (auto-approved):**
- Block 0, track 0: "Track from 1980s" → Oldest block
- Block 0, track 1: "Track from 1990s"
- ... (5 totaal)

**Adds (need approval):**
- Block 11, track 0: Survivor - Eye of the Tiger (1982, 1980s, en)
- Block 11, track 1: Alanis Morissette - Ironic (1995, 1990s, en)
- ... (5 totaal)

### User Reviews & Approves

Via web UI (Sprint 4), user:
- Sees all 5 suggestions
- Approves 4, rejects 1 (doesn't like "bad guy")
- Searches for alternative: "The Weeknd - Blinding Lights"
- Swaps the rejected track

### Commit

```bash
POST /runs/123/commit
```

Database + Spotify updated:
- Block 0 → inactive
- Block 11 → active met 5 approved tracks
- Spotify playlist: -5 old, +5 new

---

## Bestanden Gewijzigd/Toegevoegd

```
app/
├── src/
│   ├── ai_candidates.py                [REWRITTEN] OpenAI integration
│   ├── services/
│   │   └── refresh_service.py          [NEW] Preview/commit workflow
│   └── main.py                          [UPDATED] +7 run management endpoints
└── SPRINT_2_SUMMARY.md                  [NEW] This file
```

---

## API Endpoints Overzicht

| Method | Endpoint | Beschrijving |
|--------|----------|-------------|
| POST | `/playlists/{key}/runs/preview` | Start refresh preview |
| GET | `/runs/{run_id}` | Haal run details op |
| GET | `/runs/{run_id}/changes` | Haal alle changes op |
| PATCH | `/runs/{run_id}/changes/{change_id}/approve` | Approve/reject change |
| POST | `/runs/{run_id}/commit` | Commit approved run |
| DELETE | `/runs/{run_id}` | Cancel preview run |
| GET | `/playlists/{key}/runs` | Run historie |

---

## Testing

### Manual Testing (via curl)

```bash
# 1. Create preview
curl -X POST http://localhost:8000/playlists/door-de-tijd-heen/runs/preview

# Expected output:
# {
#   "run_id": 1,
#   "playlist_key": "door-de-tijd-heen",
#   "status": "preview",
#   "remove_count": 5,
#   "add_count": 5
# }

# 2. Get changes
curl http://localhost:8000/runs/1/changes

# 3. Approve a change
curl -X PATCH http://localhost:8000/runs/1/changes/2/approve \
  -H "Content-Type: application/json" \
  -d '{"is_approved": true}'

# 4. Approve all changes (repeat for each)

# 5. Commit
curl -X POST http://localhost:8000/runs/1/commit

# 6. Check Spotify playlist - should have new tracks!
```

### Integration Testing

Tests kunnen worden toegevoegd in Sprint 3 voor:
- AI kandidaat generatie
- Validation tegen policies
- Spotify update workflow
- Error scenarios

---

## Configuratie Vereisten

### Environment Variables

```bash
# Required for AI candidates
OPENAI_API_KEY=sk-...

# Required for Spotify updates
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=...

# Database
DATABASE_URL=postgresql://...
```

### Model Selection

Standaard model: `gpt-4o-mini`

Kan aangepast worden in `ai_candidates.py` lijn 289:
```python
model="gpt-4o-mini",  # Cost-effective
# model="gpt-4o",     # More powerful but expensive
```

---

## Kosten Schatting

**Per refresh (1 playlist):**
- OpenAI API call: ~$0.001 - $0.003 (gpt-4o-mini)
- Spotify API calls: Gratis (binnen rate limits)

**Per maand (10 playlists, wekelijks):**
- OpenAI kosten: ~$0.12 - $0.36
- Spotify: Gratis

**Zeer betaalbaar! 💰**

---

## Bekende Limitations

1. **AI kan falen**: Als OpenAI API niet beschikbaar is, gebruikt systeem Spotify candidates
2. **Perfect match niet gegarandeerd**: Als geen perfecte combinatie gevonden wordt, gebruikt "best effort"
3. **Geen parallel processing**: Elke Spotify track wordt sequentieel gevalideerd (kan versneld worden)
4. **Geen retry logic**: Als Spotify update faalt, hele commit rollt back

---

## Volgende Stappen (Sprint 3)

1. **Scheduler** - APScheduler voor automatische wekelijkse refreshes
2. **Auto-commit** - Optionele auto-approval voor playlists
3. **Logging** - Structured logging voor debugging
4. **Monitoring** - Health checks en alerting

---

## Volgende Stappen (Sprint 4)

1. **Frontend** - React UI voor preview/approve workflow
2. **Manual search** - Track zoeken en swappen
3. **History viewer** - Visualisatie van rotations over tijd
4. **Dashboard** - Overzicht van alle playlists

---

## Conclusie

Sprint 2 is succesvol afgerond! Het complete AI-gestuurde refresh systeem met preview/commit workflow is geïmplementeerd en klaar voor gebruik.

**Ready for:**
- ✅ Testing met echte playlists
- ✅ Sprint 3 (Scheduler + Automation)
- ✅ Sprint 4 (Frontend UI)

**Features delivered:**
- ✅ OpenAI integratie met policy-aware prompts
- ✅ Spotify validatie en metadata enrichment
- ✅ Complete refresh service met preview/commit
- ✅ 7 REST API endpoints
- ✅ Error handling en fallbacks

**Klaar voor deployment! 🚀**
