"""
Memory Store implementation using Supabase
Reemplaza completamente memory.py que usaba SQLAlchemy
"""
import asyncio
import structlog
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime
import os
import json

from src.core.supabase_client import get_supabase_db
from src.core.models import (
    ExecutionStatus,
    ExecutionContextResponse,
    Metrics,
    AgentMessagePydantic
)

logger = structlog.get_logger(__name__)


class MemoryStoreSupabase:
    def __init__(self):
        self.dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
        self._db = None
        
        # In-memory storage for dev mode
        if self.dev_mode:
            self._executions: Dict[str, Dict] = {}
            self._messages: Dict[str, Dict] = {}
            self._node_results: Dict[str, Dict] = {}
    
    @property
    def db(self):
        """Lazy load Supabase client"""
        if self._db is None and not self.dev_mode:
            self._db = get_supabase_db()
        return self._db

    async def start(self):
        """Start the memory store"""
        logger.info("Starting Memory Store")
        if self.dev_mode:
            logger.info("Running in development mode - using in-memory storage")
        else:
            logger.info("Running in production mode - using Supabase storage")
            # Test connection
            try:
                self.db.client.table("execution_contexts").select("count").limit(1).execute()
                logger.info("Supabase connection verified")
            except Exception as e:
                logger.error("Failed to connect to Supabase", error=str(e))

    async def stop(self):
        """Stop the memory store"""
        logger.info("Memory Store stopped")

    async def store_execution(self, context: Dict[str, Any]) -> bool:
        """Store execution context"""
        try:
            execution_id = str(context.get("execution_id"))
            
            if self.dev_mode:
                # Store in memory
                self._executions[execution_id] = context
                logger.info("Execution stored in memory", execution_id=execution_id)
            else:
                # Store in Supabase
                data = {
                    "execution_id": execution_id,
                    "flow_id": context.get("flow_id"),
                    "user_id": context.get("user_id"),
                    "status": context.get("status", "pending"),
                    "input_data": context.get("input_data", {}),
                    "output_data": context.get("output_data", {}),
                    "priority": context.get("priority", 0),
                    "timeout": context.get("timeout"),
                    "metadata": context.get("metadata", {}),
                    "created_at": context.get("created_at", datetime.utcnow().isoformat()),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                response = self.db.client.table("execution_contexts").upsert(data).execute()
                logger.info("Execution stored in Supabase", execution_id=execution_id)
            return True
        except Exception as e:
            logger.error("Failed to store execution", execution_id=str(context.get("execution_id")), error=str(e))
            return False

    async def get_execution(self, execution_id: UUID) -> Optional[Dict]:
        """Get execution context"""
        try:
            execution_id_str = str(execution_id)
            
            if self.dev_mode:
                # Get from memory
                return self._executions.get(execution_id_str)
            else:
                # Get from Supabase
                response = self.db.client.table("execution_contexts")\
                    .select("*")\
                    .eq("execution_id", execution_id_str)\
                    .single()\
                    .execute()
                return response.data if response.data else None
        except Exception as e:
            logger.error("Failed to get execution", execution_id=str(execution_id), error=str(e))
            return None

    async def update_execution_status(self, execution_id: UUID, status: str, 
                                    output_data: Optional[Dict] = None,
                                    error_message: Optional[str] = None) -> bool:
        """Update execution status"""
        try:
            execution_id_str = str(execution_id)
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            }
            
            if output_data is not None:
                update_data["output_data"] = output_data
            
            if error_message:
                update_data["error_message"] = error_message
            
            if status in ["completed", "failed", "cancelled"]:
                update_data["completed_at"] = datetime.utcnow().isoformat()
            
            if self.dev_mode:
                # Update in memory
                if execution_id_str in self._executions:
                    self._executions[execution_id_str].update(update_data)
                    logger.info("Execution status updated in memory", 
                              execution_id=execution_id_str, status=status)
                    return True
                return False
            else:
                # Update in Supabase
                response = self.db.client.table("execution_contexts")\
                    .update(update_data)\
                    .eq("execution_id", execution_id_str)\
                    .execute()
                logger.info("Execution status updated in Supabase", 
                          execution_id=execution_id_str, status=status)
                return bool(response.data)
        except Exception as e:
            logger.error("Failed to update execution status", 
                        execution_id=str(execution_id), error=str(e))
            return False

    async def store_message(self, message: Dict[str, Any]) -> bool:
        """Store agent message"""
        try:
            message_id = str(message.get("id", message.get("message_id")))
            
            if self.dev_mode:
                # Store in memory
                self._messages[message_id] = message
                logger.debug("Message stored in memory", message_id=message_id)
            else:
                # Store in Supabase
                data = {
                    "id": message_id,
                    "execution_id": str(message.get("execution_id")),
                    "node_id": message.get("node_id", ""),
                    "agent_id": message.get("agent_id", ""),
                    "from_agent": message.get("from_agent", ""),
                    "to_agent": message.get("to_agent", ""),
                    "message_type": message.get("message_type", "request"),
                    "content": message.get("payload", message.get("content", {})),
                    "metadata": message.get("metadata", {}),
                    "timestamp": message.get("timestamp", datetime.utcnow().isoformat())
                }
                
                response = self.db.client.table("agent_messages").insert(data).execute()
                logger.debug("Message stored in Supabase", message_id=message_id)
            return True
        except Exception as e:
            logger.error("Failed to store message", error=str(e))
            return False

    async def get_messages(self, execution_id: UUID, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get messages for an execution"""
        try:
            execution_id_str = str(execution_id)
            
            if self.dev_mode:
                # Get from memory
                messages = [
                    msg for msg in self._messages.values()
                    if str(msg.get("execution_id")) == execution_id_str
                ]
                # Sort by timestamp and apply pagination
                messages.sort(key=lambda x: x.get("timestamp", ""))
                return messages[offset:offset + limit]
            else:
                # Get from Supabase
                response = self.db.client.table("agent_messages")\
                    .select("*")\
                    .eq("execution_id", execution_id_str)\
                    .order("timestamp", desc=False)\
                    .range(offset, offset + limit - 1)\
                    .execute()
                return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to get messages", execution_id=str(execution_id), error=str(e))
            return []

    async def store_node_result(self, result: Dict[str, Any]) -> bool:
        """Store node execution result"""
        try:
            result_id = str(result.get("id", result.get("result_id")))
            
            if self.dev_mode:
                # Store in memory
                self._node_results[result_id] = result
                logger.debug("Node result stored in memory", result_id=result_id)
            else:
                # Store in Supabase
                data = {
                    "id": result_id,
                    "execution_id": str(result.get("execution_id")),
                    "node_id": result.get("node_id"),
                    "agent_id": result.get("agent_id"),
                    "status": result.get("status", "pending"),
                    "input_data": result.get("input_data", {}),
                    "output_data": result.get("output_data", {}),
                    "error_message": result.get("error_message"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "created_at": result.get("created_at", datetime.utcnow().isoformat()),
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                if result.get("status") in ["completed", "failed"]:
                    data["completed_at"] = datetime.utcnow().isoformat()
                
                response = self.db.client.table("node_execution_results").upsert(data).execute()
                logger.debug("Node result stored in Supabase", result_id=result_id)
            return True
        except Exception as e:
            logger.error("Failed to store node result", error=str(e))
            return False

    async def get_node_results(self, execution_id: UUID) -> List[Dict]:
        """Get all node results for an execution"""
        try:
            execution_id_str = str(execution_id)
            
            if self.dev_mode:
                # Get from memory
                results = [
                    result for result in self._node_results.values()
                    if str(result.get("execution_id")) == execution_id_str
                ]
                return results
            else:
                # Get from Supabase
                response = self.db.client.table("node_execution_results")\
                    .select("*")\
                    .eq("execution_id", execution_id_str)\
                    .order("created_at")\
                    .execute()
                return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to get node results", execution_id=str(execution_id), error=str(e))
            return []

    async def list_executions(self, flow_id: Optional[str] = None, 
                            limit: int = 100, offset: int = 0) -> List[Dict]:
        """List executions with optional filtering"""
        try:
            if self.dev_mode:
                # Get from memory
                executions = list(self._executions.values())
                if flow_id:
                    executions = [e for e in executions if e.get("flow_id") == flow_id]
                # Sort by created_at descending
                executions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
                return executions[offset:offset + limit]
            else:
                # Get from Supabase
                query = self.db.client.table("execution_contexts").select("*")
                
                if flow_id:
                    query = query.eq("flow_id", flow_id)
                
                response = query.order("created_at", desc=True)\
                    .range(offset, offset + limit - 1)\
                    .execute()
                
                return response.data if response.data else []
        except Exception as e:
            logger.error("Failed to list executions", error=str(e))
            return []

    async def get_metrics(self) -> Metrics:
        """Get execution metrics"""
        try:
            if self.dev_mode:
                # Calculate from memory
                executions = list(self._executions.values())
                total = len(executions)
                successful = len([e for e in executions if e.get("status") == "completed"])
                failed = len([e for e in executions if e.get("status") == "failed"])
                
                # Calculate average execution time
                execution_times = []
                for e in executions:
                    if e.get("completed_at") and e.get("created_at"):
                        # Simple time calculation for dev mode
                        execution_times.append(10.0)  # Mock value for dev mode
                
                avg_time = sum(execution_times) / len(execution_times) if execution_times else 0.0
                
                last_execution = None
                if executions:
                    last_execution = max(executions, key=lambda x: x.get("created_at", "")).get("created_at")
                    if isinstance(last_execution, str):
                        last_execution = datetime.fromisoformat(last_execution.replace("Z", "+00:00"))
                
                return Metrics(
                    total_executions=total,
                    successful_executions=successful,
                    failed_executions=failed,
                    average_execution_time=avg_time,
                    total_execution_time=sum(execution_times),
                    last_execution=last_execution
                )
            else:
                # Get from Supabase view
                response = self.db.client.table("execution_metrics").select("*").execute()
                
                if response.data and response.data[0]:
                    data = response.data[0]
                    return Metrics(
                        total_executions=data.get("total_executions", 0),
                        successful_executions=data.get("successful_executions", 0),
                        failed_executions=data.get("failed_executions", 0),
                        average_execution_time=data.get("avg_execution_time_seconds", 0.0),
                        last_execution=datetime.fromisoformat(data["last_execution_at"]) if data.get("last_execution_at") else None
                    )
                
                return Metrics()
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            return Metrics()

    # Agent registry methods
    async def register_agent(self, agent_data: Dict[str, Any]) -> bool:
        """Register an agent in the database"""
        try:
            if not self.dev_mode:
                data = {
                    "agent_id": agent_data["agent_id"],
                    "name": agent_data["name"],
                    "description": agent_data.get("description", ""),
                    "endpoint": agent_data["endpoint"],
                    "capabilities": agent_data.get("capabilities", []),
                    "agent_type": agent_data.get("agent_type", "processor"),
                    "is_active": agent_data.get("is_active", True),
                    "metadata": agent_data.get("metadata", {}),
                    "created_by": agent_data.get("created_by")  # Now the column exists
                }
                
                response = self.db.client.table("agents").upsert(data).execute()
                logger.info("Agent registered in Supabase", agent_id=agent_data["agent_id"])
                return bool(response.data)
            return True
        except Exception as e:
            logger.error("Failed to register agent", error=str(e))
            return False

    async def get_agents(self, active_only: bool = False) -> List[Dict]:
        """Get all agents from database sorted by creation date (newest first)"""
        try:
            if not self.dev_mode:
                query = self.db.client.table("agents").select("*")
                if active_only:
                    query = query.eq("is_active", True)
                response = query.order("created_at", desc=True).execute()
                return response.data if response.data else []
            return []
        except Exception as e:
            logger.error("Failed to get agents", error=str(e))
            return []

    # Flow definition methods
    async def store_flow(self, flow_data: Dict[str, Any]) -> bool:
        """Store flow definition"""
        try:
            if not self.dev_mode:
                # Convert nodes to list of dicts if they are Pydantic objects
                nodes = flow_data.get("nodes", [])
                if nodes and hasattr(nodes[0], 'dict'):
                    nodes = [node.dict() if hasattr(node, 'dict') else node for node in nodes]
                
                data = {
                    "flow_id": flow_data.get("flow_id"),
                    "name": flow_data.get("name"),
                    "description": flow_data.get("description", ""),
                    "version": flow_data.get("version", "1.0.0"),
                    "nodes": nodes,
                    "entry_point": flow_data.get("entry_point"),
                    "exit_points": flow_data.get("exit_points", []),
                    "metadata": flow_data.get("metadata", {}),
                    "is_active": flow_data.get("is_active", True),
                    "created_by": flow_data.get("created_by")  # Include created_by if provided
                }
                
                response = self.db.client.table("flow_definitions").upsert(data).execute()
                logger.info("Flow stored in Supabase", flow_id=flow_data["flow_id"])
                return bool(response.data)
            return True
        except Exception as e:
            logger.error("Failed to store flow", error=str(e))
            return False

    async def get_flows(self, active_only: bool = False) -> List[Dict]:
        """Get all flow definitions"""
        try:
            if not self.dev_mode:
                query = self.db.client.table("flow_definitions").select("*")
                if active_only:
                    query = query.eq("is_active", True)
                response = query.execute()
                return response.data if response.data else []
            return []
        except Exception as e:
            logger.error("Failed to get flows", error=str(e))
            return []
    
    async def get_flow(self, flow_id: str) -> Optional[Dict]:
        """Get a specific flow definition"""
        try:
            if not self.dev_mode:
                response = self.db.client.table("flow_definitions")\
                    .select("*")\
                    .eq("flow_id", flow_id)\
                    .execute()
                return response.data[0] if response.data else None
            return None
        except Exception as e:
            logger.error("Failed to get flow", flow_id=flow_id, error=str(e))
            return None
    
    async def update_flow(self, flow_id: str, flow_data: Dict[str, Any]) -> bool:
        """Update flow definition"""
        try:
            if not self.dev_mode:
                # Ensure updated_at is set
                flow_data['updated_at'] = datetime.utcnow().isoformat()
                
                response = self.db.client.table("flow_definitions")\
                    .update(flow_data)\
                    .eq("flow_id", flow_id)\
                    .execute()
                logger.info("Flow updated in Supabase", flow_id=flow_id)
                return bool(response.data)
            return True
        except Exception as e:
            logger.error("Failed to update flow", flow_id=flow_id, error=str(e))
            return False
    
    async def delete_flow(self, flow_id: str) -> bool:
        """Soft delete flow (set is_active to false)"""
        try:
            if not self.dev_mode:
                response = self.db.client.table("flow_definitions")\
                    .update({"is_active": False, "updated_at": datetime.utcnow().isoformat()})\
                    .eq("flow_id", flow_id)\
                    .execute()
                logger.info("Flow soft deleted in Supabase", flow_id=flow_id)
                return bool(response.data)
            return True
        except Exception as e:
            logger.error("Failed to delete flow", flow_id=flow_id, error=str(e))
            return False
    
    async def get_user_flows(self, user_id: str) -> List[Dict]:
        """Get flows created by a specific user"""
        try:
            if not self.dev_mode:
                response = self.db.client.table("flow_definitions")\
                    .select("*")\
                    .eq("created_by", user_id)\
                    .eq("is_active", True)\
                    .execute()
                return response.data if response.data else []
            return []
        except Exception as e:
            logger.error("Failed to get user flows", user_id=user_id, error=str(e))
            return []


# Singleton instance
memory_store = MemoryStoreSupabase()