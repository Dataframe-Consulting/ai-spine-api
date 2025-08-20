import asyncio
import httpx
import structlog
from typing import Dict, List, Optional, Set
from .models import ToolInfo, ToolType, CustomField, ToolUpdate
from datetime import datetime

logger = structlog.get_logger(__name__)


class ToolsRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolInfo] = {}
        self._capability_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[ToolType, Set[str]] = {}
        self._health_check_interval = 30  # seconds
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the registry and health check loop"""
        logger.info("Starting Tools Registry")
        # Load tools from database on startup
        await self._load_tools_from_db()
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Tools Registry started")

    async def _load_tools_from_db(self):
        """Load tools from database on startup"""
        try:
            from .memory import memory_store
            tools = await memory_store.get_tools(active_only=True)
            
            for tool_data in tools:
                try:
                    # Convert tool_type strings back to enums
                    tool_types = [ToolType(t) for t in tool_data.get("tool_type", [])]
                    
                    # Parse custom fields
                    custom_fields = []
                    for field_data in tool_data.get("custom_fields", []):
                        custom_fields.append(CustomField(**field_data))
                    
                    tool_info = ToolInfo(
                        tool_id=tool_data["tool_id"],
                        name=tool_data["name"],
                        description=tool_data.get("description", ""),
                        endpoint=tool_data["endpoint"],
                        capabilities=tool_data.get("capabilities", []),
                        tool_type=tool_types,
                        custom_fields=custom_fields,
                        is_active=tool_data.get("is_active", True),
                        created_by=tool_data.get("created_by")
                    )
                    
                    self._tools[tool_info.tool_id] = tool_info
                    
                    # Update capability index
                    for capability in tool_info.capabilities:
                        if capability not in self._capability_index:
                            self._capability_index[capability] = set()
                        self._capability_index[capability].add(tool_info.tool_id)
                    
                    # Update type index
                    for tool_type in tool_types:
                        if tool_type not in self._type_index:
                            self._type_index[tool_type] = set()
                        self._type_index[tool_type].add(tool_info.tool_id)
                    
                    logger.info("Tool loaded from database", tool_id=tool_info.tool_id)
                except Exception as e:
                    logger.error("Failed to load tool from database", tool_id=tool_data.get("tool_id"), error=str(e))
            
            logger.info("Loaded tools from database", count=len(self._tools))
        except Exception as e:
            logger.error("Failed to load tools from database", error=str(e))

    async def stop(self):
        """Stop the registry and health check loop"""
        logger.info("Stopping Tools Registry")
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Tools Registry stopped")

    async def register_tool(
        self,
        tool_id: str,
        name: str,
        description: str,
        endpoint: str,
        capabilities: List[str],
        tool_type: List[ToolType],
        custom_fields: List[CustomField] = None,
        is_active: bool = True,
        user_id: Optional[str] = None
    ) -> ToolInfo:
        """Register a new tool and persist to database"""
        if custom_fields is None:
            custom_fields = []
            
        tool_info = ToolInfo(
            tool_id=tool_id,
            name=name,
            description=description,
            endpoint=endpoint,
            capabilities=capabilities,
            tool_type=tool_type,
            custom_fields=custom_fields,
            is_active=is_active,
            created_by=user_id
        )
        
        self._tools[tool_id] = tool_info
        
        # Update capability index
        for capability in capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(tool_id)
        
        # Update type index
        for t_type in tool_type:
            if t_type not in self._type_index:
                self._type_index[t_type] = set()
            self._type_index[t_type].add(tool_id)
        
        # Save to database
        from .memory import memory_store
        
        tool_data = {
            "tool_id": tool_id,
            "name": name,
            "description": description,
            "endpoint": endpoint,
            "capabilities": capabilities,
            "tool_type": [str(t) for t in tool_type],
            "custom_fields": [field.dict() for field in custom_fields],
            "is_active": is_active,
            "created_by": user_id
        }
        
        # Debug logging
        logger.info("Registering tool with user_id", tool_id=tool_id, user_id=user_id)
        
        # Save to database - now we can await since register_tool is async
        await memory_store.register_tool(tool_data)
        
        logger.info("Tool registered", tool_id=tool_id, name=name, capabilities=capabilities)
        return tool_info

    async def update_tool(self, tool_id: str, tool_update: ToolUpdate, user_id: Optional[str] = None) -> Optional[ToolInfo]:
        """Update an existing tool"""
        if tool_id not in self._tools:
            return None
        
        tool_info = self._tools[tool_id]
        
        # Update fields if provided
        if tool_update.name is not None:
            tool_info.name = tool_update.name
        if tool_update.description is not None:
            tool_info.description = tool_update.description
        if tool_update.endpoint is not None:
            tool_info.endpoint = tool_update.endpoint
        if tool_update.capabilities is not None:
            # Remove old capabilities from index
            for capability in tool_info.capabilities:
                if capability in self._capability_index:
                    self._capability_index[capability].discard(tool_id)
                    if not self._capability_index[capability]:
                        del self._capability_index[capability]
            
            # Update capabilities and rebuild index
            tool_info.capabilities = tool_update.capabilities
            for capability in tool_update.capabilities:
                if capability not in self._capability_index:
                    self._capability_index[capability] = set()
                self._capability_index[capability].add(tool_id)
        
        if tool_update.tool_type is not None:
            # Remove old types from index
            for t_type in tool_info.tool_type:
                if t_type in self._type_index:
                    self._type_index[t_type].discard(tool_id)
                    if not self._type_index[t_type]:
                        del self._type_index[t_type]
            
            # Update types and rebuild index
            tool_info.tool_type = tool_update.tool_type
            for t_type in tool_update.tool_type:
                if t_type not in self._type_index:
                    self._type_index[t_type] = set()
                self._type_index[t_type].add(tool_id)
        
        if tool_update.custom_fields is not None:
            tool_info.custom_fields = tool_update.custom_fields
        if tool_update.is_active is not None:
            tool_info.is_active = tool_update.is_active
        
        tool_info.updated_at = datetime.utcnow()
        
        # Save to database
        from .memory import memory_store
        
        tool_data = {
            "tool_id": tool_id,
            "name": tool_info.name,
            "description": tool_info.description,
            "endpoint": tool_info.endpoint,
            "capabilities": tool_info.capabilities,
            "tool_type": [str(t) for t in tool_info.tool_type],
            "custom_fields": [field.dict() for field in tool_info.custom_fields],
            "is_active": tool_info.is_active,
            "created_by": tool_info.created_by
        }
        
        await memory_store.update_tool(tool_id, tool_data)
        
        logger.info("Tool updated", tool_id=tool_id)
        return tool_info

    async def unregister_tool(self, tool_id: str, user_id: Optional[str] = None) -> bool:
        """Unregister a tool"""
        if tool_id not in self._tools:
            return False
        
        tool_info = self._tools[tool_id]
        
        # Remove from capability index
        for capability in tool_info.capabilities:
            if capability in self._capability_index:
                self._capability_index[capability].discard(tool_id)
                if not self._capability_index[capability]:
                    del self._capability_index[capability]
        
        # Remove from type index
        for t_type in tool_info.tool_type:
            if t_type in self._type_index:
                self._type_index[t_type].discard(tool_id)
                if not self._type_index[t_type]:
                    del self._type_index[t_type]
        
        del self._tools[tool_id]
        
        # Remove from database
        from .memory import memory_store
        await memory_store.delete_tool(tool_id)
        
        logger.info("Tool unregistered", tool_id=tool_id)
        return True

    def get_tool(self, tool_id: str) -> Optional[ToolInfo]:
        """Get tool by ID"""
        return self._tools.get(tool_id)

    def find_tools_by_capability(self, capability: str) -> List[ToolInfo]:
        """Get all tools with a specific capability"""
        tool_ids = self._capability_index.get(capability, set())
        return [self._tools[tool_id] for tool_id in tool_ids if tool_id in self._tools]

    def find_tools_by_type(self, tool_type: str) -> List[ToolInfo]:
        """Get all tools of a specific type"""
        try:
            t_type = ToolType(tool_type)
            tool_ids = self._type_index.get(t_type, set())
            return [self._tools[tool_id] for tool_id in tool_ids if tool_id in self._tools]
        except ValueError:
            return []

    def search_tools(self, query: str) -> List[ToolInfo]:
        """Search tools by name, description, or capabilities"""
        query_lower = query.lower()
        results = []
        
        for tool in self._tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower() or
                any(query_lower in cap.lower() for cap in tool.capabilities)):
                results.append(tool)
        
        return results

    def list_tools(self) -> List[ToolInfo]:
        """List all registered tools"""
        return list(self._tools.values())

    def list_active_tools(self) -> List[ToolInfo]:
        """List all active tools"""
        return [tool for tool in self._tools.values() if tool.is_active]

    async def health_check_tool(self, tool_id: str) -> bool:
        """Check if a tool is healthy"""
        tool = self.get_tool(tool_id)
        if not tool or not tool.is_active:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{tool.endpoint}/health")
                is_healthy = response.status_code == 200
                
                logger.debug("Health check completed", tool_id=tool_id, healthy=is_healthy)
                return is_healthy
        except Exception as e:
            logger.warning("Health check failed", tool_id=tool_id, error=str(e))
            return False

    async def _health_check_loop(self):
        """Background health check loop"""
        while True:
            try:
                for tool_id in list(self._tools.keys()):
                    await self.health_check_tool(tool_id)
                
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in health check loop", error=str(e))
                await asyncio.sleep(self._health_check_interval)


# Global tools registry instance
tools_registry = ToolsRegistry()