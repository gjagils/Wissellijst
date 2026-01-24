#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables from SQLAlchemy models.
Run this for fresh installations before using Alembic migrations.
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, inspect
from src.db.models import Base
from src.db.session import get_db_url


def init_database():
    """Initialize database with all tables."""

    # Get database URL
    db_url = get_db_url()
    print(f"🔗 Connecting to database...")
    print(f"   URL: {db_url.split('@')[0]}@***")  # Hide password

    # Create engine
    engine = create_engine(db_url, echo=True)

    # Check if tables already exist
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    if existing_tables:
        print(f"\n⚠️  Found existing tables: {', '.join(existing_tables)}")
        response = input("Do you want to drop and recreate all tables? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled. No changes made.")
            return

        print("\n🗑️  Dropping all existing tables...")
        Base.metadata.drop_all(bind=engine)
        print("✅ All tables dropped.")

    # Create all tables
    print("\n🔨 Creating all tables from models...")
    Base.metadata.create_all(bind=engine)

    # Verify creation
    inspector = inspect(engine)
    created_tables = inspector.get_table_names()

    print("\n✅ Database initialized successfully!")
    print(f"📊 Created {len(created_tables)} tables:")
    for table in sorted(created_tables):
        print(f"   - {table}")

    print("\n🎉 Ready to use! You can now:")
    print("   1. Start the API: uvicorn src.main:app --reload")
    print("   2. Create playlists via /bootstrap/playlist")
    print("   3. Authenticate with Spotify")


if __name__ == "__main__":
    try:
        init_database()
    except Exception as e:
        print(f"\n❌ Error initializing database: {e}")
        sys.exit(1)
