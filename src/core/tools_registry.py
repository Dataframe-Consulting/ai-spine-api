import asyncio
import httpx
import structlog
from typing import Dict, List, Optional, Set
from .models import ToolInfo, ToolType
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
        """Start the tools registry and health check loop"""
        logger.info("Starting Tools Registry")
        # Load tools from database on startup
        await self._load_tools_from_db()
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Tools Registry started")

    async def _load_tools_from_db(self):
        """Load tools from database on startup"""
        try:
            from .supabase_client import get_supabase_db

            db = get_supabase_db()
            result = db.client.table("tools")\
                .select("*")\
                .eq("is_active", True)\
                .execute()

            tools_data = result.data if result.data else []

            for tool_data in tools_data:
                try:
                    # Handle datetime conversion
                    if isinstance(tool_data.get("created_at"), str):
                        tool_data["created_at"] = datetime.fromisoformat(tool_data["created_at"].replace("Z", "+00:00"))
                    if isinstance(tool_data.get("updated_at"), str):
                        tool_data["updated_at"] = datetime.fromisoformat(tool_data["updated_at"].replace("Z", "+00:00"))

                    # Convert tool_type strings to ToolType enums
                    tool_types = []
                    for t in tool_data.get("tool_type", []):
                        try:
                            tool_types.append(ToolType(t))
                        except ValueError:
                            tool_types.append(ToolType.CUSTOM)

                    tool_data["tool_type"] = tool_types

                    tool_info = ToolInfo(**tool_data)

                    self._tools[tool_info.tool_id] = tool_info

                    # Update capability index
                    for capability in tool_info.capabilities:
                        if capability not in self._capability_index:
                            self._capability_index[capability] = set()
                        self._capability_index[capability].add(tool_info.tool_id)

                    # Update type index
                    for tool_type in tool_info.tool_type:
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
        """Stop the tools registry and health check loop"""
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
        custom_fields: List[dict],
        is_active: bool = True,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> ToolInfo:
        """Register a new tool and persist to database"""
        tool_info = ToolInfo(
            tool_id=tool_id,
            name=name,
            description=description,
            endpoint=endpoint,
            capabilities=capabilities,
            tool_type=tool_type,
            custom_fields=custom_fields,
            is_active=is_active,
            metadata=metadata or {},
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

        logger.info("Tool registered", tool_id=tool_id, name=name, capabilities=capabilities)
        return tool_info

    async def update_tool(
        self,
        tool_id: str,
        **updates
    ) -> Optional[ToolInfo]:
        """Update an existing tool"""
        if tool_id not in self._tools:
            return None

        old_tool = self._tools[tool_id]

        # Remove from indexes
        for capability in old_tool.capabilities:
            if capability in self._capability_index:
                self._capability_index[capability].discard(tool_id)

        for tool_type in old_tool.tool_type:
            if tool_type in self._type_index:
                self._type_index[tool_type].discard(tool_id)

        # Update tool data
        tool_data = old_tool.dict()
        tool_data.update(updates)
        tool_data["updated_at"] = datetime.utcnow()

        updated_tool = ToolInfo(**tool_data)
        self._tools[tool_id] = updated_tool

        # Re-add to indexes
        for capability in updated_tool.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(tool_id)

        for tool_type in updated_tool.tool_type:
            if tool_type not in self._type_index:
                self._type_index[tool_type] = set()
            self._type_index[tool_type].add(tool_id)

        logger.info("Tool updated", tool_id=tool_id)
        return updated_tool

    def unregister_tool(self, tool_id: str) -> bool:
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
        for tool_type in tool_info.tool_type:
            if tool_type in self._type_index:
                self._type_index[tool_type].discard(tool_id)
                if not self._type_index[tool_type]:
                    del self._type_index[tool_type]

        del self._tools[tool_id]
        logger.info("Tool unregistered", tool_id=tool_id)
        return True

    def get_tool(self, tool_id: str) -> Optional[ToolInfo]:
        """Get tool by ID"""
        return self._tools.get(tool_id)

    def get_tools_by_capability(self, capability: str) -> List[ToolInfo]:
        """Get all tools with a specific capability"""
        tool_ids = self._capability_index.get(capability, set())
        return [self._tools[tool_id] for tool_id in tool_ids if tool_id in self._tools]

    def get_tools_by_type(self, tool_type: ToolType) -> List[ToolInfo]:
        """Get all tools of a specific type"""
        tool_ids = self._type_index.get(tool_type, set())
        return [self._tools[tool_id] for tool_id in tool_ids if tool_id in self._tools]

    def list_tools(self) -> List[ToolInfo]:
        """List all registered tools"""
        return list(self._tools.values())

    def list_active_tools(self) -> List[ToolInfo]:
        """List all active tools"""
        return [tool for tool in self._tools.values() if tool.is_active]

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

    async def health_check_tool(self, tool_id: str) -> bool:
        """Check if a tool is healthy"""
        tool = self.get_tool(tool_id)
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
                logger.error("Error in tools health check loop", error=str(e))
                await asyncio.sleep(self._health_check_interval)


# Global tools registry instance
tools_registry = ToolsRegistry()