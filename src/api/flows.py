from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import structlog

from src.core.orchestrator import orchestrator
from src.core.models import ExecutionRequest, ExecutionResponse, FlowDefinition

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])

@router.get("", response_model=Dict[str, Any])
async def list_flows():
    """List all available flows"""
    try:
        flows = orchestrator.list_flows()
        return {
            "flows": [flow.dict() for flow in flows],
            "count": len(flows)
        }
    except Exception as e:
        logger.error("Failed to list flows", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{flow_id}", response_model=FlowDefinition)
async def get_flow(flow_id: str):
    """Get a specific flow"""
    try:
        flow = orchestrator.get_flow(flow_id)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_id}' not found")
        return flow
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/execute", response_model=ExecutionResponse)
async def execute_flow(request: ExecutionRequest):
    """Execute a flow"""
    try:
        return await orchestrator.execute_flow(request)
    except Exception as e:
        logger.error("Flow execution failed", flow_id=request.flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=FlowDefinition)
async def create_flow(flow_definition: FlowDefinition):
    """Create a new flow"""
    try:
        flow = orchestrator.add_flow(flow_definition)
        return flow
    except Exception as e:
        logger.error("Failed to create flow", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{flow_id}", response_model=FlowDefinition)
async def update_flow(flow_id: str, flow_definition: FlowDefinition):
    """Update an existing flow"""
    try:
        if flow_id != flow_definition.flow_id:
            raise HTTPException(status_code=400, detail="Flow ID mismatch")
        
        flow = orchestrator.update_flow(flow_definition)
        if not flow:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_id}' not found")
        return flow
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{flow_id}")
async def delete_flow(flow_id: str):
    """Delete a flow"""
    try:
        success = orchestrator.delete_flow(flow_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Flow '{flow_id}' not found")
        return {"message": f"Flow '{flow_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))