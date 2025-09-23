#!/usr/bin/env python3
"""
AI Spine Main Entry Point
Single entry point for Railway deployment
"""

import os
import sys
import asyncio
from pathlib import Path
import uvicorn
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env.local (if exists)
if Path(".env.local").exists():
    load_dotenv(".env.local")

async def init_database():
    """Initialize Supabase connection"""
    import time
    start_time = time.time()

    try:
        print(f"[STARTUP] Starting database initialization at {time.time()}")
        dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
        print(f"[STARTUP] DEV_MODE: {dev_mode}")

        if not dev_mode:
            print("[STARTUP] Production mode - connecting to Supabase...")
            print(f"[STARTUP] SUPABASE_URL: {os.getenv('SUPABASE_URL', 'NOT_SET')[:50]}...")
            print(f"[STARTUP] SUPABASE_SERVICE_KEY: {'SET' if os.getenv('SUPABASE_SERVICE_KEY') else 'NOT_SET'}")

            # Supabase tables are already created via Dashboard
            # Just verify connection
            from src.core.supabase_client import get_supabase_db
            print("[STARTUP] Importing Supabase client...")
            db = get_supabase_db()
            print("[STARTUP] Supabase client created successfully")

            # Test connection
            try:
                test_result = db.client.table("api_users").select("count", count="exact").limit(1).execute()
                print(f"[STARTUP] Supabase connection test successful")
            except Exception as test_e:
                print(f"[STARTUP] Supabase connection test failed: {test_e}")

            print("[STARTUP] Supabase connection ready")
        else:
            print("[STARTUP] Development mode - using in-memory storage")

        elapsed = time.time() - start_time
        print(f"[STARTUP] Database initialization completed in {elapsed:.2f}s")

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[STARTUP] Database initialization FAILED after {elapsed:.2f}s: {e}")
        print(f"[STARTUP] Error type: {type(e).__name__}")
        print("[STARTUP] Check SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables")
        # Don't raise - allow app to continue
        return False

    return True

def main():
    """Start the AI Spine infrastructure"""
    import time

    print(f"[STARTUP] AI Spine main() started at {time.time()}")

    # Get configuration from environment variables
    # Railway provides PORT env variable
    port = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
    host = os.getenv("API_HOST", "0.0.0.0")
    debug = os.getenv("API_DEBUG", "false").lower() == "true"

    print(f"[STARTUP] Configuration - HOST: {host}, PORT: {port}, DEBUG: {debug}")
    print(f"[STARTUP] Environment variables:")
    print(f"[STARTUP]   PORT: {os.getenv('PORT', 'NOT_SET')}")
    print(f"[STARTUP]   API_PORT: {os.getenv('API_PORT', 'NOT_SET')}")
    print(f"[STARTUP]   DEV_MODE: {os.getenv('DEV_MODE', 'NOT_SET')}")

    # Initialize database
    print("[STARTUP] Calling init_database()...")
    db_result = asyncio.run(init_database())
    print(f"[STARTUP] Database initialization result: {db_result}")

    print("=" * 50)
    print("AI SPINE - Multi-Agent Orchestration Platform")
    print("=" * 50)
    print(f"Starting on {host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Health Check: http://{host}:{port}/health")
    print("=" * 50)

    print(f"[STARTUP] About to start uvicorn server...")

    try:
        # Start the FastAPI application
        uvicorn.run(
            "src.api.main:app",
            host=host,
            port=port,
            reload=debug,
            log_level="info"
        )
    except Exception as e:
        print(f"[STARTUP] Uvicorn failed to start: {e}")
        print(f"[STARTUP] Error type: {type(e).__name__}")
        raise

if __name__ == "__main__":
    main()