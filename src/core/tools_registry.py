import httpx
import structlog
from typing import List, Optional
from .models import ToolInfo, ToolType
from datetime import datetime

logger = structlog.get_logger(__name__)


class ToolsRegistry:
    def __init__(self):
        pass

    async def start(self):
        """Start the tools registry"""
        logger.info("Starting Tools Registry")
        logger.info("Tools Registry started")


    async def stop(self):
        """Stop the tools registry"""
        logger.info("Stopping Tools Registry")
        logger.info("Tools Registry stopped")

    async def register_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        endpoint: str,
        capabilities: List[str],
        tool_type: List[ToolType],
        custom_fields: List[dict],
        is_active: bool = True,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> ToolInfo:
        """Register a new tool and persist to database"""
        from .supabase_client import get_supabase_db
        
        # Create tool data
        now = datetime.utcnow()
        tool_data = {
            "tool_id": tool_id,
            "name": name,
            "description": description,
            "endpoint": endpoint,
            "capabilities": capabilities,
            "tool_type": [t.value for t in tool_type],
            "custom_fields": custom_fields,
            "is_active": is_active,
            "metadata": metadata or {},
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "created_by": user_id
        }
        
        # Save to database
        db = get_supabase_db()
        result = db.client.table("tools").insert(tool_data).execute()
        
        if not result.data or len(result.data) == 0:
            raise Exception("Failed to register tool in database")
        
        # Create ToolInfo object from saved data
        saved_data = result.data[0]
        saved_data["created_at"] = now
        saved_data["updated_at"] = now
        saved_data["tool_type"] = tool_type  # Keep as enum list
        
        tool_info = ToolInfo(**saved_data)
        logger.info("Tool registered", tool_id=tool_id, name=name, capabilities=capabilities)
        return tool_info

    async def update_tool(
        self,
        tool_id: str,
        **updates
    ) -> Optional[ToolInfo]:
        """Update an existing tool"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        
        # Check if tool exists
        existing = db.client.table("tools").select("*").eq("tool_id", tool_id).execute()
        if not existing.data or len(existing.data) == 0:
            return None
        
        # Prepare update data
        update_data = {"updated_at": datetime.utcnow().isoformat()}
        update_data.update(updates)
        
        # Convert tool_type enums to strings if present
        if "tool_type" in update_data and update_data["tool_type"]:
            update_data["tool_type"] = [t.value if hasattr(t, 'value') else t for t in update_data["tool_type"]]
        
        # Update in database
        result = db.client.table("tools").update(update_data).eq("tool_id", tool_id).execute()
        
        if not result.data or len(result.data) == 0:
            return None
        
        # Convert back to ToolInfo
        updated_data = result.data[0]
        if isinstance(updated_data.get("created_at"), str):
            updated_data["created_at"] = datetime.fromisoformat(updated_data["created_at"].replace("Z", "+00:00"))
        if isinstance(updated_data.get("updated_at"), str):
            updated_data["updated_at"] = datetime.fromisoformat(updated_data["updated_at"].replace("Z", "+00:00"))
        
        # Convert tool_type strings back to enums
        if updated_data.get("tool_type"):
            tool_types = []
            for t in updated_data["tool_type"]:
                try:
                    tool_types.append(ToolType(t))
                except ValueError:
                    tool_types.append(ToolType.CUSTOM)
            updated_data["tool_type"] = tool_types
        
        updated_tool = ToolInfo(**updated_data)
        logger.info("Tool updated", tool_id=tool_id)
        return updated_tool

    async def unregister_tool(self, tool_id: str) -> bool:
        """Unregister a tool"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        
        # Check if tool exists
        existing = db.client.table("tools").select("tool_id").eq("tool_id", tool_id).execute()
        if not existing.data or len(existing.data) == 0:
            return False
        
        # Delete from database
        result = db.client.table("tools").delete().eq("tool_id", tool_id).execute()
        
        logger.info("Tool unregistered", tool_id=tool_id)
        return True

    async def get_tool(self, tool_id: str) -> Optional[ToolInfo]:
        """Get tool by ID"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        result = db.client.table("tools").select("*").eq("tool_id", tool_id).execute()
        
        if not result.data or len(result.data) == 0:
            return None
        
        tool_data = result.data[0]
        
        # Handle datetime conversion
        if isinstance(tool_data.get("created_at"), str):
            tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
        if isinstance(tool_data.get("updated_at"), str):
            tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
        
        # Convert tool_type strings to enums
        if tool_data.get("tool_type"):
            tool_types = []
            for t in tool_data["tool_type"]:
                try:
                    tool_types.append(ToolType(t))
                except ValueError:
                    tool_types.append(ToolType.CUSTOM)
            tool_data["tool_type"] = tool_types
        
        return ToolInfo(**tool_data)

    async def get_tools_by_capability(self, capability: str) -> List[ToolInfo]:
        """Get all tools with a specific capability"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        result = db.client.table("tools")\
            .select("*")\
            .contains("capabilities", [capability])\
            .eq("is_active", True)\
            .execute()
        
        tools = []
        for tool_data in result.data if result.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                
                # Convert tool_type strings to enums
                if tool_data.get("tool_type"):
                    tool_types = []
                    for t in tool_data["tool_type"]:
                        try:
                            tool_types.append(ToolType(t))
                        except ValueError:
                            tool_types.append(ToolType.CUSTOM)
                    tool_data["tool_type"] = tool_types
                
                tools.append(ToolInfo(**tool_data))
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue
        
        return tools

    async def get_tools_by_type(self, tool_type: ToolType) -> List[ToolInfo]:
        """Get all tools of a specific type"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        result = db.client.table("tools")\
            .select("*")\
            .contains("tool_type", [tool_type.value])\
            .eq("is_active", True)\
            .execute()
        
        tools = []
        for tool_data in result.data if result.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                
                # Convert tool_type strings to enums
                if tool_data.get("tool_type"):
                    tool_types = []
                    for t in tool_data["tool_type"]:
                        try:
                            tool_types.append(ToolType(t))
                        except ValueError:
                            tool_types.append(ToolType.CUSTOM)
                    tool_data["tool_type"] = tool_types
                
                tools.append(ToolInfo(**tool_data))
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue
        
        return tools

    async def list_tools(self) -> List[ToolInfo]:
        """List all registered tools"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        result = db.client.table("tools").select("*").execute()
        
        tools = []
        for tool_data in result.data if result.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                
                # Convert tool_type strings to enums
                if tool_data.get("tool_type"):
                    tool_types = []
                    for t in tool_data["tool_type"]:
                        try:
                            tool_types.append(ToolType(t))
                        except ValueError:
                            tool_types.append(ToolType.CUSTOM)
                    tool_data["tool_type"] = tool_types
                
                tools.append(ToolInfo(**tool_data))
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue
        
        return tools

    async def list_active_tools(self) -> List[ToolInfo]:
        """List all active tools"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        result = db.client.table("tools").select("*").eq("is_active", True).execute()
        
        tools = []
        for tool_data in result.data if result.data else []:
            try:
                # Handle datetime conversion
                if isinstance(tool_data.get("created_at"), str):
                    tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                if isinstance(tool_data.get("updated_at"), str):
                    tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                
                # Convert tool_type strings to enums
                if tool_data.get("tool_type"):
                    tool_types = []
                    for t in tool_data["tool_type"]:
                        try:
                            tool_types.append(ToolType(t))
                        except ValueError:
                            tool_types.append(ToolType.CUSTOM)
                    tool_data["tool_type"] = tool_types
                
                tools.append(ToolInfo(**tool_data))
            except Exception as e:
                logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                continue
        
        return tools

    async def search_tools(self, query: str) -> List[ToolInfo]:
        """Search tools by name, description, or capabilities"""
        from .supabase_client import get_supabase_db
        
        db = get_supabase_db()
        query_lower = query.lower()
        
        # Search by name or description using ilike
        result = db.client.table("tools")\
            .select("*")\
            .or_(f"name.ilike.%{query_lower}%,description.ilike.%{query_lower}%")\
            .eq("is_active", True)\
            .execute()
        
        # Also get all tools to search capabilities manually (Supabase doesn't have array text search)
        all_tools_result = db.client.table("tools")\
            .select("*")\
            .eq("is_active", True)\
            .execute()
        
        tools = set()  # Use set to avoid duplicates
        
        # Add tools matching name/description
        for tool_data in result.data if result.data else []:
            tools.add(tool_data["tool_id"])
        
        # Add tools matching capabilities
        for tool_data in all_tools_result.data if all_tools_result.data else []:
            capabilities = tool_data.get("capabilities", [])
            if any(query_lower in cap.lower() for cap in capabilities):
                tools.add(tool_data["tool_id"])
        
        # Convert to ToolInfo objects
        results = []
        for tool_data in all_tools_result.data if all_tools_result.data else []:
            if tool_data["tool_id"] in tools:
                try:
                    # Handle datetime conversion
                    if isinstance(tool_data.get("created_at"), str):
                        tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                    if isinstance(tool_data.get("updated_at"), str):
                        tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))
                    
                    # Convert tool_type strings to enums
                    if tool_data.get("tool_type"):
                        tool_types = []
                        for t in tool_data["tool_type"]:
                            try:
                                tool_types.append(ToolType(t))
                            except ValueError:
                                tool_types.append(ToolType.CUSTOM)
                        tool_data["tool_type"] = tool_types
                    
                    results.append(ToolInfo(**tool_data))
                except Exception as e:
                    logger.warning("Failed to parse tool data", tool_id=tool_data.get("tool_id"), error=str(e))
                    continue
        
        return results

    async def health_check_tool(self, tool_id: str) -> bool:
        """Check if a tool is healthy"""
        tool = await self.get_tool(tool_id)
        if not tool or not tool.is_active:
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{tool.endpoint}/health")
                is_healthy = response.status_code == 200

                logger.debug("Tool health check completed", tool_id=tool_id, healthy=is_healthy)
                return is_healthy
        except Exception as e:
            logger.warning("Tool health check failed", tool_id=tool_id, error=str(e))
            return False



# Global tools registry instance
tools_registry = ToolsRegistry()