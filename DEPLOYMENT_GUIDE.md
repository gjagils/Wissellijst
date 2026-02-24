# Deployment Guide - Sprint 1

Deze guide helpt je om de Sprint 1 changes te deployen op je Synology NAS.

## Pre-deployment Checklist

- [ ] Git repository is up-to-date op je Synology
- [ ] `.env` file is correct geconfigureerd
- [ ] Docker Compose is geïnstalleerd op Synology
- [ ] Poorten 8000 (API) zijn beschikbaar

## Deployment Stappen

### 1. Pull de laatste changes

SSH naar je Synology en navigeer naar de project directory:

```bash
cd /volume1/docker/wissellijst  # Of waar je het project hebt staan
git pull origin claude/playlist-refresh-system-MmWqC
```

### 2. Controleer de .env file

Zorg dat je `.env` file deze variabelen bevat:

```bash
# Spotify credentials
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://your-synology-ip:8000/spotify/callback

# OpenAI
OPENAI_API_KEY=your_openai_api_key

# Database
DATABASE_URL=postgresql://playlist:playlist@db:5432/playlistdb
```

### 3. Stop de huidige containers (indien draaiend)

```bash
docker compose down
```

### 4. Rebuild de containers met nieuwe dependencies

```bash
docker compose up -d --build
```

Dit zal:
- De Python container rebuilden met de nieuwe `alembic` dependency
- De containers starten

### 5. Voer de database migratie uit

**BELANGRIJK**: Dit is een eenmalige actie die de database schema update.

```bash
# Check of de database container draait
docker compose ps

# Voer migratie uit
docker compose exec app alembic upgrade head
```

Je zou output moeten zien zoals:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> ac11471a3939, Add Run and RunChange models, extend metadata fields
```

### 6. Verifieer de migratie

**Optie A: Via SQL** (aanbevolen)

```bash
# Kopieer verificatie script naar container
docker compose exec -T db psql -U playlist -d playlistdb < app/verify_migration.sql
```

**Optie B: Handmatig via PostgreSQL**

```bash
# Open PostgreSQL shell
docker compose exec db psql -U playlist -d playlistdb

# Controleer of nieuwe tabellen bestaan
\dt

# Je zou moeten zien:
# - playlists
# - playlist_rules
# - playlist_blocks
# - block_tracks
# - playlist_track_history
# - runs              <-- NIEUW
# - run_changes       <-- NIEUW
# - alembic_version   <-- NIEUW

# Controleer nieuwe kolommen in playlists
\d playlists

# Je zou moeten zien:
# - refresh_schedule  <-- NIEUW
# - is_auto_commit    <-- NIEUW

# Controleer nieuwe kolommen in block_tracks
\d block_tracks

# Je zou moeten zien:
# - year              <-- NIEUW
# - language          <-- NIEUW
# - genre_tags        <-- NIEUW (JSONB)
# - added_at          <-- NIEUW

# Exit PostgreSQL
\q
```

### 7. Test de services

**Test de PolicyValidator:**

```bash
docker compose exec app python -m tests.test_validators
```

Verwachte output: Alle tests zouden moeten slagen (✅ PASS).

**Test de MetadataService:**

```bash
docker compose exec app python -m tests.test_metadata_service
```

Verwachte output: "🎉 ALL TESTS PASSED!"

### 8. Controleer de API

```bash
# Check health endpoint
curl http://localhost:8000/health

# Expected response: {"status":"healthy"}

# Check if API is running
docker compose logs app | tail -20
```

### 9. Controleer de logs

```bash
# Bekijk API logs
docker compose logs -f app

# Bekijk database logs
docker compose logs -f db
```

## Rollback Procedure

Als er problemen zijn, kun je terugdraaien naar de vorige versie:

### Rollback Migratie

```bash
# Rollback database naar vorige versie
docker compose exec app alembic downgrade -1

# Of helemaal terug naar basis
docker compose exec app alembic downgrade base
```

### Rollback Code

```bash
# Ga terug naar vorige commit
git checkout <previous-commit-hash>

# Rebuild containers
docker compose up -d --build
```

## Troubleshooting

### Probleem: "ModuleNotFoundError: No module named 'alembic'"

**Oplossing:**

```bash
# Rebuild de app container
docker compose up -d --build app
```

### Probleem: "Target database is not up to date"

**Oplossing:**

```bash
# Voer migraties uit
docker compose exec app alembic upgrade head
```

### Probleem: "connection to server at localhost, port 5432 failed"

**Oplossing:**

```bash
# Check of database container draait
docker compose ps

# Als db niet draait, start deze
docker compose up -d db

# Wacht 10 seconden en probeer opnieuw
sleep 10
docker compose exec app alembic upgrade head
```

### Probleem: Migratie faalt met "column already exists"

**Oplossing:** De migratie is al deels toegepast. Je kunt:

**Optie 1: Markeer migratie als toegepast**

```bash
docker compose exec app alembic stamp head
```

**Optie 2: Fresh start** (⚠️ **VERLIEST ALLE DATA!**)

```bash
# Stop containers
docker compose down

# Verwijder volumes (inclusief database data!)
docker compose down -v

# Start opnieuw
docker compose up -d
docker compose exec app alembic upgrade head
```

### Probleem: Tests falen

**Oplossing:**

```bash
# Check of alle dependencies geïnstalleerd zijn
docker compose exec app pip list | grep -E "alembic|SQLAlchemy|psycopg2"

# Herinstalleer dependencies
docker compose exec app pip install -r requirements.txt

# Probeer tests opnieuw
docker compose exec app python -m tests.test_validators
```

## Verificatie Checklist

Na deployment, controleer:

- [ ] ✅ Database migratie succesvol (`alembic current` toont ac11471a3939)
- [ ] ✅ Nieuwe tabellen `runs` en `run_changes` bestaan
- [ ] ✅ Nieuwe kolommen in `playlists` en `block_tracks` bestaan
- [ ] ✅ PolicyValidator tests slagen
- [ ] ✅ MetadataService tests slagen
- [ ] ✅ API health endpoint reageert
- [ ] ✅ Geen errors in `docker compose logs app`

## Volgende Stappen

Na succesvolle deployment van Sprint 1:

1. **Test met voorbeeld data** - Maak een test playlist aan en kijk of metadata correct wordt opgeslagen
2. **Sprint 2 voorbereiden** - OpenAI integratie en refresh service
3. **Monitoring instellen** - Bekijk regelmatig logs voor errors

## Handige Commands Reference

```bash
# Container status
docker compose ps

# Live logs volgen
docker compose logs -f app

# Container herstarten
docker compose restart app

# Database backup maken
docker compose exec db pg_dump -U playlist playlistdb > backup_$(date +%Y%m%d).sql

# Database restore
docker compose exec -T db psql -U playlist -d playlistdb < backup_20260124.sql

# Python shell in container
docker compose exec app python

# Bash shell in container
docker compose exec app bash

# Migratie status
docker compose exec app alembic current

# Migratie geschiedenis
docker compose exec app alembic history

# Nieuwe migratie maken (later)
docker compose exec app alembic revision --autogenerate -m "Description"
```

## Support

Als je problemen ondervindt:

1. Check de logs: `docker compose logs app`
2. Verifieer database status: `docker compose exec db psql -U playlist -d playlistdb -c "\dt"`
3. Run tests: `docker compose exec app python -m tests.test_validators`
4. Check de SPRINT_1_SUMMARY.md voor voorbeeld configuraties

---

**Deployment Date**: ___________
**Deployed By**: ___________
**Migration Version**: ac11471a3939
**Status**: ⬜ Success / ⬜ Failed / ⬜ Partial
