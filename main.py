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
    try:
        dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
        
        if not dev_mode:
            print("Connecting to Supabase...")
            # Supabase tables are already created via Dashboard
            # Just verify connection
            from src.core.supabase_client import get_supabase_db
            db = get_supabase_db()
            print("Supabase connection ready")
        else:
            print("Running in development mode - using in-memory storage")
            
    except Exception as e:
        print(f"Supabase connection failed: {e}")
        print("Check SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables")

def main():
    """Start the AI Spine infrastructure"""
    # Initialize database
    asyncio.run(init_database())
    
    # Get configuration from environment variables
    # Railway provides PORT env variable
    port = int(os.getenv("PORT", os.getenv("API_PORT", "8000")))
    host = os.getenv("API_HOST", "0.0.0.0")
    debug = os.getenv("API_DEBUG", "false").lower() == "true"
    
    print("=" * 50)
    print("AI SPINE - Multi-Agent Orchestration Platform")
    print("=" * 50)
    print(f"Starting on {host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Health Check: http://{host}:{port}/health")
    print("=" * 50)
    
    # Start the FastAPI application
    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info"
    )

if __name__ == "__main__":
    main()