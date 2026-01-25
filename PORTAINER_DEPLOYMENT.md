# Portainer Deployment Guide - Wissellijst

Complete stap-voor-stap handleiding voor een schone installatie van Wissellijst via Portainer op Synology NAS.

---

## Voorbereiding

### 1. API Keys Verkrijgen

**Spotify API:**
1. Ga naar https://developer.spotify.com/dashboard
2. Log in met je Spotify account
3. Klik op "Create app"
4. Vul in:
   - App name: `Wissellijst`
   - App description: `Playlist rotation system`
   - Redirect URI: `http://localhost:8888/callback`
5. Accept terms en klik "Save"
6. Kopieer de **Client ID** en **Client Secret**

**OpenAI API:**
1. Ga naar https://platform.openai.com/api-keys
2. Log in met je OpenAI account
3. Klik op "Create new secret key"
4. Geef een naam: `Wissellijst`
5. Kopieer de **API key** (je kunt hem maar 1x zien!)

---

## Stap 1: Nieuwe Stack Aanmaken in Portainer

1. Open Portainer op je Synology: `http://<nas-ip>:9000`
2. Selecteer je environment (meestal "local")
3. Ga naar **Stacks** in het menu links
4. Klik op **+ Add stack** (rechtsboven)
5. Vul in:
   - **Name**: `wissellijst`
   - **Build method**: Selecteer "Web editor"

---

## Stap 2: Docker Compose Configuratie

Kopieer de volgende configuratie in de Web editor:

```yaml
version: '3.8'

services:
  app:
    image: python:3.12-slim
    container_name: wissellijst-app
    working_dir: /app
    volumes:
      # LET OP: Pas deze paden aan naar je Synology locatie!
      # Bijvoorbeeld: /volume1/docker/wissellijst/app:/app
      - ./app:/app
      - ./secrets:/app/.secrets
    environment:
      # Database
      DATABASE_URL: postgresql://playlist:playlist@db:5432/playlistdb

      # Spotify API (vul hieronder je eigen credentials in)
      SPOTIFY_CLIENT_ID: ${SPOTIFY_CLIENT_ID}
      SPOTIFY_CLIENT_SECRET: ${SPOTIFY_CLIENT_SECRET}
      SPOTIFY_REDIRECT_URI: http://localhost:8888/callback

      # OpenAI API (vul hieronder je eigen key in)
      OPENAI_API_KEY: ${OPENAI_API_KEY}

      # Logging
      LOG_LEVEL: INFO
      LOG_FILE: /app/logs/wissellijst.log

    ports:
      - "8000:8000"
    command: >
      sh -c "pip install --no-cache-dir -r requirements.txt &&
             uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - wissellijst-network

  db:
    image: postgres:16
    container_name: wissellijst-db
    environment:
      POSTGRES_USER: playlist
      POSTGRES_PASSWORD: playlist
      POSTGRES_DB: playlistdb
      POSTGRES_INITDB_ARGS: "-E UTF8"
    volumes:
      # LET OP: Pas dit pad aan naar je Synology locatie!
      # Bijvoorbeeld: /volume1/docker/wissellijst/pgdata:/var/lib/postgresql/data
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U playlist -d playlistdb"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - wissellijst-network

networks:
  wissellijst-network:
    driver: bridge

volumes:
  pgdata:
    driver: local
```

---

## Stap 3: Environment Variables Configureren

Scroll naar beneden in Portainer naar de sectie **Environment variables**.

Klik op **+ add environment variable** en voeg de volgende toe:

| Name | Value |
|------|-------|
| `SPOTIFY_CLIENT_ID` | `<jouw-spotify-client-id>` |
| `SPOTIFY_CLIENT_SECRET` | `<jouw-spotify-client-secret>` |
| `OPENAI_API_KEY` | `<jouw-openai-api-key>` |

> **Let op:** Vervang de placeholders met je echte API keys!

---

## Stap 4: Code Uploaden naar Synology

Je moet de code van deze repository op je Synology plaatsen.

### Optie A: Via Git (Aanbevolen)

SSH naar je Synology en clone de repository:

```bash
# SSH naar je NAS
ssh <gebruiker>@<nas-ip>

# Ga naar de docker directory
cd /volume1/docker

# Clone de repository
git clone https://github.com/gjagils/Wissellijst.git
cd Wissellijst

# Checkout de juiste branch
git checkout claude/playlist-refresh-system-MmWqC

# Maak directories aan
mkdir -p secrets logs
```

### Optie B: Via File Station

1. Open File Station op je Synology
2. Ga naar `/docker/` (of maak deze aan)
3. Maak een nieuwe map `wissellijst`
4. Upload de hele `app` folder uit deze repository
5. Maak een `secrets` folder aan
6. Maak een `logs` folder aan

---

## Stap 5: Docker Compose Paden Aanpassen

In de docker-compose.yml in Portainer, pas de volume paden aan naar je Synology locatie:

**Als je git hebt gebruikt in `/volume1/docker/Wissellijst`:**

```yaml
volumes:
  - /volume1/docker/Wissellijst/app:/app
  - /volume1/docker/Wissellijst/secrets:/app/.secrets
```

**Als je File Station hebt gebruikt in `/volume1/docker/wissellijst`:**

```yaml
volumes:
  - /volume1/docker/wissellijst/app:/app
  - /volume1/docker/wissellijst/secrets:/app/.secrets
```

---

## Stap 6: Stack Deployen

1. Scroll naar beneden in Portainer
2. Klik op **Deploy the stack**
3. Wacht tot de containers starten (kan 1-2 minuten duren voor app container)

Je kunt de logs bekijken:
- Ga naar **Containers** in Portainer
- Klik op `wissellijst-app`
- Klik op **Logs**

---

## Stap 7: Database Initialiseren

De database moet geïnitialiseerd worden met alle tabellen.

### Via Portainer Console:

1. Ga naar **Containers**
2. Klik op `wissellijst-app`
3. Klik op **Console** (>_ icoon)
4. Selecteer `/bin/sh` en klik **Connect**
5. Voer uit:

```bash
# Initialiseer database (maakt alle tabellen aan)
python init_db.py
```

Het script vraagt of je bestaande tabellen wilt verwijderen (voor eerste installatie antwoord gewoon "no"):
```
Do you want to drop and recreate all tables? (yes/no): no
```

Je zou output moeten zien zoals:
```
🔗 Connecting to database...
   URL: postgresql://playlist@***
🔨 Creating all tables from models...
✅ Database initialized successfully!
📊 Created 7 tables:
   - block_tracks
   - playlist_blocks
   - playlist_rules
   - playlists
   - run_changes
   - runs
   - track_history
🎉 Ready to use!
```

### Via SSH (alternatief):

```bash
# SSH naar je NAS
ssh <gebruiker>@<nas-ip>

# Voer init script uit in container
docker exec -it wissellijst-app python init_db.py
```

**Let op:** Dit script maakt ALLE tabellen aan inclusief de nieuwe velden uit Sprint 1-4. Je hoeft daarna geen Alembic migrations meer uit te voeren voor de eerste installatie.

---

## Stap 8: Spotify Authenticatie

Voor de eerste keer moet je Spotify authenticeren.

### Via Portainer Console:

1. Open de console van `wissellijst-app` (zie Stap 7)
2. Voer uit:

```bash
python authenticate_spotify.py
```

3. Je krijgt een URL te zien. **Kopieer deze** en open in een browser
4. Log in met Spotify en geef toestemming
5. Je wordt doorgestuurd naar `http://localhost:8888/callback?code=...`
6. Kopieer de **hele URL** uit de browser (inclusief `http://localhost:8888/callback?code=...`)
7. Plak deze in de console en druk op Enter

Je zou moeten zien:
```
✅ Succesvol geauthenticeerd met Spotify!
🎉 Token opgeslagen in /app/.secrets/spotify_cache
```

De token wordt opgeslagen in `/app/.secrets/spotify_cache`

---

## Stap 9: Dashboard Openen

Open een browser en ga naar:

```
http://<nas-ip>:8000/
```

Je zou de Wissellijst dashboard moeten zien met 4 tabs:
- Dashboard
- Playlists
- Runs
- Scheduler

---

## Stap 10: Eerste Playlist Aanmaken

### Via API (Swagger UI):

1. Ga naar `http://<nas-ip>:8000/docs`
2. Klik op **POST /bootstrap/playlist**
3. Klik op **Try it out**
4. Vul in:

```json
{
  "name": "Door de tijd heen",
  "vibe": "A diverse journey through different decades, from classic 80s hits to modern 2020s tracks. Mix of international and occasional Dutch tracks, spanning various genres.",
  "key": "door-de-tijd",
  "policies": {
    "decade_distribution": {
      "1980s": 1,
      "1990s": 1,
      "2000s": 1,
      "2010s": 1,
      "2020s": 1
    },
    "max_dutch_per_block": 1,
    "history_months": 12
  }
}
```

5. Klik **Execute**
6. Je zou een 200 response moeten krijgen met de nieuwe playlist

### Herhaal voor andere playlists:

**Met hart en Soul:**
```json
{
  "name": "Met hart en Soul",
  "vibe": "Smooth soul, neo-soul and indie soul tracks. Focus on vocal quality and emotional depth. No Dutch language tracks.",
  "key": "met-hart-en-soul",
  "policies": {
    "allowed_genres": ["soul", "neo-soul", "indie soul", "r&b"],
    "forbidden_languages": ["nl"],
    "history_months": 3
  }
}
```

**In je moerstaal:**
```json
{
  "name": "In je moerstaal",
  "vibe": "Dutch language music spanning multiple decades. Mix of classic and modern Dutch tracks, various genres from pop to hip-hop.",
  "key": "in-je-moerstaal",
  "policies": {
    "required_language": "nl",
    "year_distribution": {
      "pre_2000": 2,
      "post_2000": 2,
      "wildcard": 1
    },
    "history_months": 12
  }
}
```

---

## Stap 11: Eerste Test Run

Nu kun je een test refresh doen:

1. Ga naar de dashboard: `http://<nas-ip>:8000/`
2. Klik op de **Playlists** tab
3. Bij "Door de tijd heen", klik op **Preview Refresh**
4. Ga naar de **Runs** tab
5. Je ziet een nieuwe run met status "Preview"
6. Klik op **View Details**
7. Review de voorgestelde tracks:
   - 5 tracks worden verwijderd (auto-approved)
   - 5 nieuwe tracks worden voorgesteld door AI
8. Klik op **✓** bij elke track die je wilt toevoegen
9. Als alle tracks approved zijn, klik op **Commit Run**

De playlist wordt nu bijgewerkt in Spotify! 🎉

---

## Stap 12: Scheduler Activeren (Optioneel)

Om automatische wekelijkse refreshes in te stellen:

### Via API (Swagger UI):

1. Ga naar `http://<nas-ip>:8000/docs`
2. Klik op **PATCH /playlists/{key}/schedule**
3. Vul in:
   - `key`: `door-de-tijd`
   - Request body:
   ```json
   {
     "refresh_schedule": "0 10 * * 1",
     "is_auto_commit": false
   }
   ```
   (Betekent: elke maandag om 10:00 uur, manual approval required)

4. Herhaal voor andere playlists met andere tijden

### Cron Schema:

```
0 10 * * 1  = Maandag 10:00
0 10 * * 2  = Dinsdag 10:00
0 10 * * 3  = Woensdag 10:00
```

Format: `minuut uur dag maand weekdag`

---

## Troubleshooting

### Container start niet:

**Logs bekijken:**
- Portainer → Containers → wissellijst-app → Logs

**Veelvoorkomende problemen:**
- **"requirements.txt not found"**: Volume pad is niet correct
- **"Connection refused to database"**: Database container is nog niet klaar, wacht 30 sec
- **"ImportError: No module named..."**: Dependencies worden geïnstalleerd, wacht af

### Database verbinding mislukt:

```bash
# Test database verbinding
docker exec -it wissellijst-db psql -U playlist -d playlistdb

# Binnen psql:
\dt  # Toon alle tabellen (zou 7 tabellen moeten tonen)
\q   # Quit
```

### Database initialisatie mislukt:

**Error: "relation 'playlists' does not exist"**
- Dit betekent dat de tabellen nog niet zijn aangemaakt
- Run `python init_db.py` opnieuw in de app container

**Error: "could not connect to server"**
- Database container is nog niet klaar
- Wacht 30 seconden en probeer opnieuw

**Tabellen opnieuw aanmaken:**
```bash
docker exec -it wissellijst-app python init_db.py
# Antwoord "yes" als gevraagd of je tabellen wilt verwijderen
```

### API keys werken niet:

Controleer of de environment variables correct zijn ingesteld:

```bash
docker exec -it wissellijst-app env | grep SPOTIFY
docker exec -it wissellijst-app env | grep OPENAI
```

### Spotify authenticatie mislukt:

1. Controleer of `SPOTIFY_REDIRECT_URI` exact `http://localhost:8888/callback` is
2. Controleer of deze URI ook in je Spotify Developer Dashboard staat
3. Verwijder oude token: `docker exec -it wissellijst-app rm -rf .secrets/.cache*`
4. Probeer opnieuw

### Dashboard toont geen data:

1. Open browser console (F12)
2. Check voor JavaScript errors
3. Check of API bereikbaar is: `http://<nas-ip>:8000/docs`

---

## Handige Commands

### Logs bekijken:

```bash
# App logs (real-time)
docker logs -f wissellijst-app

# Database logs
docker logs -f wissellijst-db

# Laatste 100 regels
docker logs --tail 100 wissellijst-app
```

### Container herstarten:

Via Portainer:
- Containers → wissellijst-app → Restart

Of via SSH:
```bash
docker restart wissellijst-app
```

### Stack updaten na code wijzigingen:

```bash
# SSH naar NAS
ssh <gebruiker>@<nas-ip>

# Pull latest code
cd /volume1/docker/Wissellijst
git pull origin claude/playlist-refresh-system-MmWqC

# Herstart container in Portainer
# Containers → wissellijst-app → Restart
```

### Database backup:

```bash
# Backup maken
docker exec wissellijst-db pg_dump -U playlist playlistdb > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i wissellijst-db psql -U playlist playlistdb < backup_20260124.sql
```

---

## Poorten

Zorg dat deze poorten beschikbaar zijn op je Synology:

- **8000**: Wissellijst API en Dashboard
- **5432**: PostgreSQL (alleen nodig voor externe toegang)

### Firewall regel (optioneel):

Als je de dashboard vanaf andere computers wilt benaderen:
1. Synology DSM → Control Panel → Security → Firewall
2. Maak nieuwe regel voor port 8000

---

## Beveiliging

**Aanbevelingen voor productie:**

1. **Wijzig database wachtwoord:**
   ```yaml
   environment:
     POSTGRES_PASSWORD: <sterk-wachtwoord>
   ```
   En update `DATABASE_URL` in app environment

2. **Gebruik Docker secrets** in plaats van environment variables voor API keys

3. **Reverse proxy** (nginx/Traefik) voor HTTPS

4. **Beperkte toegang** tot Portainer en dashboard

5. **Regular backups** van database en secrets

---

## Volgende Stappen

Na succesvolle deployment:

1. **Maak alle 3 playlists aan** (zie Stap 10)
2. **Test elke playlist** met een preview refresh
3. **Configureer schedules** voor automatische refreshes
4. **Monitor logs** eerste week voor eventuele issues
5. **Backup je secrets directory** (bevat Spotify token)

---

## Support

Bij problemen:
1. Check de logs (zie Troubleshooting)
2. Controleer of alle environment variables correct zijn
3. Test API endpoints via Swagger UI (`/docs`)
4. Bekijk database status met `docker exec`

---

**Veel succes met je Wissellijst deployment! 🎵**
