# Database Migrations

This directory contains Alembic database migrations for the Wissellijst project.

## Setup

Alembic is already configured to use the `DATABASE_URL` environment variable. Make sure your `.env` file contains:

```bash
DATABASE_URL=postgresql://playlist:playlist@db:5432/playlistdb
```

## Running Migrations

### Inside Docker Container

When the app container starts, migrations should run automatically. If you need to run them manually:

```bash
# Enter the app container
docker compose exec app bash

# Run migrations
cd /app
alembic upgrade head
```

### During Development (Local)

If you're developing locally with a database:

```bash
cd app
alembic upgrade head
```

## Creating New Migrations

### Auto-generate from model changes

```bash
cd app
alembic revision --autogenerate -m "Description of changes"
```

### Manual migration

```bash
cd app
alembic revision -m "Description of changes"
# Then edit the generated file in alembic/versions/
```

## Migration History

### ac11471a3939 - Initial Sprint 1 Changes

**Date**: 2026-01-24

**Changes**:
- Added `Run` table for tracking playlist refresh runs
- Added `RunChange` table for tracking individual track changes in runs
- Extended `playlists` table with:
  - `refresh_schedule` (cron expression for automatic refreshes)
  - `is_auto_commit` (auto-approve AI suggestions)
- Extended `block_tracks` table with metadata fields:
  - `year` (release year)
  - `language` (nl/en/other)
  - `genre_tags` (JSONB with genre classifications)
  - `added_at` (timestamp when track was added)

**Purpose**: Foundation for the playlist refresh system with AI-driven suggestions and manual override capabilities.

## Rollback

To rollback the last migration:

```bash
alembic downgrade -1
```

To rollback to a specific revision:

```bash
alembic downgrade <revision_id>
```

To rollback all migrations:

```bash
alembic downgrade base
```

## Checking Current Version

```bash
alembic current
```

## Viewing Migration History

```bash
alembic history --verbose
```

## Troubleshooting

### "Target database is not up to date"

This means there are pending migrations. Run:

```bash
alembic upgrade head
```

### "Can't locate revision identified by..."

The migrations table might be out of sync. Check:

```bash
alembic current
alembic history
```

### Fresh Database Setup

If you have a completely fresh database:

```bash
# This will create all tables from scratch
alembic upgrade head
```

### Resetting Database (Development Only!)

**WARNING**: This will delete all data!

```bash
# Drop all tables
docker compose down -v  # This removes volumes

# Start fresh
docker compose up -d
docker compose exec app alembic upgrade head
```
