#!/usr/bin/env python3
"""
Database Setup Script for AI Spine

This script initializes the PostgreSQL database and creates all necessary tables.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Load environment variables
load_dotenv(".env.local")

from src.core.database import db_manager
from src.core.models import Base

async def test_database_connection():
    """Test the database connection"""
    print("Testing database connection...")
    
    try:
        # Test sync connection
        engine = create_engine(db_manager.sync_database_url)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"PostgreSQL connection successful!")
            print(f"   Version: {version}")
        
        return True
    except OperationalError as e:
        print(f"Database connection failed: {e}")
        print("\nTroubleshooting tips:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your DATABASE_URL in config.env")
        print("3. Verify the database exists")
        print("4. Check username and password")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def create_database_if_not_exists():
    """Create the database if it doesn't exist"""
    print("Checking if database exists...")
    
    # Parse database URL to get database name
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL not found in config.env")
        return False
    
    # Extract database name from URL
    # Format: postgresql+psycopg2://user:pass@host:port/dbname
    try:
        db_name = database_url.split('/')[-1]
        base_url = database_url.rsplit('/', 1)[0]
        
        print(f"   Database name: {db_name}")
        
        # Connect to postgres database to check if our database exists
        postgres_url = f"{base_url}/postgres"
        engine = create_engine(postgres_url)
        
        with engine.connect() as conn:
            # Check if database exists
            result = conn.execute(text(
                "SELECT 1 FROM pg_database WHERE datname = :db_name"
            ), {"db_name": db_name})
            
            if result.fetchone():
                print(f"Database '{db_name}' already exists")
                return True
            else:
                print(f"Creating database '{db_name}'...")
                # Note: CREATE DATABASE cannot be executed in a transaction
                conn.execute(text("COMMIT"))
                conn.execute(text(f"CREATE DATABASE {db_name}"))
                print(f"Database '{db_name}' created successfully")
                return True
                
    except Exception as e:
        print(f"Failed to create database: {e}")
        print("\nYou may need to create the database manually:")
        print(f"   psql -U postgres -c 'CREATE DATABASE {db_name};'")
        return False

async def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    
    try:
        await db_manager.create_tables()
        print("All tables created successfully!")
        return True
    except Exception as e:
        print(f"Failed to create tables: {e}")
        return False

async def verify_setup():
    """Verify the database setup is working"""
    print("Verifying database setup...")
    
    try:
        async with db_manager.get_async_session() as session:
            # Try a simple query
            result = await session.execute(text("SELECT 1"))
            if result.fetchone():
                print("Database setup verified successfully!")
                return True
    except Exception as e:
        print(f"Verification failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("AI Spine Database Setup")
    print("=" * 50)
    
    # Show current configuration
    database_url = os.getenv("DATABASE_URL", "Not set")
    print(f"Database URL: {database_url}")
    print()
    
    # Step 1: Create database if needed
    if not create_database_if_not_exists():
        print("Database creation failed. Please check your PostgreSQL setup.")
        return False
    
    # Step 2: Test connection
    if not await test_database_connection():
        print("Setup failed at connection test.")
        return False
    
    # Step 3: Create tables
    if not await create_tables():
        print("Setup failed at table creation.")
        return False
    
    # Step 4: Verify setup
    if not await verify_setup():
        print("Setup failed at verification.")
        return False
    
    print("\nDatabase setup completed successfully!")
    print("   You can now start the AI Spine backend.")
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    if not success:
        sys.exit(1)