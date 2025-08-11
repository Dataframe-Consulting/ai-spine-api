from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from uuid import UUID
import structlog

from src.core.orchestrator import orchestrator
from src.core.memory import memory_store
from src.core.models import ExecutionContextResponse, AgentMessage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/executions", tags=["executions"])

@router.get("/{execution_id}", response_model=ExecutionContextResponse)
async def get_execution_status(execution_id: UUID):
    """Get execution status"""
    try:
        context = await orchestrator.get_execution_status(execution_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
        return ExecutionContextResponse.from_sqlalchemy(context)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get execution status", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: UUID):
    """Cancel a running execution"""
    try:
        success = await orchestrator.cancel_execution(execution_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found or not running")
        return {"message": "Execution cancelled successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel execution", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{execution_id}/messages", response_model=Dict[str, Any])
async def get_execution_messages(execution_id: UUID, limit: int = 100, offset: int = 0):
    """Get messages for an execution"""
    try:
        messages = await memory_store.get_messages(execution_id, limit, offset)
        return {
            "messages": [message.dict() for message in messages],
            "count": len(messages),
            "execution_id": str(execution_id)
        }
    except Exception as e:
        logger.error("Failed to get messages", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=Dict[str, Any])
async def list_executions(limit: int = 20, offset: int = 0, status: str = None):
    """List executions with optional filtering"""
    try:
        executions = await memory_store.list_executions(None, limit, offset)
        return {
            "executions": [ExecutionContextResponse.from_sqlalchemy(execution).dict() for execution in executions],
            "count": len(executions),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error("Failed to list executions", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{execution_id}/results", response_model=Dict[str, Any])
async def get_execution_results(execution_id: UUID):
    """Get detailed results for an execution"""
    try:
        context = await orchestrator.get_execution_status(execution_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
        
        # Get node results
        node_results = await memory_store.get_node_results(execution_id)
        
        return {
            "execution": ExecutionContextResponse.from_sqlalchemy(context).dict(),
            "node_results": [result.dict() for result in node_results]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get execution results", execution_id=str(execution_id), error=str(e))
        raise HTTPException(status_code=500, detail=str(e))