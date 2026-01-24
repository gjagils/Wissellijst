-- Verification script for Sprint 1 database migration
-- Run this inside the PostgreSQL container to verify all changes were applied correctly

\echo '=== VERIFYING SPRINT 1 DATABASE MIGRATION ==='
\echo ''

-- Check if new tables exist
\echo '1. Checking if new tables exist...'
SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'runs')
        THEN '✓ runs table exists'
        ELSE '✗ runs table MISSING'
    END as status
UNION ALL
SELECT
    CASE
        WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'run_changes')
        THEN '✓ run_changes table exists'
        ELSE '✗ run_changes table MISSING'
    END;

\echo ''
\echo '2. Checking playlists table new columns...'
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'playlists'
  AND column_name IN ('refresh_schedule', 'is_auto_commit')
ORDER BY column_name;

\echo ''
\echo '3. Checking block_tracks table new columns...'
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'block_tracks'
  AND column_name IN ('year', 'language', 'genre_tags', 'added_at')
ORDER BY column_name;

\echo ''
\echo '4. Checking runs table structure...'
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'runs'
ORDER BY ordinal_position;

\echo ''
\echo '5. Checking run_changes table structure...'
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'run_changes'
ORDER BY ordinal_position;

\echo ''
\echo '6. Checking foreign key constraints...'
SELECT
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_name IN ('runs', 'run_changes')
ORDER BY tc.table_name, tc.constraint_name;

\echo ''
\echo '7. Checking alembic_version table...'
SELECT version_num,
       CASE
           WHEN version_num = 'ac11471a3939' THEN '✓ Sprint 1 migration applied'
           ELSE '⚠ Different migration version: ' || version_num
       END as migration_status
FROM alembic_version;

\echo ''
\echo '=== VERIFICATION COMPLETE ==='
\echo ''
\echo 'Expected results:'
\echo '  - runs and run_changes tables should exist'
\echo '  - playlists should have refresh_schedule and is_auto_commit columns'
\echo '  - block_tracks should have year, language, genre_tags, and added_at columns'
\echo '  - Foreign keys should reference playlists.id and runs.id correctly'
\echo '  - alembic_version should show: ac11471a3939'
\echo ''
