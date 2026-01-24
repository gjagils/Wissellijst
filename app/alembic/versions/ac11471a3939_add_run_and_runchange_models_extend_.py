"""Add Run and RunChange models, extend metadata fields

Revision ID: ac11471a3939
Revises:
Create Date: 2026-01-24 13:03:45.432114

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ac11471a3939'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scheduling fields to playlists table
    op.add_column('playlists', sa.Column('refresh_schedule', sa.String(length=100), nullable=True))
    op.add_column('playlists', sa.Column('is_auto_commit', sa.Boolean(), nullable=False, server_default='false'))

    # Add metadata fields to block_tracks table
    op.add_column('block_tracks', sa.Column('year', sa.Integer(), nullable=True))
    op.add_column('block_tracks', sa.Column('language', sa.String(length=10), nullable=True))
    op.add_column('block_tracks', sa.Column('genre_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('block_tracks', sa.Column('added_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')))

    # Create runs table
    op.create_table(
        'runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playlist_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['playlist_id'], ['playlists.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create run_changes table
    op.create_table(
        'run_changes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('spotify_track_id', sa.String(length=64), nullable=False),
        sa.Column('artist', sa.String(length=256), nullable=False),
        sa.Column('title', sa.String(length=256), nullable=False),
        sa.Column('block_index', sa.Integer(), nullable=True),
        sa.Column('position_in_block', sa.Integer(), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('decade', sa.Integer(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=True),
        sa.Column('genre_tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_ai_suggested', sa.Boolean(), nullable=False),
        sa.Column('is_approved', sa.Boolean(), nullable=False),
        sa.Column('suggested_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('run_changes')
    op.drop_table('runs')

    # Remove columns from block_tracks
    op.drop_column('block_tracks', 'added_at')
    op.drop_column('block_tracks', 'genre_tags')
    op.drop_column('block_tracks', 'language')
    op.drop_column('block_tracks', 'year')

    # Remove columns from playlists
    op.drop_column('playlists', 'is_auto_commit')
    op.drop_column('playlists', 'refresh_schedule')
