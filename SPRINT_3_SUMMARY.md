# Sprint 3: Scheduler & Automation - Samenvatting

**Datum**: 24 januari 2026
**Status**: ✅ Voltooid

## Overzicht

Sprint 3 implementeert automatische playlist refreshes met APScheduler. Playlists kunnen nu op basis van cron expressions automatisch ververst worden, met optionele auto-commit functionaliteit.

## Wat is geïmplementeerd

### 1. APScheduler Integration

**Dependencies toegevoegd:**
- `APScheduler==3.10.4` - Production-ready job scheduling

### 2. Scheduler Service (`scheduler_service.py`)

**Nieuwe service met volledige scheduling capabilities**

#### Core Features:

**`PlaylistScheduler` Class:**
- **Cron-based scheduling**: Elke playlist kan eigen schedule hebben
- **Auto-commit support**: Optioneel automatisch goedkeuren en uitvoeren
- **Database reload**: Leest playlists uit database bij startup
- **Job management**: Add, remove, update scheduled jobs
- **Manual triggers**: Voor testing zonder te wachten op cron

#### Key Methods:

```python
class PlaylistScheduler:
    def add_playlist_job(playlist_key, cron_expression, is_auto_commit)
    def remove_playlist_job(playlist_key)
    def reload_from_database()
    def trigger_manual_refresh(playlist_key, is_auto_commit)
    def get_scheduled_jobs()
```

#### Workflow:

1. **Startup**: Scheduler start en leest alle active playlists
2. **Scheduling**: Voor elke playlist met `refresh_schedule`:
   - Parse cron expression
   - Schedule job met APScheduler
   - Log configuratie
3. **Execution**: Wanneer scheduled tijd bereikt:
   - Create refresh preview
   - Als `is_auto_commit=True`:
     - Approve alle ADD changes automatisch
     - Commit run meteen
     - Update Spotify
   - Als `is_auto_commit=False`:
     - Laat run in PREVIEW status
     - Vereist handmatige approval
4. **Logging**: Alle actions worden gelogd

---

### 3. API Endpoints (Sprint 3)

**4 nieuwe endpoints voor scheduler management**

#### Manual Trigger

**`POST /scheduler/refresh/{playlist_key}?auto_commit=false`**
- Trigger handmatig een refresh (voor testing)
- Query param `auto_commit`: boolean (default false)

```bash
# Test refresh without auto-commit
curl -X POST http://localhost:8000/scheduler/refresh/door-de-tijd-heen

# Test with auto-commit
curl -X POST http://localhost:8000/scheduler/refresh/door-de-tijd-heen?auto_commit=true
```

Response:
```json
{
  "success": true,
  "message": "Manual refresh preview created",
  "run_id": 123,
  "status": "preview",
  "remove_count": 5,
  "add_count": 5
}
```

#### Scheduler Status

**`GET /scheduler/jobs`**
- Bekijk alle scheduled jobs met next run times

```bash
curl http://localhost:8000/scheduler/jobs
```

Response:
```json
{
  "total": 3,
  "jobs": [
    {
      "id": "playlist_door-de-tijd-heen",
      "name": "Refresh door-de-tijd-heen",
      "next_run": "2026-01-27T02:00:00",
      "trigger": "cron[day_of_week='mon', hour='2', minute='0']"
    },
    ...
  ]
}
```

#### Reload Scheduler

**`POST /scheduler/reload`**
- Herlaad scheduler van database
- Gebruik na het updaten van playlist schedules

```bash
curl -X POST http://localhost:8000/scheduler/reload
```

#### Update Schedule

**`PATCH /playlists/{playlist_key}/schedule`**
- Update de refresh schedule van een playlist
- Body: `refresh_schedule` (cron), `is_auto_commit` (bool)

```bash
curl -X PATCH http://localhost:8000/playlists/door-de-tijd-heen/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_schedule": "0 2 * * 1",
    "is_auto_commit": false
  }'
```

---

### 4. Logging Configuration

**Structured logging voor alle services**

#### Features:
- **Console output**: Colored, formatted logs
- **File output**: Optioneel loggen naar file
- **Log levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Noisy logger suppression**: APScheduler en urllib3 op WARNING

#### Configuration:

Via environment variables:
```bash
# .env
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=/logs/app.log  # Optional: log to file
```

#### Log Format:

```
2026-01-24 14:30:00 - src.services.scheduler_service - INFO - Scheduled refresh for 'door-de-tijd-heen': 0 2 * * 1 (auto_commit=False)
2026-01-24 14:30:00 - src.services.scheduler_service - INFO - Scheduler reload complete. 3 jobs scheduled.
```

---

### 5. Startup & Shutdown Hooks

**Application lifecycle management in `main.py`**

#### Startup:
1. Setup logging (van LOG_LEVEL env var)
2. Start scheduler
3. Load all active playlists from database
4. Schedule jobs

```python
@app.on_event("startup")
async def startup_event():
    setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
    start_scheduler()
    # ✅ Scheduler running
```

#### Shutdown:
1. Stop scheduler gracefully
2. Cancel pending jobs
3. Cleanup resources

```python
@app.on_event("shutdown")
async def shutdown_event():
    shutdown_scheduler()
    # ✅ Scheduler stopped
```

---

## Cron Expression Referentie

### Format:
```
minute hour day_of_month month day_of_week
```

### Voorbeelden:

| Cron Expression | Beschrijving |
|----------------|-------------|
| `0 2 * * 1` | Elke maandag om 02:00 |
| `0 2 * * *` | Elke dag om 02:00 |
| `0 */6 * * *` | Elke 6 uur |
| `0 2 1 * *` | Eerste dag van elke maand om 02:00 |
| `0 2 * * 0` | Elke zondag om 02:00 |
| `30 3 * * 1,5` | Maandag en vrijdag om 03:30 |

### Cron Tester:
https://crontab.guru/ - Online cron expression validator

---

## Playlist Schedule Configuratie

### Voorbeeld 1: "Door de tijd heen" (Wekelijks, Manual Approval)

```bash
curl -X PATCH http://localhost:8000/playlists/door-de-tijd-heen/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_schedule": "0 2 * * 1",
    "is_auto_commit": false
  }'
```

**Behavior:**
- Elke maandag om 02:00
- AI genereert 5 nieuwe tracks
- Run blijft in PREVIEW status
- Jij krijgt notificatie (via web UI in Sprint 4)
- Je reviewed en approved handmatig
- Je commit wanneer je klaar bent

### Voorbeeld 2: "Met hart en Soul" (Wekelijks, Auto-Commit)

```bash
curl -X PATCH http://localhost:8000/playlists/met-hart-en-soul/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_schedule": "0 3 * * 2",
    "is_auto_commit": true
  }'
```

**Behavior:**
- Elke dinsdag om 03:00
- AI genereert 5 nieuwe tracks
- Alle ADD changes worden **automatisch approved**
- Run wordt **automatisch gecommit**
- Spotify playlist wordt direct updated
- Je checkt resultaat later

### Voorbeeld 3: "In je moerstaal" (Maandelijks, Manual)

```bash
curl -X PATCH http://localhost:8000/playlists/in-je-moerstaal/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_schedule": "0 2 1 * *",
    "is_auto_commit": false
  }'
```

**Behavior:**
- Eerste dag van elke maand om 02:00
- Manual approval required

### Schedule Disablen:

```bash
curl -X PATCH http://localhost:8000/playlists/door-de-tijd-heen/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_schedule": null
  }'
```

---

## Complete Workflow Voorbeeld

### Setup: "Door de tijd heen" met wekelijkse refresh

**1. Create playlist (als nog niet gedaan):**

```bash
curl -X POST http://localhost:8000/playlists \
  -H "Content-Type: application/json" \
  -d '{
    "key": "door-de-tijd-heen",
    "name": "Door de tijd heen",
    "spotify_playlist_id": "your-spotify-id",
    "vibe": "Diverse hits door de decennia heen. Van 80s tot 2020s.",
    "refresh_schedule": "0 2 * * 1",
    "is_auto_commit": false
  }'
```

**2. Create rules:**

```bash
curl -X PATCH http://localhost:8000/playlists/door-de-tijd-heen/rules \
  -H "Content-Type: application/json" \
  -d '{
    "block_size": 5,
    "block_count": 10,
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
  }'
```

**3. Reload scheduler (optioneel, gebeurt automatisch bij startup):**

```bash
curl -X POST http://localhost:8000/scheduler/reload
```

**4. Verify schedule:**

```bash
curl http://localhost:8000/scheduler/jobs
```

Response:
```json
{
  "total": 1,
  "jobs": [
    {
      "id": "playlist_door-de-tijd-heen",
      "name": "Refresh door-de-tijd-heen",
      "next_run": "2026-01-27T02:00:00",
      "trigger": "cron[day_of_week='mon', hour='2', minute='0']"
    }
  ]
}
```

**5. Test met manual trigger (zonder te wachten tot maandag):**

```bash
curl -X POST http://localhost:8000/scheduler/refresh/door-de-tijd-heen
```

**6. Check de preview:**

```bash
curl http://localhost:8000/runs/1/changes
```

**7. Approve changes (via API of web UI):**

```bash
# Approve change 2
curl -X PATCH http://localhost:8000/runs/1/changes/2/approve \
  -d '{"is_approved": true}'

# Herhaal voor alle 5 ADD changes
```

**8. Commit:**

```bash
curl -X POST http://localhost:8000/runs/1/commit
```

**9. Next week (maandag 02:00):**
- Scheduler triggert automatisch nieuwe refresh
- Je krijgt notificatie
- Herhaal stap 6-8

---

## Logging Voorbeelden

### Startup Logs:

```
2026-01-24 14:00:00 - root - INFO - Logging configured: level=INFO, file=None
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Playlist scheduler started
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Reloading schedules for 3 active playlists
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Scheduled refresh for 'door-de-tijd-heen': 0 2 * * 1 (auto_commit=False)
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Scheduled refresh for 'met-hart-en-soul': 0 3 * * 2 (auto_commit=True)
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Scheduled refresh for 'in-je-moerstaal': 0 2 1 * * (auto_commit=False)
2026-01-24 14:00:00 - src.services.scheduler_service - INFO - Scheduler reload complete. 3 jobs scheduled.
```

### Scheduled Refresh Logs (Auto-commit):

```
2026-01-28 03:00:00 - src.services.scheduler_service - INFO - === Executing scheduled refresh for 'met-hart-en-soul' (auto_commit=True) ===
2026-01-28 03:00:00 - src.services.scheduler_service - INFO - Creating refresh preview for 'met-hart-en-soul'...
2026-01-28 03:00:01 - src.ai_candidates - INFO - Requesting 15 AI suggestions for playlist 'met-hart-en-soul'...
2026-01-28 03:00:03 - src.ai_candidates - INFO - OpenAI returned 15 suggestions
2026-01-28 03:00:05 - src.ai_candidates - INFO - Validated 12 tracks with Spotify
2026-01-28 03:00:05 - src.services.refresh_service - INFO - Found valid set of 5 candidates
2026-01-28 03:00:05 - src.services.refresh_service - INFO - Created run 456 with 5 removes and 5 adds
2026-01-28 03:00:05 - src.services.scheduler_service - INFO - Preview created: run_id=456, removes=5, adds=5
2026-01-28 03:00:05 - src.services.scheduler_service - INFO - Auto-commit enabled. Approving all 5 ADD changes...
2026-01-28 03:00:05 - src.services.scheduler_service - INFO - Committing run 456...
2026-01-28 03:00:06 - src.services.refresh_service - INFO - Updated Spotify playlist: removed 5, added 5
2026-01-28 03:00:06 - src.services.scheduler_service - INFO - ✅ Auto-commit successful for 'met-hart-en-soul'
2026-01-28 03:00:06 - src.services.scheduler_service - INFO -    Removed block 2: 5 tracks
2026-01-28 03:00:06 - src.services.scheduler_service - INFO -    Added block 12: 5 tracks
```

### Scheduled Refresh Logs (Manual approval):

```
2026-01-27 02:00:00 - src.services.scheduler_service - INFO - === Executing scheduled refresh for 'door-de-tijd-heen' (auto_commit=False) ===
2026-01-27 02:00:00 - src.services.scheduler_service - INFO - Creating refresh preview for 'door-de-tijd-heen'...
2026-01-27 02:00:02 - src.services.scheduler_service - INFO - Preview created: run_id=457, removes=5, adds=5
2026-01-27 02:00:02 - src.services.scheduler_service - INFO - ⏸️ Manual approval required for 'door-de-tijd-heen'. Run 457 is in PREVIEW status.
2026-01-27 02:00:02 - src.services.scheduler_service - INFO -    Review and approve via: GET /runs/457/changes
```

---

## Environment Variables

```bash
# .env
# Logging
LOG_LEVEL=INFO                      # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FILE=/app/logs/wissellijst.log  # Optional: log to file

# Database
DATABASE_URL=postgresql://...

# Spotify
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...

# OpenAI
OPENAI_API_KEY=...
```

---

## Bestanden Gewijzigd/Toegevoegd

```
app/
├── requirements.txt                    [UPDATED] +APScheduler
├── src/
│   ├── logging_config.py               [NEW] Logging setup
│   ├── services/
│   │   └── scheduler_service.py        [NEW] Scheduler implementation
│   └── main.py                          [UPDATED] +startup/shutdown hooks, +4 endpoints
└── SPRINT_3_SUMMARY.md                  [NEW] This file
```

---

## API Endpoints Overzicht

| Method | Endpoint | Beschrijving |
|--------|----------|-------------|
| POST | `/scheduler/refresh/{key}` | Manual trigger refresh |
| GET | `/scheduler/jobs` | List scheduled jobs |
| POST | `/scheduler/reload` | Reload scheduler from DB |
| PATCH | `/playlists/{key}/schedule` | Update playlist schedule |

---

## Testing

### 1. Verify Scheduler Started

```bash
# Check logs on startup
docker compose logs app | grep scheduler

# Expected:
# ✅ Playlist scheduler started
# Scheduler reload complete. X jobs scheduled.
```

### 2. List Scheduled Jobs

```bash
curl http://localhost:8000/scheduler/jobs
```

### 3. Manual Trigger (Preview)

```bash
curl -X POST http://localhost:8000/scheduler/refresh/door-de-tijd-heen

# Check the created run
curl http://localhost:8000/runs/1/changes
```

### 4. Manual Trigger (Auto-commit)

```bash
curl -X POST http://localhost:8000/scheduler/refresh/met-hart-en-soul?auto_commit=true

# Should commit immediately
# Check Spotify playlist - should have new tracks!
```

### 5. Update Schedule

```bash
# Set to run every day at 3am
curl -X PATCH http://localhost:8000/playlists/door-de-tijd-heen/schedule \
  -H "Content-Type: application/json" \
  -d '{"refresh_schedule": "0 3 * * *"}'

# Verify update
curl http://localhost:8000/scheduler/jobs
```

---

## Troubleshooting

### Scheduler doesn't start

**Check logs:**
```bash
docker compose logs app | grep -i error
```

**Common issues:**
- APScheduler not installed: `pip install APScheduler==3.10.4`
- Database connection error

**Solution:**
```bash
docker compose restart app
```

### Invalid cron expression

**Error:**
```
ValueError: Invalid cron expression: 0 2 * *
```

**Solution:**
Use valid 5-field cron: `minute hour day month day_of_week`

Example: `0 2 * * 1` (not `0 2 * *`)

### Job not triggering

**Check:**
1. Is playlist active? `SELECT * FROM playlists WHERE key='...'`
2. Has refresh_schedule? Should not be NULL
3. Is scheduler running? `curl http://localhost:8000/scheduler/jobs`

**Solution:**
```bash
# Reload scheduler
curl -X POST http://localhost:8000/scheduler/reload
```

### Auto-commit not working

**Check:**
1. Is `is_auto_commit=true` in database?
2. Are all policies valid? (might fail validation)

**Debug:**
```bash
# Check logs during scheduled run
docker compose logs -f app
```

---

## Deployment Checklist

- [ ] ✅ APScheduler added to requirements.txt
- [ ] ✅ Environment variables configured (LOG_LEVEL, LOG_FILE)
- [ ] ✅ Database migrated (Sprint 1 migration includes scheduler fields)
- [ ] ✅ Playlists configured with refresh_schedule
- [ ] ✅ Test manual trigger works
- [ ] ✅ Verify scheduler starts on app startup
- [ ] ✅ Monitor logs during first scheduled run

---

## Volgende Stappen (Sprint 4)

1. **Frontend UI** - React dashboard voor:
   - Viewing scheduled jobs
   - Configuring playlist schedules
   - Reviewing preview runs
   - Approving/rejecting AI suggestions

2. **Notifications** - Email/webhook notificaties voor:
   - Scheduled refreshes completed
   - Manual approval required
   - Failed refreshes

3. **Analytics** - Dashboard met:
   - Refresh history
   - AI suggestion acceptance rate
   - Track rotation analytics

---

## Conclusie

Sprint 3 is succesvol afgerond! Het volledige automatische refresh systeem is geïmplementeerd en klaar voor productie gebruik.

**Features delivered:**
- ✅ APScheduler integration met cron support
- ✅ Auto-commit workflow (optioneel)
- ✅ Manual trigger voor testing
- ✅ Scheduler management API
- ✅ Structured logging
- ✅ Startup/shutdown lifecycle

**Playlists kunnen nu:**
- Automatisch ververst worden op basis van cron schedule
- Handmatig getriggerd worden voor testing
- Auto-approved en gecommit worden (optioneel)
- Gelogd worden voor debugging en monitoring

**Klaar voor deployment en Sprint 4! 🚀**
