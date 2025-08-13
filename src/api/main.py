import asyncio
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import structlog
from typing import List, Dict, Any, Optional
from uuid import UUID

from src.core.models import ExecutionRequest, ExecutionResponse, ExecutionContextResponse
from src.core.orchestrator import orchestrator
from src.core.registry import registry
from src.core.communication import communication_manager
from src.core.memory import memory_store
from src.core.auth import require_api_key, optional_api_key, auth_manager
from src.api.agents import router as agents_router
from src.api.flows import router as flows_router
from src.api.executions import router as executions_router
from src.api.marketplace_simple import router as marketplace_router
from src.api.users import router as users_router

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

# Create FastAPI app
app = FastAPI(
    title="AI Spine API",
    description="Multi-agent orchestration system",
    version="1.0.0"
)

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
app.include_router(flows_router, prefix="/api/v1")
app.include_router(executions_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Initialize all core components on startup"""
    logger.info("Starting AI Spine infrastructure")
    
    try:
        # Start core components
        await registry.start()
        await communication_manager.start()
        await memory_store.start()
        await orchestrator.start()
        
        # Register default agents
        await register_default_agents()
        
        # Log authentication status
        if auth_manager.api_key_required:
            logger.info("API authentication enabled", key=auth_manager.master_api_key[:8] + "...")
        else:
            logger.info("API authentication disabled - development mode")
        
        logger.info("AI Spine infrastructure started successfully")
    except Exception as e:
        logger.error("Failed to start AI Spine infrastructure", error=str(e))
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down AI Spine infrastructure")
    
    try:
        await orchestrator.stop()
        await memory_store.stop()
        await communication_manager.stop()
        await registry.stop()
        
        logger.info("AI Spine infrastructure stopped successfully")
    except Exception as e:
        logger.error("Error during shutdown", error=str(e))

async def register_default_agents():
    """Register default agents (Zoe and Eddie)"""
    try:
        # Register Zoe - Assistant Agent
        registry.register_agent(
            agent_id="zoe",
            name="Zoe Assistant",
            description="Asistente conversacional que recolecta información del usuario",
            endpoint="http://localhost:8001/zoe",
            capabilities=["conversation", "information_gathering"],
            agent_type="input"
        )
        
        # Register Eddie - Credit Analysis Agent
        registry.register_agent(
            agent_id="eddie",
            name="Eddie Credit Analyzer",
            description="Analizador de crédito que evalúa solicitudes de préstamo",
            endpoint="http://localhost:8002/eddie",
            capabilities=["credit_analysis", "risk_assessment"],
            agent_type="processor"
        )
        
        logger.info("Default agents registered")
    except Exception as e:
        logger.error("Failed to register default agents", error=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

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
async def register_agent(agent_data: Dict[str, Any], api_key: str = Depends(require_api_key)):
    """Register a new agent"""
    try:
        agent = registry.register_agent(
            agent_id=agent_data["agent_id"],
            name=agent_data["name"],
            description=agent_data["description"],
            endpoint=agent_data["endpoint"],
            capabilities=agent_data["capabilities"],
            agent_type=agent_data["agent_type"],
            is_active=agent_data.get("is_active", True)
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