#!/usr/bin/env python3
"""
Neon Database Setup Script for AI Spine
Creates all necessary tables in your Neon PostgreSQL database
"""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.ext.asyncio import create_async_engine

# Load environment variables
load_dotenv(".env.local")

# Import models after loading env
from src.core.models import Base

def get_database_url():
    """Get database URL from environment"""
    url = os.getenv("DATABASE_URL")
    if not url:
        print("❌ DATABASE_URL not found in .env.local")
        print("Please add your Neon connection string to .env.local")
        sys.exit(1)
    return url

def get_async_url(sync_url):
    """Convert sync URL to async URL for asyncpg"""
    # Replace postgresql:// with postgresql+asyncpg://
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url

async def test_connection():
    """Test database connection"""
    print("🔍 Testing connection to Neon...")
    
    try:
        url = get_database_url()
        # For testing, use sync engine
        engine = create_engine(url)
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected to Neon PostgreSQL!")
            print(f"   Version: {version}")
            print(f"   Database: {engine.url.database}")
            print(f"   Host: {engine.url.host}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False

async def create_tables():
    """Create all tables defined in models"""
    print("\n📋 Creating tables...")
    
    try:
        url = get_database_url()
        engine = create_engine(url)
        
        # Check existing tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        if existing_tables:
            print(f"   Found {len(existing_tables)} existing tables:")
            for table in existing_tables:
                print(f"     • {table}")
        
        # Create all tables
        Base.metadata.create_all(bind=engine)
        
        # Check tables after creation
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        
        print(f"\n✅ Database setup complete!")
        print(f"   Total tables: {len(all_tables)}")
        print("\n   Tables created:")
        for table in all_tables:
            print(f"     • {table}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False

async def verify_tables():
    """Verify tables are accessible"""
    print("\n🔍 Verifying table access...")
    
    try:
        url = get_database_url()
        engine = create_engine(url)
        
        # Test queries on main tables
        with engine.connect() as conn:
            # Test agents table
            result = conn.execute(text("SELECT COUNT(*) FROM agents"))
            agent_count = result.scalar()
            print(f"   ✓ agents table: {agent_count} records")
            
            # Test execution_contexts table
            result = conn.execute(text("SELECT COUNT(*) FROM execution_contexts"))
            exec_count = result.scalar()
            print(f"   ✓ execution_contexts table: {exec_count} records")
            
            # Test node_execution_results table
            result = conn.execute(text("SELECT COUNT(*) FROM node_execution_results"))
            node_count = result.scalar()
            print(f"   ✓ node_execution_results table: {node_count} records")
            
            # Test agent_messages table
            result = conn.execute(text("SELECT COUNT(*) FROM agent_messages"))
            msg_count = result.scalar()
            print(f"   ✓ agent_messages table: {msg_count} records")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Table verification failed: {e}")
        return False

async def main():
    """Main setup function"""
    print("🚀 AI Spine - Neon Database Setup")
    print("=" * 50)
    
    # Show configuration
    db_url = get_database_url()
    # Hide password in display
    display_url = db_url.split('@')[1] if '@' in db_url else db_url
    print(f"📍 Database: ...@{display_url[:50]}...")
    print()
    
    # Check if we're in dev mode
    dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
    if dev_mode:
        print("⚠️  WARNING: DEV_MODE is set to 'true'")
        print("   Set DEV_MODE=false in .env.local to use Neon database")
        response = input("\nContinue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return False
    
    # Test connection
    if not await test_connection():
        print("\n❌ Cannot connect to database. Please check:")
        print("   1. Your DATABASE_URL is correct")
        print("   2. Neon database is active")
        print("   3. Network connection is working")
        return False
    
    # Create tables
    if not await create_tables():
        return False
    
    # Verify tables
    if not await verify_tables():
        return False
    
    print("\n✨ Setup completed successfully!")
    print("\nNext steps:")
    print("1. Set DEV_MODE=false in .env.local")
    print("2. Run: python main.py")
    print("3. Visit: http://localhost:8000/docs")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)