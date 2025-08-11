import asyncio
import structlog
from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime
import os
from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    ExecutionContext as ExecutionContextModel, 
    NodeExecutionResult as NodeExecutionResultModel, 
    AgentMessage as AgentMessageModel, 
    Metrics, 
    ExecutionStatus
)
from .database import get_db_session

logger = structlog.get_logger(__name__)


class MemoryStore:
    def __init__(self):
        self.dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"
        
        # In-memory storage (fallback for dev mode)
        if self.dev_mode:
            self._executions: Dict[str, ExecutionContextModel] = {}
            self._messages: Dict[str, AgentMessageModel] = {}
            self._node_results: Dict[str, NodeExecutionResultModel] = {}

    async def start(self):
        """Start the memory store"""
        logger.info("Starting Memory Store")
        if self.dev_mode:
            logger.info("Running in development mode - using in-memory storage")
        else:
            logger.info("Running in production mode - using PostgreSQL storage")

    async def stop(self):
        """Stop the memory store"""
        logger.info("Memory Store stopped")

    async def store_execution(self, context: ExecutionContextModel) -> bool:
        """Store execution context"""
        try:
            if self.dev_mode:
                # Store in memory
                self._executions[str(context.execution_id)] = context
                logger.info("Execution stored in memory", execution_id=str(context.execution_id))
            else:
                # Store in database
                async with get_db_session() as session:
                    session.add(context)
                    await session.commit()
                    logger.info("Execution stored in database", execution_id=str(context.execution_id))
            return True
        except Exception as e:
            logger.error("Failed to store execution", execution_id=str(context.execution_id), error=str(e))
            return False

    async def get_execution(self, execution_id: UUID) -> Optional[ExecutionContextModel]:
        """Get execution context"""
        try:
            if self.dev_mode:
                # Get from memory
                return self._executions.get(str(execution_id))
            else:
                # Get from database
                async with get_db_session() as session:
                    result = await session.execute(
                        select(ExecutionContextModel).where(
                            ExecutionContextModel.execution_id == str(execution_id)
                        )
                    )
                    return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get execution", execution_id=str(execution_id), error=str(e))
            return None

    async def store_message(self, message: AgentMessageModel) -> bool:
        """Store agent message"""
        try:
            if self.dev_mode:
                # Store in memory
                self._messages[str(message.id)] = message
                logger.debug("Message stored in memory", message_id=str(message.id))
            else:
                # Store in database
                async with get_db_session() as session:
                    session.add(message)
                    await session.commit()
                    logger.debug("Message stored in database", message_id=str(message.id))
            return True
        except Exception as e:
            logger.error("Failed to store message", message_id=str(message.id), error=str(e))
            return False

    async def get_messages(self, execution_id: UUID, limit: int = 100, offset: int = 0) -> List[AgentMessageModel]:
        """Get messages for an execution"""
        try:
            if self.dev_mode:
                # Get from memory
                messages = [
                    msg for msg in self._messages.values() 
                    if msg.execution_id == str(execution_id)
                ]
                messages.sort(key=lambda x: x.timestamp)
                return messages[offset:offset + limit]
            else:
                # Get from database
                async with get_db_session() as session:
                    result = await session.execute(
                        select(AgentMessageModel)
                        .where(AgentMessageModel.execution_id == str(execution_id))
                        .order_by(AgentMessageModel.timestamp)
                        .offset(offset)
                        .limit(limit)
                    )
                    return result.scalars().all()
        except Exception as e:
            logger.error("Failed to get messages", execution_id=str(execution_id), error=str(e))
            return []

    async def store_node_result(self, result: NodeExecutionResultModel) -> bool:
        """Store node execution result"""
        try:
            if self.dev_mode:
                # Store in memory
                key = f"{result.execution_id}:{result.node_id}"
                self._node_results[key] = result
                logger.info("Node result stored in memory", execution_id=str(result.execution_id), node_id=result.node_id)
            else:
                # Store in database
                async with get_db_session() as session:
                    session.add(result)
                    await session.commit()
                    logger.info("Node result stored in database", execution_id=str(result.execution_id), node_id=result.node_id)
            return True
        except Exception as e:
            logger.error("Failed to store node result", execution_id=str(result.execution_id), node_id=result.node_id, error=str(e))
            return False

    async def get_metrics(self, flow_id: Optional[str] = None) -> Metrics:
        """Get system metrics"""
        try:
            if self.dev_mode:
                # Calculate metrics from in-memory data
                executions = list(self._executions.values())
                if flow_id:
                    executions = [e for e in executions if e.flow_id == flow_id]
                
                total_executions = len(executions)
                successful_executions = len([e for e in executions if e.status == "completed"])
                failed_executions = len([e for e in executions if e.status == "failed"])
                
                # Calculate average execution time
                completed_executions = [e for e in executions 
                                     if e.status == "completed" and e.created_at and e.completed_at]
                
                total_time = 0
                count = 0
                for execution in completed_executions:
                    duration = (execution.completed_at - execution.created_at).total_seconds()
                    total_time += duration
                    count += 1
                
                average_time = total_time / count if count > 0 else 0.0
                last_execution = max([e.created_at for e in executions]) if executions else None
            else:
                # Calculate metrics from database
                async with get_db_session() as session:
                    # Base query
                    base_query = select(ExecutionContextModel)
                    if flow_id:
                        base_query = base_query.where(ExecutionContextModel.flow_id == flow_id)
                    
                    # Total executions
                    total_result = await session.execute(
                        select(func.count()).select_from(base_query.subquery())
                    )
                    total_executions = total_result.scalar() or 0
                    
                    # Successful executions
                    success_result = await session.execute(
                        select(func.count()).select_from(
                            base_query.where(ExecutionContextModel.status == "completed").subquery()
                        )
                    )
                    successful_executions = success_result.scalar() or 0
                    
                    # Failed executions
                    failed_result = await session.execute(
                        select(func.count()).select_from(
                            base_query.where(ExecutionContextModel.status == "failed").subquery()
                        )
                    )
                    failed_executions = failed_result.scalar() or 0
                    
                    # Average execution time
                    avg_result = await session.execute(
                        select(func.avg(
                            func.extract('epoch', ExecutionContextModel.completed_at - ExecutionContextModel.created_at)
                        )).select_from(
                            base_query.where(
                                and_(
                                    ExecutionContextModel.status == "completed",
                                    ExecutionContextModel.completed_at.isnot(None)
                                )
                            ).subquery()
                        )
                    )
                    average_time = avg_result.scalar() or 0.0
                    
                    # Last execution
                    last_result = await session.execute(
                        select(func.max(ExecutionContextModel.created_at)).select_from(base_query.subquery())
                    )
                    last_execution = last_result.scalar()
            
            return Metrics(
                total_executions=total_executions,
                successful_executions=successful_executions,
                failed_executions=failed_executions,
                average_execution_time=average_time,
                total_execution_time=total_time if self.dev_mode else 0.0,
                last_execution=last_execution
            )
        except Exception as e:
            logger.error("Failed to get metrics", error=str(e))
            return Metrics()

    async def get_node_results(self, execution_id: UUID) -> List[NodeExecutionResultModel]:
        """Get all node results for an execution"""
        try:
            if self.dev_mode:
                # Get from memory
                results = [
                    result for key, result in self._node_results.items()
                    if key.startswith(f"{execution_id}:")
                ]
                results.sort(key=lambda x: x.created_at)
                return results
            else:
                # Get from database
                async with get_db_session() as session:
                    result = await session.execute(
                        select(NodeExecutionResultModel)
                        .where(NodeExecutionResultModel.execution_id == str(execution_id))
                        .order_by(NodeExecutionResultModel.created_at)
                    )
                    return result.scalars().all()
        except Exception as e:
            logger.error("Failed to get node results", execution_id=str(execution_id), error=str(e))
            return []

    async def get_node_result(self, execution_id: UUID, node_id: str) -> Optional[NodeExecutionResultModel]:
        """Get specific node result"""
        try:
            if self.dev_mode:
                # Get from memory
                key = f"{execution_id}:{node_id}"
                return self._node_results.get(key)
            else:
                # Get from database
                async with get_db_session() as session:
                    result = await session.execute(
                        select(NodeExecutionResultModel).where(
                            and_(
                                NodeExecutionResultModel.execution_id == str(execution_id),
                                NodeExecutionResultModel.node_id == node_id
                            )
                        )
                    )
                    return result.scalar_one_or_none()
        except Exception as e:
            logger.error("Failed to get node result", execution_id=str(execution_id), node_id=node_id, error=str(e))
            return None

    async def list_executions(self, flow_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[ExecutionContextModel]:
        """List executions with optional filtering"""
        try:
            if self.dev_mode:
                # Get from memory
                executions = list(self._executions.values())
                if flow_id:
                    executions = [e for e in executions if e.flow_id == flow_id]
                executions.sort(key=lambda x: x.created_at, reverse=True)
                return executions[offset:offset + limit]
            else:
                # Get from database
                async with get_db_session() as session:
                    query = select(ExecutionContextModel)
                    if flow_id:
                        query = query.where(ExecutionContextModel.flow_id == flow_id)
                    query = query.order_by(ExecutionContextModel.created_at.desc())
                    query = query.offset(offset).limit(limit)
                    
                    result = await session.execute(query)
                    return result.scalars().all()
        except Exception as e:
            logger.error("Failed to list executions", error=str(e))
            return []

    async def update_execution_status(self, execution_id: UUID, status: str, output_data: Optional[Dict[str, Any]] = None) -> bool:
        """Update execution status and output data"""
        try:
            if self.dev_mode:
                # Update in memory
                execution = self._executions.get(str(execution_id))
                if execution:
                    execution.status = status
                    execution.updated_at = datetime.utcnow()
                    if status in ["completed", "failed"]:
                        execution.completed_at = datetime.utcnow()
                    if output_data:
                        execution.output_data = output_data
                    logger.info("Execution status updated in memory", execution_id=str(execution_id), status=status)
                    return True
                return False
            else:
                # Update in database
                async with get_db_session() as session:
                    result = await session.execute(
                        select(ExecutionContextModel).where(
                            ExecutionContextModel.execution_id == str(execution_id)
                        )
                    )
                    execution = result.scalar_one_or_none()
                    if execution:
                        execution.status = status
                        execution.updated_at = datetime.utcnow()
                        if status in ["completed", "failed"]:
                            execution.completed_at = datetime.utcnow()
                        if output_data:
                            execution.output_data = output_data
                        await session.commit()
                        logger.info("Execution status updated in database", execution_id=str(execution_id), status=status)
                        return True
                    return False
        except Exception as e:
            logger.error("Failed to update execution status", execution_id=str(execution_id), error=str(e))
            return False


# Global memory store instance
memory_store = MemoryStore() 