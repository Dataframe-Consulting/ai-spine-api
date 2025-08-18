from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import structlog

from src.core.registry import registry
from src.core.models import AgentInfo
from src.core.auth import optional_api_key
from src.core.supabase_client import get_supabase_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("", response_model=Dict[str, Any])
async def list_agents(api_key: Optional[str] = Depends(optional_api_key)):
    """List agents (system agents for all, plus own agents if authenticated)"""
    try:
        # Get all agents from registry (in memory)
        all_agents = registry.list_agents()
        
        # If no authentication, return only system agents (those without created_by)
        if not api_key or api_key == "anonymous":
            # Get system agents from database (those without created_by)
            db = get_supabase_db()
            system_agents = db.client.table("agents")\
                .select("agent_id")\
                .is_("created_by", None)\
                .execute()
            
            system_agent_ids = {a['agent_id'] for a in system_agents.data} if system_agents.data else set()
            # system_agent_ids.update(['zoe', 'eddie'])  # Commented to prevent forced inclusion
            
            # Filter to only system agents
            filtered_agents = [a for a in all_agents if a.agent_id in system_agent_ids]
        else:
            # User is authenticated, get their user_id
            user_id = None
            if api_key.startswith("sk_"):
                db = get_supabase_db()
                result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]
            
            if user_id:
                # Get system agents and user's own agents
                db = get_supabase_db()
                user_agents = db.client.table("agents")\
                    .select("agent_id")\
                    .or_(f"created_by.eq.{user_id},created_by.is.null")\
                    .execute()
                
                allowed_agent_ids = {a['agent_id'] for a in user_agents.data} if user_agents.data else set()
                # allowed_agent_ids.update(['zoe', 'eddie'])  # Commented to prevent forced inclusion
                
                # Filter agents
                filtered_agents = [a for a in all_agents if a.agent_id in allowed_agent_ids]
            else:
                # Failed to get user_id, return all agents (no filter)
                filtered_agents = all_agents  # Changed to show all agents instead of forcing zoe/eddie
        
        return {
            "agents": [agent.dict() for agent in filtered_agents],
            "count": len(filtered_agents),
            "authenticated": api_key is not None and api_key != "anonymous"
        }
    except Exception as e:
        logger.error("Failed to list agents", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-agents", response_model=Dict[str, Any])
async def get_my_agents(api_key: str = Depends(optional_api_key)):
    """Get only the authenticated user's agents"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Get user_id from API key
        user_id = None
        if api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Get user's agents from database
        db = get_supabase_db()
        user_agents = db.client.table("agents")\
            .select("*")\
            .eq("created_by", user_id)\
            .execute()
        
        # Get from registry and filter
        all_agents = registry.list_agents()
        user_agent_ids = {a['agent_id'] for a in user_agents.data} if user_agents.data else set()
        filtered_agents = [a for a in all_agents if a.agent_id in user_agent_ids]
        
        return {
            "agents": [agent.dict() for agent in filtered_agents],
            "count": len(filtered_agents),
            "user_id": user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user agents", error=str(e))
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
        agent = await registry.register_agent(
            agent_id=agent_data["agent_id"],
            name=agent_data["name"],
            description=agent_data["description"],
            endpoint=agent_data["endpoint"],
            capabilities=agent_data["capabilities"],
            agent_type=agent_data["agent_type"],
            is_active=agent_data.get("is_active", True),
            user_id=None  # This endpoint doesn't have user context
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