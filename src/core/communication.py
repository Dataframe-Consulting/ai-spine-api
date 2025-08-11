import asyncio
import json
import redis.asyncio as redis
from celery import Celery
import structlog
from typing import Dict, List, Optional, Any
from uuid import UUID
import os
from .models import AgentMessage, ExecutionContext

logger = structlog.get_logger(__name__)

# Create Celery app outside the class to avoid decorator issues
celery_app = Celery(
    "ai_spine_tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task
def process_message(message_data: Dict[str, Any]):
    """Celery task for processing messages asynchronously"""
    try:
        message = AgentMessage(**message_data)
        logger.info("Processing async message", message_id=str(message.message_id))
        
        # Here you would implement the actual message processing logic
        # For now, we just log the message
        
        return {"status": "processed", "message_id": str(message.message_id)}
    except Exception as e:
        logger.error("Failed to process message", error=str(e))
        return {"status": "failed", "error": str(e)}


class CommunicationManager:
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        celery_broker: str = "redis://localhost:6379/0",
        celery_backend: str = "redis://localhost:6379/0"
    ):
        self.redis_url = redis_url
        self.celery_broker = celery_broker
        self.celery_backend = celery_backend
        self.redis_client: Optional[redis.Redis] = None
        self.dev_mode = os.getenv("DEV_MODE", "false").lower() == "true"
        
        # In-memory message storage for development mode
        self._messages: Dict[str, AgentMessage] = {}
        self._message_queues: Dict[str, List[AgentMessage]] = {}

    async def start(self):
        """Start the communication manager"""
        logger.info("Starting Communication Manager")
        
        if self.dev_mode:
            logger.info("Running in development mode - using in-memory messaging")
            return
        
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            logger.info("Communication Manager started with Redis")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}")
            logger.info("Falling back to development mode")
            self.dev_mode = True

    async def stop(self):
        """Stop the communication manager"""
        logger.info("Stopping Communication Manager")
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Communication Manager stopped")

    async def send_message(self, message: AgentMessage, use_async: bool = False) -> bool:
        """Send a message to an agent"""
        try:
            if self.dev_mode:
                # Store message in memory
                self._messages[str(message.message_id)] = message
                
                # Add to recipient's queue
                recipient = message.to_agent or "broadcast"
                if recipient not in self._message_queues:
                    self._message_queues[recipient] = []
                self._message_queues[recipient].append(message)
                
                logger.info("Message sent via in-memory queue", 
                          message_id=str(message.message_id), 
                          recipient=recipient)
                return True
            
            if use_async:
                # Use Celery for async processing
                task = process_message.delay(message.dict())
                logger.info("Message queued for async processing", message_id=str(message.message_id))
                return True
            else:
                # Use Redis Pub/Sub for sync communication
                channel = f"agent:{message.to_agent}" if message.to_agent else "broadcast"
                await self.redis_client.publish(channel, message.json())
                await self._store_message(message)
                logger.info("Message sent via Redis", message_id=str(message.message_id), channel=channel)
                return True
        except Exception as e:
            logger.error("Failed to send message", message_id=str(message.message_id), error=str(e))
            return False

    async def receive_message(self, agent_id: str, timeout: float = 5.0) -> Optional[AgentMessage]:
        """Receive a message for a specific agent"""
        try:
            if self.dev_mode:
                # Get message from in-memory queue
                queue_key = f"agent:{agent_id}"
                if queue_key in self._message_queues and self._message_queues[queue_key]:
                    return self._message_queues[queue_key].pop(0)
                
                # Also check broadcast messages
                if "broadcast" in self._message_queues and self._message_queues["broadcast"]:
                    return self._message_queues["broadcast"].pop(0)
                
                return None
            
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(f"agent:{agent_id}")
            
            message = await pubsub.get_message(timeout=timeout)
            await pubsub.unsubscribe(f"agent:{agent_id}")
            await pubsub.close()
            
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                return AgentMessage(**data)
            
            return None
        except Exception as e:
            logger.error("Failed to receive message", agent_id=agent_id, error=str(e))
            return None

    async def broadcast_message(
        self,
        execution_id: UUID,
        from_agent: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[bool]:
        """Broadcast a message to all agents in an execution"""
        message = AgentMessage(
            execution_id=execution_id,
            from_agent=from_agent,
            payload=payload,
            metadata=metadata
        )
        
        try:
            if self.dev_mode:
                # Store in memory
                self._messages[str(message.message_id)] = message
                if "broadcast" not in self._message_queues:
                    self._message_queues["broadcast"] = []
                self._message_queues["broadcast"].append(message)
                logger.info("Message broadcasted via in-memory queue", 
                          execution_id=str(execution_id), from_agent=from_agent)
                return [True]
            
            await self.redis_client.publish("broadcast", message.json())
            await self._store_message(message)
            logger.info("Message broadcasted", execution_id=str(execution_id), from_agent=from_agent)
            return [True]
        except Exception as e:
            logger.error("Failed to broadcast message", execution_id=str(execution_id), error=str(e))
            return [False]

    async def _store_message(self, message: AgentMessage):
        """Store message in Redis for persistence"""
        try:
            if not self.dev_mode:
                key = f"message:{message.message_id}"
                await self.redis_client.setex(key, 3600, message.json())  # TTL: 1 hour
        except Exception as e:
            logger.error("Failed to store message", message_id=str(message.message_id), error=str(e))

    async def get_message_history(self, execution_id: UUID, limit: int = 100) -> List[AgentMessage]:
        """Get message history for an execution"""
        try:
            if self.dev_mode:
                # Get from in-memory storage
                messages = [
                    msg for msg in self._messages.values() 
                    if msg.execution_id == execution_id
                ]
                messages.sort(key=lambda x: x.timestamp)
                return messages[-limit:]
            
            pattern = f"message:*"
            messages = []
            
            async for key in self.redis_client.scan_iter(match=pattern):
                data = await self.redis_client.get(key)
                if data:
                    message = AgentMessage(**json.loads(data))
                    if message.execution_id == execution_id:
                        messages.append(message)
            
            # Sort by timestamp and limit
            messages.sort(key=lambda x: x.timestamp)
            return messages[-limit:]
        except Exception as e:
            logger.error("Failed to get message history", execution_id=str(execution_id), error=str(e))
            return []


# Global communication manager instance
communication_manager = CommunicationManager() 