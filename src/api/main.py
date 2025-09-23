import asyncio
import yaml
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import structlog
from typing import List, Dict, Any, Optional
from uuid import UUID

from src.core.models import ExecutionRequest, ExecutionResponse, ExecutionContextResponse
from src.core.orchestrator import orchestrator
from src.core.registry import registry
from src.core.tools_registry import tools_registry
from src.core.communication import communication_manager
from src.core.memory import memory_store
from src.core.auth import require_api_key, optional_api_key, auth_manager
from src.api.agents import router as agents_router
from src.api.tools import router as tools_router
from src.api.flows import router as flows_router
from src.api.executions import router as executions_router
from src.api.marketplace_simple import router as marketplace_router
from src.api.users import router as users_router
from src.api.user_keys import router as user_keys_router
from src.api.user_keys_secure import router as user_account_router
from pathlib import Path
from fastapi.responses import PlainTextResponse

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# --- OpenAPI YAML loading (robusto en ruta y con fallback) ---
OPENAPI_PATH = Path(__file__).resolve().parent / "openapi" / "openapi-v1.yaml"

try:
    OPENAPI_YAML = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
except Exception as e:
    logger.warning("Could not load openapi-v1.yaml; falling back to FastAPI defaults", error=str(e))
    OPENAPI_YAML = {
        "openapi": "3.0.0",
        "info": {
            "title": "AI Spine API",
            "version": "1.0.0",
            "description": "Multi-agent orchestration system",
        },
    }

# Create FastAPI app
app = FastAPI(
    title=OPENAPI_YAML.get("info", {}).get("title", "AI Spine API"),
    description=OPENAPI_YAML.get("info", {}).get("description", "Multi-agent orchestration system"),
    version=OPENAPI_YAML.get("info", {}).get("version", "1.0.0"),
    openapi_version=OPENAPI_YAML.get("openapi", "3.0.0")
)
app.openapi_schema = OPENAPI_YAML


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents_router, prefix="/api/v1")
app.include_router(tools_router, prefix="/api/v1")
app.include_router(flows_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(user_keys_router, prefix="/api/v1")  # Legacy endpoints (will deprecate)
app.include_router(user_account_router, prefix="/api/v1")  # New secure endpoints with JWT

@app.on_event("startup")
async def startup_event():
    """Initialize all core components on startup"""
    import time

    logger.info("FastAPI startup event started")
    logger.info("Starting AI Spine infrastructure")

    try:
        # Start core components with detailed logging
        logger.info("Starting registry...")
        start_time = time.time()
        await registry.start()
        logger.info("Registry started", elapsed_time_s=f"{time.time() - start_time:.2f}")

        logger.info("Starting tools_registry...")
        start_time = time.time()
        await tools_registry.start()
        logger.info("Tools registry started", elapsed_time_s=f"{time.time() - start_time:.2f}")

        logger.info("Starting communication_manager...")
        start_time = time.time()
        await communication_manager.start()
        logger.info("Communication manager started", elapsed_time_s=f"{time.time() - start_time:.2f}")

        logger.info("Starting memory_store...")
        start_time = time.time()
        await memory_store.start()
        logger.info("Memory store started", elapsed_time_s=f"{time.time() - start_time:.2f}")

        logger.info("Starting orchestrator...")
        start_time = time.time()
        await orchestrator.start()
        logger.info("Orchestrator started", elapsed_time_s=f"{time.time() - start_time:.2f}")

        # Register default agents
        # await register_default_agents()  # Commented to prevent auto-registration

        # Log authentication status
        logger.info("Checking authentication...")
        if auth_manager.api_key_required:
            logger.info("API authentication enabled", key=auth_manager.master_api_key[:8] + "...")
        else:
            logger.info("API authentication disabled - development mode")

        logger.info("AI Spine infrastructure started successfully")
    except Exception as e:
        logger.error("Failed to start AI Spine infrastructure", error=str(e), error_type=type(e).__name__)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AI Spine infrastructure")
    
    try:
        await orchestrator.stop()
        await memory_store.stop()
        await communication_manager.stop()
        await tools_registry.stop()
        await registry.stop()
        
        logger.info("AI Spine infrastructure stopped successfully")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

async def register_default_agents():
    """Register default agents (Zoe and Eddie)"""
    try:
        # Register Zoe - Assistant Agent
        await registry.register_agent(
            agent_id="zoe",
            name="Zoe Assistant",
            description="Asistente conversacional que recolecta información del usuario",
            endpoint="http://localhost:8001/zoe",
            capabilities=["conversation", "information_gathering"],
            agent_type="input",
            user_id=None  # System agent
        )
        
        # Register Eddie - Credit Analysis Agent
        await registry.register_agent(
            agent_id="eddie",
            name="Eddie Credit Analyzer",
            description="Analizador de crédito que evalúa solicitudes de préstamo",
            endpoint="http://localhost:8002/eddie",
            capabilities=["credit_analysis", "risk_assessment"],
            agent_type="processor",
            user_id=None  # System agent
        )
        
        logger.info("Default agents registered")
    except Exception as e:
        logger.error("Failed to register default agents", error=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    import time

    logger.info("Health check endpoint called")

    try:
        # Test basic app readiness
        logger.debug("App is responding")

        # Quick database check if in production
        import os
        dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

        if not dev_mode:
            try:
                from src.core.supabase_client import get_supabase_db
                db = get_supabase_db()
                # Quick test query
                result = db.client.table("api_users").select("count", count="exact").limit(1).execute()
                logger.debug("Database connection OK")
            except Exception as db_e:
                logger.warning("Database check failed", error=str(db_e))
                # Don't fail health check for DB issues

        logger.info("Health check successful")
        return {"status": "healthy", "timestamp": time.time()}

    except Exception as e:
        logger.error("Health check failed", error=str(e))
        logger.error("Health check failed", error=str(e))
        return {"status": "unhealthy", "error": str(e), "timestamp": time.time()}

# Debug endpoints for deployment troubleshooting
@app.get("/debug/startup")
async def debug_startup():
    """Debug endpoint for Railway deployment issues"""
    import os
    import time

    return {
        "status": "OK",
        "timestamp": time.time(),
        "environment": {
            "PORT": os.getenv("PORT", "NOT_SET"),
            "DEV_MODE": os.getenv("DEV_MODE", "NOT_SET"),
            "SUPABASE_URL": os.getenv("SUPABASE_URL", "NOT_SET")[:50] + "..." if os.getenv("SUPABASE_URL") else "NOT_SET",
            "SUPABASE_SERVICE_KEY": "SET" if os.getenv("SUPABASE_SERVICE_KEY") else "NOT_SET",
        },
        "process_info": {
            "pid": os.getpid(),
            "python_version": os.sys.version,
        }
    }

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to check all registered routes"""
    return {
        "routes": [
            {
                "path": route.path, 
                "methods": list(route.methods) if hasattr(route, 'methods') else [],
                "name": getattr(route, 'name', 'unknown')
            } 
            for route in app.routes
        ]
    }

@app.get("/debug/imports")
async def debug_imports():
    """Debug endpoint to check if imports are working"""
    try:
        from src.api import tools
        from src.api import agents
        from src.core import tools_registry as tr
        
        return {
            "status": "imports_ok",
            "tools_router": hasattr(tools, 'router'),
            "agents_router": hasattr(agents, 'router'),
            "tools_registry": hasattr(tr, 'tools_registry'),
            "tools_registry_started": len(tr.tools_registry._tools) if hasattr(tr.tools_registry, '_tools') else 0
        }
    except Exception as e:
        return {"status": "import_error", "error": str(e), "error_type": type(e).__name__}

# Flow management endpoints
@app.post("/flows/execute")
async def execute_flow(request: ExecutionRequest, api_key: str = Depends(require_api_key)) -> ExecutionResponse:
    """Execute a flow"""
    try:
        logger.info("Flow execution requested", flow_id=request.flow_id, user=api_key[:8] + "..." if api_key != "anonymous" else "anonymous")
        return await orchestrator.execute_flow(request)
    except Exception as e:
        logger.error("Flow execution failed", flow_id=request.flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/flows")
async def list_flows(api_key: str = Depends(optional_api_key)):
    """List all available flows"""
    try:
        flows = orchestrator.list_flows()
        return {
            "flows": [flow.dict() for flow in flows],
            "count": len(flows)
        }
    except Exception as e:
        logger.error("Failed to list flows", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/flows/{flow_id}")
async def get_flow(flow_id: str, api_key: str = Depends(optional_api_key)):
    """Get a specific flow"""
    try:
        flow = orchestrator.get_flow(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_id}' not found")
        return flow.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/flows")
async def create_flow(flow_data: Dict[str, Any], api_key: str = Depends(require_api_key)):
    """Create a new flow"""
    try:
        from src.core.models import FlowDefinition
        flow_def = FlowDefinition(**flow_data)
        success = await orchestrator.add_flow(flow_def)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to create flow")
        return flow_def.dict()
    except Exception as e:
        logger.error("Failed to create flow", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/flows/{flow_id}")
async def update_flow(flow_id: str, flow_data: Dict[str, Any], api_key: str = Depends(require_api_key)):
    """Update an existing flow"""
    try:
        from src.core.models import FlowDefinition
        flow_def = FlowDefinition(**flow_data)
        success = await orchestrator.update_flow(flow_id, flow_def)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update flow")
        return flow_def.dict()
    except Exception as e:
        logger.error("Failed to update flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/flows/{flow_id}")
async def delete_flow(flow_id: str, api_key: str = Depends(require_api_key)):
    """Delete a flow"""
    try:
        success = await orchestrator.delete_flow(flow_id)
        if not success:
            raise HTTPException(status_code=400, detail=f"Failed to delete flow '{flow_id}'")
        return {"message": f"Flow '{flow_id}' deleted successfully"}
    except Exception as e:
        logger.error("Failed to delete flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Execution management endpoints
@app.get("/executions/{execution_id}")
async def get_execution_status(execution_id: UUID, api_key: str = Depends(require_api_key)):
    """Get execution status"""
    try:
        context = await orchestrator.get_execution_status(execution_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
        return ExecutionContextResponse.from_dict(context).dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get execution status", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/executions/{execution_id}/cancel")
async def cancel_execution(execution_id: UUID, api_key: str = Depends(require_api_key)):
    """Cancel a running execution"""
    try:
        success = await orchestrator.cancel_execution(execution_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found or not running")
        return {"message": "Execution cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel execution", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/executions")
async def list_executions(flow_id: Optional[str] = None, limit: int = 100, offset: int = 0, api_key: str = Depends(require_api_key)):
    """List executions with optional filtering"""
    try:
        executions = await orchestrator.list_executions(flow_id, limit, offset)
        return {
            "executions": [ExecutionContextResponse.from_dict(execution).dict() for execution in executions],
            "count": len(executions),
            "flow_id": flow_id
        }
    except Exception as e:
        logger.error("Failed to list executions", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/executions/{execution_id}/results")
async def get_execution_results(execution_id: UUID, api_key: str = Depends(require_api_key)):
    """Get detailed results for an execution"""
    try:
        node_results = await orchestrator.get_node_results(execution_id)
        return {
            "execution_id": str(execution_id),
            "node_results": node_results,  # Ya son diccionarios
            "count": len(node_results)
        }
    except Exception as e:
        logger.error("Failed to get execution results", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Agent management endpoints
@app.get("/agents")
async def list_agents(api_key: str = Depends(optional_api_key)):
    """List all registered agents"""
    try:
        agents = registry.list_agents()
        return {
            "agents": [agent.dict() for agent in agents],
            "count": len(agents)
        }
    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/active")
async def list_active_agents():
    """List all active agents"""
    try:
        agents = registry.list_active_agents()
        return {
            "agents": [agent.dict() for agent in agents],
            "count": len(agents)
        }
    except Exception as e:
        logger.error("Failed to list active agents", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str):
    """Get a specific agent"""
    try:
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return agent.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents")
async def register_agent(agent_data: Dict[str, Any], auth_result = Depends(require_api_key)):
    """Register a new agent"""
    try:
        # Extract user_id from auth result
        user_id = None
        
        # require_api_key returns different types depending on the key:
        # - "master" for master key
        # - UserInfo object for user API keys
        # - string (the API key) for legacy keys
        # - "anonymous" for no auth (if auth is disabled)
        
        if hasattr(auth_result, 'id'):
            # It's a UserInfo object from a user API key
            user_id = auth_result.id
            logger.info("User API key authenticated", user_id=user_id[:8] if user_id else "None")
        elif auth_result == "master":
            logger.info("Master API key used, no user_id")
        elif isinstance(auth_result, str) and auth_result.startswith("sk_"):
            # Legacy API key - need to look up user_id
            from src.core.supabase_client import get_supabase_db
            try:
                db = get_supabase_db()
                result = db.client.table("api_users").select("id").eq("api_key", auth_result).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]
                    logger.info("Found user for legacy API key", user_id=user_id[:8] if user_id else "None")
            except Exception as e:
                logger.error("Failed to get user_id from legacy API key", error=str(e))
        else:
            logger.info("Auth type not recognized", auth_type=type(auth_result).__name__)
        
        agent = await registry.register_agent(
            agent_id=agent_data["agent_id"],
            name=agent_data["name"],
            description=agent_data["description"],
            endpoint=agent_data["endpoint"],
            capabilities=agent_data["capabilities"],
            agent_type=agent_data["agent_type"],
            is_active=agent_data.get("is_active", True),
            user_id=user_id
        )
        return agent.dict()
    except Exception as e:
        logger.error("Failed to register agent", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/agents/{agent_id}")
async def unregister_agent(agent_id: str, api_key: str = Depends(require_api_key)):
    """Unregister an agent"""
    try:
        success = registry.unregister_agent(agent_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return {"message": f"Agent '{agent_id}' unregistered successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to unregister agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Communication endpoints
@app.get("/messages/{execution_id}")
async def get_messages(execution_id: UUID, limit: int = 100, offset: int = 0, api_key: str = Depends(require_api_key)):
    """Get messages for an execution"""
    try:
        messages = await memory_store.get_messages(execution_id, limit, offset)
        return {
            "messages": messages,  # Ya son diccionarios
            "count": len(messages),
            "execution_id": str(execution_id)
        }
    except Exception as e:
        logger.error("Failed to get messages", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Monitoring endpoints
@app.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    try:
        metrics = await memory_store.get_metrics()
        return metrics.dict()
    except Exception as e:
        logger.error("Failed to get metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_system_status():
    """Get overall system status"""
    try:
        return {
            "status": "operational",
            "components": {
                "registry": "active",
                "communication": "active",
                "memory": "active",
                "orchestrator": "active"
            },
            "agents": {
                "total": len(registry.list_agents()),
                "active": len(registry.list_active_agents())
            },
            "flows": {
                "total": len(orchestrator.list_flows())
            }
        }
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

# Authentication endpoints
@app.get("/auth/status")
async def auth_status():
    """Get authentication status"""
    return {
        "api_key_required": auth_manager.api_key_required,
        "master_key_hint": auth_manager.master_api_key[:8] + "..." if auth_manager.api_key_required else None
    }

@app.post("/auth/generate-key")
async def generate_api_key(api_key: str = Depends(require_api_key)):
    """Generate a new API key (requires existing valid key)"""
    import secrets
    new_key = "ai-spine-" + secrets.token_urlsafe(32)
    auth_manager.add_api_key(new_key)
    return {
        "api_key": new_key,
        "message": "New API key generated successfully"
    }

@app.post("/auth/revoke-key")
async def revoke_api_key(key_to_revoke: str, api_key: str = Depends(require_api_key)):
    """Revoke an API key (requires existing valid key)"""
    if key_to_revoke == auth_manager.master_api_key:
        raise HTTPException(status_code=400, detail="Cannot revoke master API key")
    
    auth_manager.remove_api_key(key_to_revoke)
    return {
        "message": "API key revoked successfully"
    }

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "AI Spine API",
        "version": "1.0.0",
        "docs": "/docs",
        "marketplace": "/api/v1/marketplace",
        "authentication_required": auth_manager.api_key_required
    } 

@app.get("/openapi.yaml", response_class=PlainTextResponse, include_in_schema=False)
def get_openapi_yaml():
    return OPENAPI_PATH.read_text(encoding="utf-8")
