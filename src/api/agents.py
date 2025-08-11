from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import structlog

from src.core.registry import registry
from src.core.models import AgentInfo

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("", response_model=Dict[str, Any])
async def list_agents():
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

@router.get("/active", response_model=Dict[str, Any])
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

@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """Get a specific agent"""
    try:
        agent = registry.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get agent", agent_id=agent_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=AgentInfo)
async def register_agent(agent_data: Dict[str, Any]):
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
        return agent
    except Exception as e:
        logger.error("Failed to register agent", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{agent_id}")
async def unregister_agent(agent_id: str):
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