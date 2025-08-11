#!/usr/bin/env python3
"""
Test AI Spine startup
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ.setdefault("DEV_MODE", "true")

def test_imports():
    """Test that all modules can be imported"""
    try:
        print("Testing core imports...")
        
        # Test models
        from src.core.models import ExecutionRequest, FlowDefinition
        print("  Models imported successfully")
        
        # Test memory
        from src.core.memory import memory_store
        print("  Memory store imported successfully")
        
        # Test orchestrator
        from src.core.orchestrator import orchestrator
        print("  Orchestrator imported successfully")
        
        # Test registry
        from src.core.registry import registry
        print("  Registry imported successfully")
        
        # Test auth
        from src.core.auth import auth_manager
        print("  Auth manager imported successfully")
        
        print("\nAll core components imported successfully!")
        return True
        
    except Exception as e:
        print(f"Import failed: {e}")
        return False

def test_api():
    """Test that API can be imported"""
    try:
        print("\nTesting API imports...")
        
        from src.api.main import app
        print("  FastAPI app imported successfully")
        
        return True
    except Exception as e:
        print(f"API import failed: {e}")
        return False

async def test_startup():
    """Test startup sequence"""
    try:
        print("\nTesting startup sequence...")
        
        from src.core.memory import memory_store
        from src.core.orchestrator import orchestrator
        from src.core.registry import registry
        from src.core.communication import communication_manager
        
        # Start components
        await memory_store.start()
        print("  Memory store started")
        
        await registry.start()
        print("  Registry started")
        
        await communication_manager.start()
        print("  Communication manager started")
        
        await orchestrator.start()
        print("  Orchestrator started")
        
        print("\nAll components started successfully!")
        
        # Stop components
        # Note: orchestrator doesn't have a stop method
        await memory_store.stop()
        await communication_manager.stop()
        await registry.stop()
        
        print("  All components stopped cleanly")
        return True
        
    except Exception as e:
        print(f"Startup test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    print("AI Spine Startup Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        return False
    
    if not test_api():
        return False
    
    # Test startup
    if not await test_startup():
        return False
    
    print("\nAll tests passed! AI Spine is ready to run.")
    return True

if __name__ == "__main__":
    import asyncio
    success = asyncio.run(main())
    sys.exit(0 if success else 1)