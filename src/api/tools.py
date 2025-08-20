from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import structlog
import httpx
import asyncio
from datetime import datetime

from src.core.tools_registry import tools_registry
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
        # Get all tools from registry (in memory)
        all_tools = tools_registry.list_tools()
        
        # If no authentication, return only system tools (those without created_by)
        if not api_key or api_key == "anonymous":
            # Get system tools from database (those without created_by)
            db = get_supabase_db()
            system_tools = db.client.table("tools")\
                .select("tool_id")\
                .is_("created_by", None)\
                .execute()
            
            system_tool_ids = {t['tool_id'] for t in system_tools.data} if system_tools.data else set()
            
            # Filter to only system tools
            filtered_tools = [t for t in all_tools if t.tool_id in system_tool_ids]
        else:
            # User is authenticated, get their user_id
            user_id = None
            if api_key.startswith("sk_"):
                db = get_supabase_db()
                result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]
            
            if user_id:
                # Get system tools and user's own tools
                db = get_supabase_db()
                user_tools = db.client.table("tools")\
                    .select("tool_id")\
                    .or_(f"created_by.eq.{user_id},created_by.is.null")\
                    .execute()
                
                allowed_tool_ids = {t['tool_id'] for t in user_tools.data} if user_tools.data else set()
                
                # Filter tools
                filtered_tools = [t for t in all_tools if t.tool_id in allowed_tool_ids]
            else:
                # Failed to get user_id, return empty list
                filtered_tools = []
        
        return {
            "tools": [tool.dict() for tool in filtered_tools],
            "count": len(filtered_tools),
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
        
        # Get from registry and filter
        all_tools = tools_registry.list_tools()
        user_tool_ids = {t['tool_id'] for t in user_tools.data} if user_tools.data else set()
        filtered_tools = [t for t in all_tools if t.tool_id in user_tool_ids]
        
        return {
            "tools": [tool.dict() for tool in filtered_tools],
            "count": len(filtered_tools),
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
        tools = tools_registry.list_active_tools()
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
        tool = tools_registry.get_tool(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=ToolInfo)
async def register_tool(tool_data: ToolRegistration, api_key: Optional[str] = Depends(optional_api_key)):
    """Register a new tool"""
    try:
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        tool = await tools_registry.register_tool(
            tool_id=tool_data.tool_id,
            name=tool_data.name,
            description=tool_data.description,
            endpoint=tool_data.endpoint,
            capabilities=tool_data.capabilities,
            tool_type=tool_data.tool_type,
            custom_fields=tool_data.custom_fields,
            user_id=user_id
        )
        return tool
    except Exception as e:
        logger.error("Failed to register tool", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{tool_id}", response_model=ToolInfo)
async def update_tool(tool_id: str, tool_update: ToolUpdate, api_key: Optional[str] = Depends(optional_api_key)):
    """Update an existing tool"""
    try:
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        # Check if tool exists and user has permission
        existing_tool = tools_registry.get_tool(tool_id)
        if not existing_tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        # Check ownership if user is authenticated
        if user_id and existing_tool.created_by and existing_tool.created_by != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this tool")
        
        tool = await tools_registry.update_tool(tool_id, tool_update, user_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        return tool
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{tool_id}")
async def delete_tool(tool_id: str, api_key: Optional[str] = Depends(optional_api_key)):
    """Delete a tool"""
    try:
        # Get user_id if authenticated
        user_id = None
        if api_key and api_key != "anonymous" and api_key.startswith("sk_"):
            db = get_supabase_db()
            result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
            if result.data and len(result.data) > 0:
                user_id = result.data[0]["id"]
        
        # Check if tool exists and user has permission
        existing_tool = tools_registry.get_tool(tool_id)
        if not existing_tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        
        # Check ownership if user is authenticated
        if user_id and existing_tool.created_by and existing_tool.created_by != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this tool")
        
        success = await tools_registry.unregister_tool(tool_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
        return {"message": f"Tool '{tool_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete tool", tool_id=tool_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/test", response_model=ToolTestResponse)
async def test_tool_connection(test_request: ToolTestRequest):
    """Test tool connectivity"""
    try:
        start_time = asyncio.get_event_loop().time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{test_request.endpoint}/health")
                end_time = asyncio.get_event_loop().time()
                response_time_ms = int((end_time - start_time) * 1000)
                
                if response.status_code == 200:
                    return ToolTestResponse(
                        success=True,
                        message="Tool is responding",
                        response_time_ms=response_time_ms,
                        status_code=response.status_code
                    )
                else:
                    return ToolTestResponse(
                        success=False,
                        message=f"Tool returned status {response.status_code}",
                        response_time_ms=response_time_ms,
                        status_code=response.status_code
                    )
            except httpx.TimeoutException:
                return ToolTestResponse(
                    success=False,
                    message="Tool connection timeout"
                )
            except httpx.RequestError as e:
                return ToolTestResponse(
                    success=False,
                    message=f"Connection error: {str(e)}"
                )
    except Exception as e:
        logger.error("Failed to test tool connection", error=str(e))
        return ToolTestResponse(
            success=False,
            message=f"Test failed: {str(e)}"
        )

# Search and filtering endpoints
@router.get("/search/capabilities", response_model=Dict[str, Any])
async def search_tools_by_capability(capability: str, api_key: Optional[str] = Depends(optional_api_key)):
    """Search tools by capability"""
    try:
        tools = tools_registry.find_tools_by_capability(capability)
        
        # Apply same visibility filtering as list_tools
        if not api_key or api_key == "anonymous":
            db = get_supabase_db()
            system_tools = db.client.table("tools")\
                .select("tool_id")\
                .is_("created_by", None)\
                .execute()
            system_tool_ids = {t['tool_id'] for t in system_tools.data} if system_tools.data else set()
            tools = [t for t in tools if t.tool_id in system_tool_ids]
        else:
            user_id = None
            if api_key.startswith("sk_"):
                db = get_supabase_db()
                result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]
            
            if user_id:
                db = get_supabase_db()
                user_tools = db.client.table("tools")\
                    .select("tool_id")\
                    .or_(f"created_by.eq.{user_id},created_by.is.null")\
                    .execute()
                allowed_tool_ids = {t['tool_id'] for t in user_tools.data} if user_tools.data else set()
                tools = [t for t in tools if t.tool_id in allowed_tool_ids]
        
        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "capability": capability
        }
    except Exception as e:
        logger.error("Failed to search tools by capability", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search/type", response_model=Dict[str, Any])
async def search_tools_by_type(tool_type: str, api_key: Optional[str] = Depends(optional_api_key)):
    """Search tools by type"""
    try:
        tools = tools_registry.find_tools_by_type(tool_type)
        
        # Apply same visibility filtering as list_tools
        if not api_key or api_key == "anonymous":
            db = get_supabase_db()
            system_tools = db.client.table("tools")\
                .select("tool_id")\
                .is_("created_by", None)\
                .execute()
            system_tool_ids = {t['tool_id'] for t in system_tools.data} if system_tools.data else set()
            tools = [t for t in tools if t.tool_id in system_tool_ids]
        else:
            user_id = None
            if api_key.startswith("sk_"):
                db = get_supabase_db()
                result = db.client.table("api_users").select("id").eq("api_key", api_key).execute()
                if result.data and len(result.data) > 0:
                    user_id = result.data[0]["id"]
            
            if user_id:
                db = get_supabase_db()
                user_tools = db.client.table("tools")\
                    .select("tool_id")\
                    .or_(f"created_by.eq.{user_id},created_by.is.null")\
                    .execute()
                allowed_tool_ids = {t['tool_id'] for t in user_tools.data} if user_tools.data else set()
                tools = [t for t in tools if t.tool_id in allowed_tool_ids]
        
        return {
            "tools": [tool.dict() for tool in tools],
            "count": len(tools),
            "tool_type": tool_type
        }
    except Exception as e:
        logger.error("Failed to search tools by type", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))