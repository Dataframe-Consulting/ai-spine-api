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
from src.api.tool_generation import router as tool_generation_router
# Direct import of tool generation dependencies to bypass router import issues
import anthropic
import re
import json
from typing import List, Dict, Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field
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

logger.info("MAIN.PY LOADING STARTED - THIS IS THE DEBUG MESSAGE")

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
# Comment out the static schema override to let FastAPI auto-generate from routes
# app.openapi_schema = OPENAPI_YAML


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
logger.info("Including routers...")
app.include_router(agents_router, prefix="/api/v1")
logger.info("Agents router included")
app.include_router(tools_router, prefix="/api/v1")
logger.info("Tools router included")
try:
    app.include_router(tool_generation_router, prefix="/api/v1")  # AI tool generation
    logger.info("Tool generation router included successfully", routes_count=len(tool_generation_router.routes))
except Exception as e:
    logger.error("Failed to include tool generation router", error=str(e))
app.include_router(flows_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(user_keys_router, prefix="/api/v1")  # Legacy endpoints (will deprecate)
app.include_router(user_account_router, prefix="/api/v1")  # New secure endpoints with JWT
logger.info("All routers included")

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
        # Mark startup as complete
        global _startup_complete
        _startup_complete = True
    except Exception as e:
        logger.error("Failed to start AI Spine infrastructure", error=str(e), error_type=type(e).__name__)
        # Don't raise - let the app start even if some components fail
        # This allows health check to respond even if there are startup issues
        logger.warning("Continuing startup despite component failures")

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

# Global startup status
_startup_complete = False

# Health check endpoint - optimized for Railway deployment
@app.get("/health")
async def health_check():
    """Fast health check endpoint for Railway deployment"""
    import time

    # Return immediately - Railway just needs to know the server is responding
    # Don't wait for startup to complete
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "message": "AI Spine API is running",
        "startup_complete": _startup_complete
    }

# Detailed health check endpoint for monitoring
@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check endpoint with database verification"""
    import time

    logger.info("Detailed health check endpoint called")

    try:
        # Test basic app readiness
        logger.debug("App is responding")

        # Quick database check if in production
        import os
        dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

        db_status = "skipped"
        if not dev_mode:
            try:
                from src.core.supabase_client import get_supabase_db
                db = get_supabase_db()
                # Quick test query
                result = db.client.table("api_users").select("count", count="exact").limit(1).execute()
                logger.debug("Database connection OK")
                db_status = "connected"
            except Exception as db_e:
                logger.warning("Database check failed", error=str(db_e))
                db_status = "failed"

        logger.info("Detailed health check successful")
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "database": db_status,
            "mode": "development" if dev_mode else "production"
        }

    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
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

# AI Tool Generation endpoints - added directly to bypass import issues
class ToolGenerationRequest(BaseModel):
    prompt: str = Field(..., description="User prompt describing the tool to generate")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list)

class ToolGenerationResponse(BaseModel):
    success: bool
    tool_config: Optional[Dict[str, Any]] = None
    generated_code: Optional[str] = None
    error: Optional[str] = None
    conversation_id: Optional[str] = None

LANGGRAPH_TOOL_TEMPLATE = """
You are an expert at creating LangGraph-compatible tools. Create a tool based on the user's requirements.

IMPORTANT: The tool must be compatible with LangGraph using the `tool` function from "@langchain/core/tools".

Here's the template structure you must follow:

```typescript
import { tool } from "@langchain/core/tools";
import { z } from "zod";

export const {tool_name} = tool(
  async (input: {InputType}) => {
    // Tool implementation here
    // Return the result as a string or object
    return "Tool execution result";
  },
  {
    name: "{tool_name}",
    description: "{tool_description}",
    schema: z.object({
      // Define input schema here using Zod
      // Example: text: z.string().describe("Input text to process")
    })
  }
);
```

{conversation_context}

User Request: {user_prompt}

Please create a complete LangGraph-compatible tool based on this request. Your response should include:

1. The complete TypeScript code with proper imports
2. A clear description of what the tool does
3. Proper input/output schema using Zod validation
4. Any necessary error handling

Make sure the tool follows the exact structure shown above and is ready to use with LangGraph.
"""

def get_anthropic_client() -> anthropic.Anthropic:
    """Get configured Anthropic client"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    return anthropic.Anthropic(api_key=api_key)

def parse_generated_tool(response_text: str) -> Dict[str, Any]:
    """Parse Claude's response to extract tool configuration and code"""
    try:
        logger.info("Parsing generated tool response", response_length=len(response_text))

        # Extract TypeScript code from markdown code blocks
        code_match = re.search(r'```(?:typescript|ts|javascript|js)?\\n(.*?)\\n```', response_text, re.DOTALL)
        if not code_match:
            raise ValueError("No code block found in response")

        generated_code = code_match.group(1).strip()

        # Extract tool name from export statement
        name_match = re.search(r'export const (\\w+) = tool', generated_code)
        tool_name = name_match.group(1) if name_match else "generatedTool"

        # Extract description from tool definition
        desc_match = re.search(r'description:\\s*["\\'']([^"\\'']+)["\\'']', generated_code)
        description = desc_match.group(1) if desc_match else "AI generated tool"

        # Extract schema definition (simplified)
        schema_match = re.search(r'schema:\\s*z\\.object\\(\\{([^}]+)\\}\\)', generated_code, re.DOTALL)
        input_schema = {}

        if schema_match:
            schema_content = schema_match.group(1)
            # Parse field definitions (simplified)
            field_matches = re.findall(r'(\\w+):\\s*z\\.(\\w+)\\([^)]*\\)(?:\\.describe\\(["\\'']([^"\\'']+)["\\'']\\))?', schema_content)

            for field_name, field_type, field_desc in field_matches:
                input_schema[field_name] = {
                    "type": field_type,
                    "description": field_desc or f"{field_name} parameter"
                }

        tool_config = {
            "name": tool_name,
            "description": description,
            "input_schema": input_schema,
            "output_format": "string or object"
        }

        logger.info("Tool parsing successful", tool_name=tool_name, schema_fields=len(input_schema))

        return {
            "tool_config": tool_config,
            "generated_code": generated_code,
            "summary": f"Generated {tool_name}: {description}"
        }

    except Exception as e:
        logger.error("Failed to parse generated tool", error=str(e))
        raise ValueError(f"Failed to parse generated tool: {str(e)}")

@app.get("/api/v1/ai-tools/test")
async def test_ai_tools_endpoint():
    """Simple test endpoint to verify AI tools router is working"""
    return {"message": "AI Tools router works!", "status": "success"}

@app.post("/api/v1/ai-tools/generate")
async def generate_tool_with_claude(
    request: ToolGenerationRequest,
    api_key: str = Depends(optional_api_key)
):
    """Generate a LangGraph-compatible tool using Claude API"""
    try:
        logger.info("Generating tool with Claude", api_key=api_key[:8] + "..." if api_key else "none", prompt_length=len(request.prompt))

        # Get Anthropic client
        client = get_anthropic_client()

        # Build conversation context
        conversation_context = ""
        if request.conversation_history:
            conversation_context = "Previous conversation:\\n"
            for msg in request.conversation_history[-5:]:  # Last 5 messages
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_context += f"{role}: {content}\\n"
            conversation_context += "\\nContinue the conversation and improve/modify the tool based on the new request.\\n"

        # Prepare the prompt
        full_prompt = LANGGRAPH_TOOL_TEMPLATE.format(
            user_prompt=request.prompt,
            conversation_context=conversation_context,
            tool_name="generatedTool",
            tool_description="AI generated tool",
        )

        logger.info("Calling Claude API", prompt_length=len(full_prompt))

        # Call Claude API
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            messages=[{"role": "user", "content": full_prompt}]
        )

        response_text = response.content[0].text
        logger.info("Claude API responded", response_length=len(response_text))

        # Parse the response
        conversation_id = f"conv_{uuid4().hex[:8]}"
        parsed_result = parse_generated_tool(response_text)

        logger.info("Tool generation successful", conversation_id=conversation_id)

        return ToolGenerationResponse(
            success=True,
            tool_config=parsed_result["tool_config"],
            generated_code=parsed_result["generated_code"],
            conversation_id=conversation_id
        )

    except Exception as e:
        logger.error("Tool generation failed", error=str(e), api_key=api_key[:8] + "..." if api_key else "none")
        return ToolGenerationResponse(
            success=False,
            error=str(e)
        )

# Simple AI Tool Generator endpoint (direct implementation)
@app.post("/tool-builder")
async def simple_tool_builder(request: dict):
    """Simple AI tool generator - bypass all routing issues"""
    try:
        import os
        import anthropic
        import re
        from uuid import uuid4

        # Get user prompt
        user_prompt = request.get("prompt", "")
        if not user_prompt:
            return {"success": False, "error": "Prompt is required"}

        # Get API key from environment
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"success": False, "error": "ANTHROPIC_API_KEY not found"}

        # Initialize Claude client
        client = anthropic.Anthropic(api_key=api_key)

        # Simple LangGraph tool template
        template = f"""
Create a LangGraph-compatible tool based on this request: "{user_prompt}"

Use this exact template structure:

```typescript
import {{ tool }} from "@langchain/core/tools";
import {{ z }} from "zod";

export const myTool = tool(
  async (input) => {{
    // Tool implementation here
    // Add your code logic based on the user request
    return "Tool execution result";
  }},
  {{
    name: "myTool",
    description: "Description of what this tool does",
    schema: z.object({{
      // Define input parameters here using Zod
      text: z.string().describe("Input text parameter")
    }})
  }}
);
```

Generate a complete, working tool that implements the user's request.
"""

        # Call Claude API
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2000,
            messages=[{"role": "user", "content": template}]
        )

        response_text = response.content[0].text

        # Extract code from response
        code_match = re.search(r'```(?:typescript|ts|javascript|js)?\\n(.*?)\\n```', response_text, re.DOTALL)
        generated_code = code_match.group(1).strip() if code_match else response_text

        # Extract tool name
        name_match = re.search(r'export const (\\w+) = tool', generated_code)
        tool_name = name_match.group(1) if name_match else "generatedTool"

        # Extract description
        desc_match = re.search(r'description:\\s*"(.*?)"', generated_code)
        description = desc_match.group(1) if desc_match else "AI generated tool"

        return {
            "success": True,
            "tool_config": {
                "name": tool_name,
                "description": description,
                "input_schema": {"text": {"type": "string", "description": "Input parameter"}},
                "output_format": "string"
            },
            "generated_code": generated_code,
            "conversation_id": str(uuid4())
        }

    except Exception as e:
        return {"success": False, "error": str(e)}
