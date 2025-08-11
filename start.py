#!/usr/bin/env python3
"""
AI Spine Startup Script
Starts the multi-agent infrastructure
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

# Load environment variables from .env.local
load_dotenv(".env.local")

async def init_database():
    """Initialize database tables if they don't exist"""
    try:
        from src.core.database import db_manager
        dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
        
        if not dev_mode:
            print("Initializing database...")
            await db_manager.create_tables()
            print("Database tables ready")
        else:
            print("Running in development mode - using in-memory storage")
            
    except Exception as e:
        print(f"Database initialization failed: {e}")
        print("Falling back to development mode")
        os.environ["DEV_MODE"] = "true"

def main():
    """Start the AI Spine infrastructure"""
    # Initialize database
    asyncio.run(init_database())
    
    # Get configuration from environment variables
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    debug = os.getenv("API_DEBUG", "true").lower() == "true"
    
    print(f"Starting AI Spine on {host}:{port}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Health Check: http://{host}:{port}/health")
    
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