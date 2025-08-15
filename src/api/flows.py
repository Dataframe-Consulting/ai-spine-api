from fastapi import APIRouter, HTTPException, Depends, status
from typing import List, Dict, Any, Optional
import structlog

from src.core.orchestrator import orchestrator
from src.core.models import ExecutionRequest, ExecutionResponse, FlowDefinition
from src.core.supabase_auth import verify_supabase_token, optional_supabase_token
from src.core.memory import memory_store

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/flows", tags=["flows"])

@router.get("", response_model=Dict[str, Any])
async def list_flows(user_id: Optional[str] = Depends(optional_supabase_token)):
    """List all available flows (system flows + user's flows if authenticated)"""
    try:
        # Get all active flows from orchestrator (in-memory cache)
        all_flows = orchestrator.list_flows()
        flows_list = [flow.dict() for flow in all_flows]
        
        # If authenticated, also get user's flows from database
        if user_id:
            user_flows = await memory_store.get_user_flows(user_id)
            # Add user flows that aren't already in the list
            existing_ids = {f['flow_id'] for f in flows_list}
            for flow in user_flows:
                if flow['flow_id'] not in existing_ids:
                    flows_list.append(flow)
        
        return {
            "flows": flows_list,
            "count": len(flows_list),
            "user_id": user_id
        }
    except Exception as e:
        logger.error("Failed to list flows", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/my-flows", response_model=Dict[str, Any])
async def get_my_flows(user_id: str = Depends(verify_supabase_token)):
    """Get flows created by the authenticated user"""
    try:
        user_flows = await memory_store.get_user_flows(user_id)
        return {
            "flows": user_flows,
            "count": len(user_flows),
            "user_id": user_id
        }
    except Exception as e:
        logger.error("Failed to get user flows", user_id=user_id, error=str(e))
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

@router.post("", response_model=FlowDefinition, status_code=status.HTTP_201_CREATED)
async def create_flow(
    flow_definition: FlowDefinition,
    user_id: str = Depends(verify_supabase_token)
):
    """Create a new flow (requires authentication)"""
    try:
        # Check if flow ID already exists
        existing_flow = await memory_store.get_flow(flow_definition.flow_id)
        if existing_flow:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Flow with ID '{flow_definition.flow_id}' already exists"
            )
        
        # Add flow with user ownership
        success = await orchestrator.add_flow(flow_definition, user_id=user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow validation failed. Check DAG structure and agent IDs."
            )
        
        logger.info("Flow created", flow_id=flow_definition.flow_id, user_id=user_id)
        return flow_definition
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create flow", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{flow_id}", response_model=FlowDefinition)
async def update_flow(
    flow_id: str,
    flow_definition: FlowDefinition,
    user_id: str = Depends(verify_supabase_token)
):
    """Update an existing flow (requires authentication and ownership)"""
    try:
        if flow_id != flow_definition.flow_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow ID in path doesn't match flow ID in body"
            )
        
        # Check if flow exists
        existing_flow = await memory_store.get_flow(flow_id)
        if not existing_flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow '{flow_id}' not found"
            )
        
        # Check permissions (only owner can update, unless it's a system flow)
        if existing_flow.get('created_by') and existing_flow['created_by'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to update this flow"
            )
        
        # Update flow
        success = await orchestrator.update_flow(flow_id, flow_definition, user_id=user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Flow validation failed or update not allowed"
            )
        
        logger.info("Flow updated", flow_id=flow_id, user_id=user_id)
        return flow_definition
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{flow_id}")
async def delete_flow(
    flow_id: str,
    user_id: str = Depends(verify_supabase_token)
):
    """Delete a flow (soft delete - requires authentication and ownership)"""
    try:
        # Check if flow exists
        existing_flow = await memory_store.get_flow(flow_id)
        if not existing_flow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Flow '{flow_id}' not found"
            )
        
        # Check permissions (only owner can delete, unless it's a system flow)
        if existing_flow.get('created_by') and existing_flow['created_by'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to delete this flow"
            )
        
        # Prevent deletion of system flows (those without created_by)
        if not existing_flow.get('created_by'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="System flows cannot be deleted"
            )
        
        # Soft delete flow
        success = await orchestrator.delete_flow(flow_id, user_id=user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete flow"
            )
        
        logger.info("Flow deleted", flow_id=flow_id, user_id=user_id)
        return {"message": f"Flow '{flow_id}' deleted successfully", "status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete flow", flow_id=flow_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))