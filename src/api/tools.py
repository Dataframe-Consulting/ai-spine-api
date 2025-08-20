from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import structlog
from datetime import datetime

from src.core.models import (
    ToolInfo, ToolRegistration, ToolUpdate, ToolResponse,
    ToolTestRequest, ToolTestResponse
)
from src.core.auth import optional_api_key
from src.core.supabase_client import get_supabase_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])

@router.get("", response_model=Dict[str, Any])
async def list_tools(api_key: Optional[str] = Depends(optional_api_key)):
    """List tools (system tools for all, plus own tools if authenticated)"""
    try:
        # Get all tools from database
        db = get_supabase_db()

        # If no authentication, return only system tools (those without created_by)
        if not api_key or api_key == "anonymous":
            system_tools = db.client.table("tools")\
                .select("*")\
                .is_("created_by", None)\
                .eq("is_active", True)\
                .execute()

            tools_data = system_tools.data if system_tools.data else []
        else:
            # User is authenticated, get their user_id
            user_id = None
            if api_key.startswith("sk_"):
                result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]

            if user_id:
                # Get system tools and user's own tools
                user_tools = db.client.table("tools")\
                    .select("*")\
                    .or_(f"created_by.eq.{user_id},created_by.is.null")\
                    .eq("is_active", True)\
                    .execute()

                tools_data = user_tools.data if user_tools.data else []
            else:
                # Failed to get user_id, return only system tools
                system_tools = db.client.table("tools")\
                    .select("*")\
                    .is_("created_by", None)\
                    .eq("is_active", True)\
                    .execute()

                tools_data = system_tools.data if system_tools.data else []

        # Convert to ToolInfo objects
        tools = []
        for tool_data in tools_data:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "authenticated": api_key is not None and api_key != "anonymous"
        }
    except Exception as e:
        logger.error("Failed to list tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-tools", response_model=Dict[str, Any])
async def get_my_tools(api_key: str = Depends(optional_api_key)):
    """Get only the authenticated user's tools"""
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

        # Get user's tools from database
        db = get_supabase_db()
        user_tools = db.client.table("tools")\
            .select("*")\
            .eq("created_by", user_id)\
            .execute()

        # Convert to ToolInfo objects
        tools = []
        for tool_data in user_tools.data if user_tools.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "user_id": user_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get user tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=Dict[str, Any])
async def list_active_tools():
    """List all active tools"""
    try:
        db = get_supabase_db()
        active_tools = db.client.table("tools")\
            .select("*")\
            .eq("is_active", True)\
            .execute()

        # Convert to ToolInfo objects
        tools = []
        for tool_data in active_tools.data if active_tools.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                tool = ToolInfo(**tool_data)
                tools.append(tool)
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue

        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools)
        }
    except Exception as e:
        logger.error("Failed to list active tools", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{tool_id}", response_model=ToolInfo)
async def get_tool(tool_id: str):
    """Get a specific tool"""
    try:
        db = get_supabase_db()
        result = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        tool_data = result.data[0]

        # Handle datetime conversion
        if isinstance(tool_data.get("created_at"), str):
            tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
        if isinstance(tool_data.get("updated_at"), str):
            tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

        return ToolInfo(**tool_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=ToolResponse)
async def register_tool(
    tool_data: ToolRegistration,
    api_key: str = Depends(optional_api_key)
):
    """Register a new tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to register tools")

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

        # Check if tool_id already exists
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("tool_id")\
            .eq("tool_id", tool_data.tool_id)\
            .execute()

        if existing.data and len(existing.data) > 0:
            raise HTTPException(status_code=400, detail=f"Tool '{tool_data.tool_id}' already exists")

        # Create new tool
        now = datetime.utcnow()
        new_tool = {
            "tool_id": tool_data.tool_id,
            "name": tool_data.name,
            "description": tool_data.description,
            "endpoint": tool_data.endpoint,
            "capabilities": tool_data.capabilities,
            "tool_type": [t.value for t in tool_data.tool_type],
            "custom_fields": [field.dict() for field in tool_data.custom_fields],
            "is_active": True,
            "metadata": tool_data.metadata,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "created_by": user_id
        }

        result = db.client.table("tools").insert(new_tool).execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to create tool")

        # Return the created tool
        created_tool_data = result.data[0]
        created_tool_data["created_at"] = now
        created_tool_data["updated_at"] = now

        tool = ToolInfo(**created_tool_data)

        return ToolResponse(
            success=True,
            tool=tool,
            message=f"Tool '{tool_data.tool_id}' registered successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to register tool", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: str,
    tool_update: ToolUpdate,
    api_key: str = Depends(optional_api_key)
):
    """Update a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to update tools")

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

        # Check if tool exists and user owns it
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        existing_tool = existing.data[0]

        # Check ownership (only owner can update, or system tools if user has admin)
        if existing_tool.get("created_by") and existing_tool["created_by"] != user_id:
            raise HTTPException(status_code=403, detail="You can only update your own tools")

        # Build update data
        update_data = {"updated_at": datetime.utcnow().isoformat()}

        if tool_update.name is not None:
            update_data["name"] = tool_update.name
        if tool_update.description is not None:
            update_data["description"] = tool_update.description
        if tool_update.endpoint is not None:
            update_data["endpoint"] = tool_update.endpoint
        if tool_update.capabilities is not None:
            update_data["capabilities"] = tool_update.capabilities
        if tool_update.tool_type is not None:
            update_data["tool_type"] = [t.value for t in tool_update.tool_type]
        if tool_update.custom_fields is not None:
            update_data["custom_fields"] = [field.dict() for field in tool_update.custom_fields]
        if tool_update.is_active is not None:
            update_data["is_active"] = tool_update.is_active
        if tool_update.metadata is not None:
            update_data["metadata"] = tool_update.metadata

        # Update tool
        result = db.client.table("tools")\
            .update(update_data)\
            .eq("tool_id", tool_id)\
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to update tool")

        # Return updated tool
        updated_tool_data = result.data[0]
        if isinstance(updated_tool_data.get("created_at"), str):
            updated_tool_data["created_at"] = datetime.fromisoformat(updated_tool_data["created_at"].replace("Z", "+00:00"))
        if isinstance(updated_tool_data.get("updated_at"), str):
            updated_tool_data["updated_at"] = datetime.fromisoformat(updated_tool_data["updated_at"].replace("Z", "+00:00"))

        tool = ToolInfo(**updated_tool_data)

        return ToolResponse(
            success=True,
            tool=tool,
            message=f"Tool '{tool_id}' updated successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{tool_id}", response_model=Dict[str, str])
async def delete_tool(
    tool_id: str,
    api_key: str = Depends(optional_api_key)
):
    """Delete a tool"""
    if not api_key or api_key == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required to delete tools")

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

        # Check if tool exists and user owns it
        db = get_supabase_db()
        existing = db.client.table("tools")\
            .select("*")\
            .eq("tool_id", tool_id)\
            .execute()

        if not existing.data or len(existing.data) == 0:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")

        existing_tool = existing.data[0]

        # Check ownership
        if existing_tool.get("created_by") and existing_tool["created_by"] != user_id:
            raise HTTPException(status_code=403, detail="You can only delete your own tools")

        # Delete tool
        result = db.client.table("tools")\
            .delete()\
            .eq("tool_id", tool_id)\
            .execute()

        return {"message": f"Tool '{tool_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test", response_model=ToolTestResponse)
async def test_tool_connection(test_request: ToolTestRequest):
    """Test connection to a tool endpoint"""
    try:
        import httpx
        from time import time

        start_time = time()

        async with httpx.AsyncClient(timeout=test_request.timeout) as client:
            try:
                # Try to hit the health endpoint
                response = await client.get(f"{test_request.endpoint}/health")
                response_time = int((time() - start_time) * 1000)

                if response.status_code == 200:
                    return ToolTestResponse(
                        success=True,
                        connected=True,
                        response_time_ms=response_time,
                        endpoint=test_request.endpoint
                    )
                else:
                    return ToolTestResponse(
                        success=False,
                        connected=False,
                        response_time_ms=response_time,
                        error=f"HTTP {response.status_code}",
                        endpoint=test_request.endpoint
                    )
            except httpx.TimeoutException:
                return ToolTestResponse(
                    success=False,
                    connected=False,
                    error="Connection timeout",
                    endpoint=test_request.endpoint
                )
            except Exception as e:
                return ToolTestResponse(
                    success=False,
                    connected=False,
                    error=str(e),
                    endpoint=test_request.endpoint
                )
    except Exception as e:
        logger.error("Failed to test tool connection", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))