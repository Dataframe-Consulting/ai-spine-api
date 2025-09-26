from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional, List
import structlog
from datetime import datetime
import uuid

from src.core.supabase_client import get_supabase_db
from src.core.encryption import encryption_service
from src.core.supabase_auth import optional_supabase_token, verify_supabase_token

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

@router.get("", response_model=Dict[str, Any])
async def get_agents(user_id: Optional[str] = Depends(optional_supabase_token)):
    """Get all agents - system agents for anonymous users, system + user agents for authenticated users"""
    try:
        db = get_supabase_db()

        # Build query based on authentication status
        if user_id:
            # Authenticated user: show system agents (created_by is null) + their own agents
            agents_result = db.client.table("agents").select(
                "id, agent_id, name, description, agent_type, model, system_prompt, "
                "temperature, max_tokens, max_turns, timeout_seconds, enable_memory, "
                "is_active, status, created_by, created_at, updated_at"
            ).or_(f"created_by.is.null,created_by.eq.{user_id}").execute()
        else:
            # Anonymous user: only show system agents (created_by is null)
            agents_result = db.client.table("agents").select(
                "id, agent_id, name, description, agent_type, model, system_prompt, "
                "temperature, max_tokens, max_turns, timeout_seconds, enable_memory, "
                "is_active, status, created_by, created_at, updated_at"
            ).is_("created_by", None).execute()

        agents = agents_result.data or []

        # Get tool associations for all agents
        agent_ids = [agent["id"] for agent in agents]
        tools_data = {}

        if agent_ids:
            # Get agent-tool relationships
            tools_result = db.client.table("agent_tools").select(
                "agent_id, tool_id"
            ).in_("agent_id", agent_ids).execute()

            # Group tools by agent_id
            for tool_rel in tools_result.data or []:
                agent_id = tool_rel["agent_id"]
                if agent_id not in tools_data:
                    tools_data[agent_id] = []
                tools_data[agent_id].append(tool_rel["tool_id"])

        # Format response
        formatted_agents = []
        for agent in agents:
            agent_tools = tools_data.get(agent["id"], [])

            formatted_agent = {
                "id": agent["id"],
                "agent_id": agent["agent_id"],
                "name": agent["name"],
                "description": agent["description"],
                "agent_type": agent["agent_type"],
                "model": agent["model"],
                "system_prompt": agent["system_prompt"],
                "temperature": agent["temperature"],
                "max_tokens": agent["max_tokens"],
                "max_turns": agent["max_turns"],
                "timeout_seconds": agent["timeout_seconds"],
                "enable_memory": agent["enable_memory"],
                "is_active": agent["is_active"],
                "status": agent["status"],
                "created_by": agent["created_by"],
                "created_at": agent["created_at"],
                "updated_at": agent["updated_at"],
                "available_tools": agent_tools,
                "tools_count": len(agent_tools),
                "is_system_agent": agent["created_by"] is None
            }
            formatted_agents.append(formatted_agent)

        logger.info("Agents retrieved successfully",
                   user_id=user_id,
                   total_count=len(formatted_agents),
                   authenticated=user_id is not None)

        return {
            "success": True,
            "agents": formatted_agents,
            "total_count": len(formatted_agents),
            "user_authenticated": user_id is not None
        }

    except Exception as e:
        logger.error("Failed to get agents", user_id=user_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")

@router.post("", response_model=Dict[str, Any])
async def create_agent(agent_data: Dict[str, Any], user_id: str = Depends(verify_supabase_token)):
    """Create a new agent with tools and configurations"""
    try:
        # Generate UUID for the agent
        agent_uuid = str(uuid.uuid4())

        # Prepare agent data for database insertion
        agent_db_data = {
            "id": agent_uuid,
            "agent_id": agent_data["agent_id"],
            "name": agent_data["name"],
            "description": agent_data["description"],
            "agent_type": agent_data["agent_type"],
            "model": agent_data["model"],
            "system_prompt": agent_data["system_prompt"],
            "temperature": agent_data["temperature"],
            "max_tokens": agent_data["max_tokens"],
            "max_turns": agent_data["max_turns"],
            "timeout_seconds": agent_data["timeout"],
            "enable_memory": agent_data["enable_memory"],
            "llm_api_key_encrypted": encryption_service.encrypt(agent_data["llm_api_key"]) if agent_data.get("llm_api_key") else None,
            "encryption_key_id": "default",
            "is_active": True,
            "status": "active",
            "created_by": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        db = get_supabase_db()

        # Insert agent into database
        agent_result = db.client.table("agents").insert(agent_db_data).execute()

        if not agent_result.data:
            raise HTTPException(status_code=500, detail="Failed to create agent")

        created_agent = agent_result.data[0]

        # Handle tool associations
        available_tools = agent_data.get("available_tools", [])
        if available_tools:
            # Insert agent-tool relationships
            agent_tools_data = []
            for tool_id in available_tools:
                agent_tools_data.append({
                    "agent_id": agent_db_data["id"],
                    "tool_id": tool_id,
                    "created_at": datetime.utcnow().isoformat()
                })

            if agent_tools_data:
                tools_result = db.client.table("agent_tools").insert(agent_tools_data).execute()
                if not tools_result.data:
                    logger.warning("Failed to create agent-tool relationships", agent_id=agent_db_data["id"])

            # Handle tool configurations
            tool_configurations = agent_data.get("tool_configurations", {})
            if tool_configurations:
                config_data = []
                for tool_id, configurations in tool_configurations.items():
                    for property_name, config in configurations.items():
                        config_entry = {
                            "agent_id": agent_db_data["id"],
                            "tool_id": tool_id,
                            "property_name": property_name,
                            "is_encrypted": config["is_encrypted"],
                            "created_at": datetime.utcnow().isoformat(),
                            "updated_at": datetime.utcnow().isoformat()
                        }

                        # Store value based on encryption flag
                        if config["is_encrypted"]:
                            config_entry["property_value_encrypted"] = encryption_service.encrypt(config["value"])
                            config_entry["property_value"] = None
                        else:
                            config_entry["property_value"] = config["value"]
                            config_entry["property_value_encrypted"] = None

                        config_data.append(config_entry)

                if config_data:
                    config_result = db.client.table("agent_tool_configurations").insert(config_data).execute()
                    if not config_result.data:
                        logger.warning("Failed to create tool configurations", agent_id=agent_db_data["id"])

        logger.info("Agent created successfully",
                   agent_id=agent_db_data["id"],
                   user_id=user_id,
                   tools_count=len(available_tools))

        return {
            "success": True,
            "message": "Agent created successfully",
            "agent": {
                "id": created_agent["id"],
                "agent_id": created_agent["agent_id"],
                "name": created_agent["name"],
                "description": created_agent["description"],
                "agent_type": created_agent["agent_type"],
                "model": created_agent["model"],
                "created_at": created_agent["created_at"],
                "tools_count": len(available_tools),
                "configs_count": sum(len(configs) for configs in tool_configurations.values()) if tool_configurations else 0
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create agent",
                    agent_id=agent_data.get('agent_id', 'unknown'),
                    error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")