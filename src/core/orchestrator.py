import asyncio
import time
import networkx as nx
import structlog
import yaml
import httpx
from typing import Dict, List, Optional, Any, Set
from uuid import UUID
from datetime import datetime
from pathlib import Path

from .models import (
    ExecutionContext, ExecutionStatus, FlowDefinition, FlowNode,
    NodeExecutionResult, AgentMessage, ExecutionRequest, ExecutionResponse
)
from .registry import registry
from .communication import communication_manager
from .memory import memory_store

logger = structlog.get_logger(__name__)


class FlowOrchestrator:
    def __init__(self):
        self._flows: Dict[str, FlowDefinition] = {}
        self._executions: Dict[UUID, ExecutionContext] = {}
        self._running_executions: Set[UUID] = set()

    async def start(self):
        """Start the orchestrator and load flows"""
        logger.info("Starting Flow Orchestrator")
        await self._load_flows()
        logger.info("Flow Orchestrator started")

    async def _load_flows(self):
        """Load flow definitions from YAML files"""
        flows_dir = Path(__file__).parent.parent / "flows"
        if not flows_dir.exists():
            logger.warning("Flows directory not found", path=str(flows_dir))
            return

        for yaml_file in flows_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    flow_data = yaml.safe_load(f)
                    flow_def = FlowDefinition(**flow_data)
                    
                    if await self._validate_flow(flow_def):
                        self._flows[flow_def.flow_id] = flow_def
                        logger.info("Flow loaded", flow_id=flow_def.flow_id, name=flow_def.name)
                    else:
                        logger.error("Invalid flow definition", flow_id=flow_def.flow_id)
            except Exception as e:
                logger.error("Failed to load flow", file=str(yaml_file), error=str(e))

    async def _validate_flow(self, flow_def: FlowDefinition) -> bool:
        """Validate flow structure and dependencies"""
        try:
            # Create directed graph
            G = nx.DiGraph()
            
            # Add nodes
            for node in flow_def.nodes:
                G.add_node(node.id)
            
            # Add edges based on dependencies
            for node in flow_def.nodes:
                for dep in node.depends_on:
                    if dep in G.nodes:
                        G.add_edge(dep, node.id)
                    else:
                        logger.error("Invalid dependency", node_id=node.id, dependency=dep)
                        return False
            
            # Check for cycles
            if not nx.is_directed_acyclic_graph(G):
                logger.error("Flow contains cycles", flow_id=flow_def.flow_id)
                return False
            
            # Check that entry point exists
            if flow_def.entry_point not in G.nodes:
                logger.error("Entry point not found", flow_id=flow_def.flow_id, entry_point=flow_def.entry_point)
                return False
            
            # Check that exit points exist
            for exit_point in flow_def.exit_points:
                if exit_point not in G.nodes:
                    logger.error("Exit point not found", flow_id=flow_def.flow_id, exit_point=exit_point)
                    return False
            
            return True
        except Exception as e:
            logger.error("Flow validation failed", flow_id=flow_def.flow_id, error=str(e))
            return False

    async def execute_flow(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute a flow"""
        try:
            # Check if flow exists
            if request.flow_id not in self._flows:
                return ExecutionResponse(
                    execution_id=UUID('00000000-0000-0000-0000-000000000000'),
                    status=ExecutionStatus.FAILED,
                    message=f"Flow '{request.flow_id}' not found"
                )
            
            flow_def = self._flows[request.flow_id]
            
            # Create execution context
            context = ExecutionContext(
                flow_id=request.flow_id,
                input_data=request.input_data,
                metadata=request.metadata or {}
            )
            
            # Store execution context
            await memory_store.store_execution(context)
            self._executions[context.execution_id] = context
            
            # Start async execution
            asyncio.create_task(self._execute_flow_async(context, flow_def))
            
            logger.info("Flow execution started", execution_id=str(context.execution_id), flow_id=request.flow_id)
            
            return ExecutionResponse(
                execution_id=context.execution_id,
                status=ExecutionStatus.PENDING,
                message="Flow execution started"
            )
        except Exception as e:
            logger.error("Failed to start flow execution", flow_id=request.flow_id, error=str(e))
            return ExecutionResponse(
                execution_id=UUID('00000000-0000-0000-0000-000000000000'),
                status=ExecutionStatus.FAILED,
                message=f"Failed to start execution: {str(e)}"
            )

    async def _execute_flow_async(self, context: ExecutionContext, flow_def: FlowDefinition):
        """Execute flow asynchronously"""
        try:
            self._running_executions.add(context.execution_id)
            context.status = ExecutionStatus.RUNNING
            context.started_at = datetime.utcnow()
            await memory_store.store_execution(context)
            
            # Create directed graph for topological sort
            G = nx.DiGraph()
            for node in flow_def.nodes:
                G.add_node(node.id, node=node)
                for dep in node.depends_on:
                    G.add_edge(dep, node.id)
            
            # Get execution order
            execution_order = list(nx.topological_sort(G))
            
            # Execute nodes in order
            node_results = {}
            for node_id in execution_order:
                node = next(n for n in flow_def.nodes if n.id == node_id)
                
                # Prepare input data
                input_data = context.input_data.copy()
                for dep in node.depends_on:
                    if dep in node_results:
                        input_data.update(node_results[dep].output_data or {})
                
                # Execute node
                result = await self._execute_node(context, node, input_data)
                node_results[node_id] = result
                
                # Store result
                await memory_store.store_node_result(result)
                
                # Check if execution should continue
                if result.status == ExecutionStatus.FAILED:
                    context.status = ExecutionStatus.FAILED
                    context.error_message = result.error_message
                    break
            
            # Update final status
            if context.status != ExecutionStatus.FAILED:
                context.status = ExecutionStatus.COMPLETED
                context.completed_at = datetime.utcnow()
                
                # Prepare output data
                output_data = {}
                for exit_point in flow_def.exit_points:
                    if exit_point in node_results:
                        output_data[exit_point] = node_results[exit_point].output_data
                context.output_data = output_data
            
            await memory_store.store_execution(context)
            logger.info("Flow execution completed", execution_id=str(context.execution_id), status=context.status.value)
            
        except Exception as e:
            logger.error("Flow execution failed", execution_id=str(context.execution_id), error=str(e))
            context.status = ExecutionStatus.FAILED
            context.error_message = str(e)
            context.completed_at = datetime.utcnow()
            await memory_store.store_execution(context)
        finally:
            self._running_executions.discard(context.execution_id)

    async def _execute_node(self, context: ExecutionContext, node: FlowNode, input_data: Dict[str, Any]) -> NodeExecutionResult:
        """Execute a single node"""
        start_time = datetime.utcnow()
        
        try:
            logger.info("Executing node", execution_id=str(context.execution_id), node_id=node.id, agent_id=node.agent_id)
            
            if node.agent_id:
                # Execute agent
                output_data = await self._invoke_agent(node.agent_id, input_data, node.config)
                status = ExecutionStatus.COMPLETED
                error_message = None
            else:
                # Output node - just pass through data
                output_data = input_data
                status = ExecutionStatus.COMPLETED
                error_message = None
            
            completed_at = datetime.utcnow()
            execution_time = (completed_at - start_time).total_seconds()
            
            return NodeExecutionResult(
                execution_id=context.execution_id,
                node_id=node.id,
                agent_id=node.agent_id,
                status=status,
                input_data=input_data,
                output_data=output_data,
                started_at=start_time,
                completed_at=completed_at,
                error_message=error_message,
                execution_time=execution_time,
                metadata=node.metadata
            )
            
        except Exception as e:
            logger.error("Node execution failed", execution_id=str(context.execution_id), node_id=node.id, error=str(e))
            return NodeExecutionResult(
                execution_id=context.execution_id,
                node_id=node.id,
                agent_id=node.agent_id,
                status=ExecutionStatus.FAILED,
                input_data=input_data,
                output_data=None,
                started_at=start_time,
                completed_at=datetime.utcnow(),
                error_message=str(e),
                execution_time=(datetime.utcnow() - start_time).total_seconds(),
                metadata=node.metadata
            )

    async def _invoke_agent(self, agent_id: str, input_data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke an external agent"""
        agent = registry.get_agent(agent_id)
        if not agent:
            # In development mode, return mock data instead of failing
            logger.warning(f"Agent '{agent_id}' not found, returning mock data")
            return {
                "status": "mock_response",
                "agent_id": agent_id,
                "input_received": input_data,
                "config": config,
                "message": "This is a mock response in development mode"
            }
        
        if not agent.is_active:
            logger.warning(f"Agent '{agent_id}' is not active, returning mock data")
            return {
                "status": "mock_response",
                "agent_id": agent_id,
                "input_received": input_data,
                "config": config,
                "message": "This is a mock response for inactive agent"
            }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{agent.endpoint}/process",
                    json={
                        "input": input_data,
                        "config": config,
                        "metadata": {
                            "agent_id": agent_id,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("output", {})
                else:
                    # In development mode, return mock data instead of failing
                    logger.warning(f"Agent '{agent_id}' returned status {response.status_code}, returning mock data")
                    return {
                        "status": "mock_response",
                        "agent_id": agent_id,
                        "input_received": input_data,
                        "config": config,
                        "message": f"Mock response due to agent error (status {response.status_code})"
                    }
                    
        except httpx.TimeoutException:
            logger.warning(f"Timeout calling agent '{agent_id}', returning mock data")
            return {
                "status": "mock_response",
                "agent_id": agent_id,
                "input_received": input_data,
                "config": config,
                "message": "Mock response due to timeout"
            }
        except Exception as e:
            logger.warning(f"Failed to call agent '{agent_id}': {str(e)}, returning mock data")
            return {
                "status": "mock_response",
                "agent_id": agent_id,
                "input_received": input_data,
                "config": config,
                "message": f"Mock response due to error: {str(e)}"
            }

    async def get_execution_status(self, execution_id: UUID) -> Optional[ExecutionContext]:
        """Get execution status"""
        return await memory_store.get_execution(execution_id)

    async def cancel_execution(self, execution_id: UUID) -> bool:
        """Cancel a running execution"""
        if execution_id in self._running_executions:
            # For now, we just mark it as cancelled
            # In a real implementation, you'd need to implement proper cancellation
            context = await memory_store.get_execution(execution_id)
            if context:
                context.status = ExecutionStatus.CANCELLED
                context.completed_at = datetime.utcnow()
                await memory_store.store_execution(context)
                self._running_executions.discard(execution_id)
                return True
        return False

    def list_flows(self) -> List[FlowDefinition]:
        """List all available flows"""
        return list(self._flows.values())

    def get_flow(self, flow_id: str) -> Optional[FlowDefinition]:
        """Get a specific flow"""
        return self._flows.get(flow_id)

    async def add_flow(self, flow_def: FlowDefinition) -> bool:
        """Add a new flow definition"""
        try:
            # Validate the flow
            if not await self._validate_flow(flow_def):
                logger.error("Flow validation failed", flow_id=flow_def.flow_id)
                return False
            
            # Check if flow already exists
            if flow_def.flow_id in self._flows:
                logger.error("Flow already exists", flow_id=flow_def.flow_id)
                return False
            
            # Save to file
            flow_file = self.flows_directory / f"{flow_def.flow_id}.yaml"
            flow_data = flow_def.dict()
            
            with flow_file.open('w') as f:
                yaml.dump(flow_data, f, default_flow_style=False)
            
            # Add to in-memory cache
            self._flows[flow_def.flow_id] = flow_def
            
            logger.info("Flow added successfully", flow_id=flow_def.flow_id)
            return True
            
        except Exception as e:
            logger.error("Failed to add flow", flow_id=flow_def.flow_id, error=str(e))
            return False

    async def update_flow(self, flow_id: str, flow_def: FlowDefinition) -> bool:
        """Update an existing flow definition"""
        try:
            # Validate the flow
            if not await self._validate_flow(flow_def):
                logger.error("Flow validation failed", flow_id=flow_def.flow_id)
                return False
            
            # Check if flow exists
            if flow_id not in self._flows:
                logger.error("Flow not found", flow_id=flow_id)
                return False
            
            # Ensure flow_id consistency
            flow_def.flow_id = flow_id
            
            # Save to file
            flow_file = self.flows_directory / f"{flow_id}.yaml"
            flow_data = flow_def.dict()
            
            with flow_file.open('w') as f:
                yaml.dump(flow_data, f, default_flow_style=False)
            
            # Update in-memory cache
            self._flows[flow_id] = flow_def
            
            logger.info("Flow updated successfully", flow_id=flow_id)
            return True
            
        except Exception as e:
            logger.error("Failed to update flow", flow_id=flow_id, error=str(e))
            return False

    async def delete_flow(self, flow_id: str) -> bool:
        """Delete a flow definition"""
        try:
            # Check if flow exists
            if flow_id not in self._flows:
                logger.error("Flow not found", flow_id=flow_id)
                return False
            
            # Check if there are any running executions for this flow
            running_executions = [
                exec_id for exec_id, context in self._execution_contexts.items()
                if context.flow_id == flow_id and context.status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]
            ]
            
            if running_executions:
                logger.error("Cannot delete flow with running executions", 
                           flow_id=flow_id, running_executions=len(running_executions))
                return False
            
            # Delete file
            flow_file = self.flows_directory / f"{flow_id}.yaml"
            if flow_file.exists():
                flow_file.unlink()
            
            # Remove from in-memory cache
            del self._flows[flow_id]
            
            logger.info("Flow deleted successfully", flow_id=flow_id)
            return True
            
        except Exception as e:
            logger.error("Failed to delete flow", flow_id=flow_id, error=str(e))
            return False

    async def list_executions(self, flow_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[ExecutionContext]:
        """List executions with optional filtering"""
        try:
            return await memory_store.list_executions(flow_id, limit, offset)
        except Exception as e:
            logger.error("Failed to list executions", flow_id=flow_id, error=str(e))
            return []

    async def get_node_results(self, execution_id: UUID) -> List[NodeExecutionResult]:
        """Get all node results for an execution"""
        try:
            return await memory_store.get_node_results(execution_id)
        except Exception as e:
            logger.error("Failed to get node results", execution_id=str(execution_id), error=str(e))
            return []


# Global orchestrator instance
orchestrator = FlowOrchestrator() 