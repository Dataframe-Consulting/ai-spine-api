import asyncio
import httpx
import structlog
from typing import Dict, List, Optional, Set
from .models import AgentInfo, AgentCapability, AgentType
from datetime import datetime

logger = structlog.get_logger(__name__)


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._capability_index: Dict[AgentCapability, Set[str]] = {}
        self._health_check_interval = 30  # seconds
        self._health_check_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the registry and health check loop"""
        logger.info("Starting Agent Registry")
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Agent Registry started")

    async def stop(self):
        """Stop the registry and health check loop"""
        logger.info("Stopping Agent Registry")
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Agent Registry stopped")

    def register_agent(
        self,
        agent_id: str,
        name: str,
        description: str,
        endpoint: str,
        capabilities: List[AgentCapability],
        agent_type: AgentType,
        is_active: bool = True
    ) -> AgentInfo:
        """Register a new agent"""
        agent_info = AgentInfo(
            agent_id=agent_id,
            name=name,
            description=description,
            endpoint=endpoint,
            capabilities=capabilities,
            agent_type=agent_type,
            is_active=is_active
        )
        
        self._agents[agent_id] = agent_info
        
        # Update capability index
        for capability in capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(agent_id)
        
        logger.info("Agent registered", agent_id=agent_id, name=name, capabilities=capabilities)
        return agent_info

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id not in self._agents:
            return False
        
        agent_info = self._agents[agent_id]
        
        # Remove from capability index
        for capability in agent_info.capabilities:
            if capability in self._capability_index:
                self._capability_index[capability].discard(agent_id)
                if not self._capability_index[capability]:
                    del self._capability_index[capability]
        
        del self._agents[agent_id]
        logger.info("Agent unregistered", agent_id=agent_id)
        return True

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent by ID"""
        return self._agents.get(agent_id)

    def get_agents_by_capability(self, capability: AgentCapability) -> List[AgentInfo]:
        """Get all agents with a specific capability"""
        agent_ids = self._capability_index.get(capability, set())
        return [self._agents[agent_id] for agent_id in agent_ids if agent_id in self._agents]

    def get_agents_by_type(self, agent_type: AgentType) -> List[AgentInfo]:
        """Get all agents of a specific type"""
        return [agent for agent in self._agents.values() if agent.agent_type == agent_type]

    def list_agents(self) -> List[AgentInfo]:
        """List all registered agents"""
        return list(self._agents.values())

    def list_active_agents(self) -> List[AgentInfo]:
        """List all active agents"""
        return [agent for agent in self._agents.values() if agent.is_active]

    async def health_check_agent(self, agent_id: str) -> bool:
        """Check if an agent is healthy"""
        agent = self.get_agent(agent_id)
        if not agent or not agent.is_active:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{agent.endpoint}/health")
                is_healthy = response.status_code == 200
                
                if is_healthy:
                    agent.last_health_check = datetime.utcnow()
                
                logger.debug("Health check completed", agent_id=agent_id, healthy=is_healthy)
                return is_healthy
        except Exception as e:
            logger.warning("Health check failed", agent_id=agent_id, error=str(e))
            return False

    async def _health_check_loop(self):
        """Background health check loop"""
        while True:
            try:
                for agent_id in list(self._agents.keys()):
                    await self.health_check_agent(agent_id)
                
                await asyncio.sleep(self._health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in health check loop", error=str(e))
                await asyncio.sleep(self._health_check_interval)


# Global registry instance
registry = AgentRegistry() 