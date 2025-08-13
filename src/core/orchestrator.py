"""
Flow Orchestrator - Versión Supabase sin SQLAlchemy
"""
import asyncio
import time
import networkx as nx
import structlog
import yaml
import httpx
from typing import Dict, List, Optional, Any, Set
from uuid import UUID, uuid4
from datetime import datetime
from pathlib import Path

from src.core.models import (
    ExecutionStatus, FlowDefinition, FlowNode,
    NodeExecutionResult, AgentMessagePydantic, ExecutionRequest, ExecutionResponse
)
from src.core.registry import registry
from src.core.communication import communication_manager
from src.core.memory import memory_store

logger = structlog.get_logger(__name__)


class FlowOrchestrator:
    def __init__(self):
        self._flows: Dict[str, FlowDefinition] = {}
        self._executions: Dict[UUID, Dict] = {}  # Diccionarios en lugar de objetos SQLAlchemy
        self._running_executions: Set[UUID] = set()

    async def start(self):
        """Start the orchestrator and load flows"""
        logger.info("Starting Flow Orchestrator")
        await self._load_flows()
        logger.info("Flow Orchestrator started")

    async def _load_flows(self):
        """Load flow definitions from YAML files"""
        flows_dir = Path(__file__).parent.parent.parent / "flows"
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
                        logger.warning("Flow validation failed", flow_id=flow_def.flow_id)
            except Exception as e:
                logger.error("Failed to load flow", file=str(yaml_file), error=str(e))

    async def _validate_flow(self, flow_def: FlowDefinition) -> bool:
        """Validate flow definition"""
        try:
            # Create directed graph
            G = nx.DiGraph()
            
            # Add nodes
            node_ids = {node.id for node in flow_def.nodes}
            for node in flow_def.nodes:
                G.add_node(node.id)
                
                # Validate dependencies
                for dep in node.depends_on:
                    if dep not in node_ids:
                        logger.error("Unknown dependency", node_id=node.id, dependency=dep)
                        return False
                    G.add_edge(dep, node.id)
            
            # Check for cycles
            if not nx.is_directed_acyclic_graph(G):
                logger.error("Flow contains cycles", flow_id=flow_def.flow_id)
                return False
            
            # Validate entry point
            if flow_def.entry_point not in node_ids:
                logger.error("Invalid entry point", flow_id=flow_def.flow_id, entry_point=flow_def.entry_point)
                return False
            
            # Validate exit points
            for exit_point in flow_def.exit_points:
                if exit_point not in node_ids:
                    logger.error("Invalid exit point", flow_id=flow_def.flow_id, exit_point=exit_point)
                    return False
            
            return True
        except Exception as e:
            logger.error("Flow validation error", flow_id=flow_def.flow_id, error=str(e))
            return False

    async def stop(self):
        """Stop the orchestrator"""
        logger.info("Stopping Flow Orchestrator")
        
        # Cancel running executions
        for execution_id in self._running_executions.copy():
            await self.cancel_execution(execution_id)
        
        logger.info("Flow Orchestrator stopped")

    async def execute_flow(self, request: ExecutionRequest) -> ExecutionResponse:
        """Execute a flow based on request"""
        try:
            if request.flow_id not in self._flows:
                return ExecutionResponse(
                    execution_id=UUID('00000000-0000-0000-0000-000000000000'),
                    status=ExecutionStatus.FAILED,
                    error=f"Flow '{request.flow_id}' not found"
                )
            
            flow_def = self._flows[request.flow_id]
            
            # Create execution context as dictionary
            execution_id = uuid4()
            context = {
                "execution_id": str(execution_id),
                "flow_id": request.flow_id,
                "status": ExecutionStatus.PENDING.value,
                "input_data": request.input_data,
                "output_data": {},
                "metadata": request.metadata or {},
                "user_id": request.user_id,
                "priority": request.priority,
                "timeout": request.timeout,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            
            # Store execution context
            await memory_store.store_execution(context)
            self._executions[execution_id] = context
            
            # Start async execution
            asyncio.create_task(self._execute_flow_async(execution_id, flow_def))
            
            logger.info("Flow execution started", execution_id=str(execution_id), flow_id=request.flow_id)
            
            return ExecutionResponse(
                execution_id=execution_id,
                status=ExecutionStatus.PENDING
            )
        except Exception as e:
            logger.error("Failed to start flow execution", flow_id=request.flow_id, error=str(e))
            return ExecutionResponse(
                execution_id=UUID('00000000-0000-0000-0000-000000000000'),
                status=ExecutionStatus.FAILED,
                error=f"Failed to start execution: {str(e)}"
            )

    async def _execute_flow_async(self, execution_id: UUID, flow_def: FlowDefinition):
        """Execute flow asynchronously"""
        context = self._executions.get(execution_id)
        if not context:
            logger.error("Execution context not found", execution_id=str(execution_id))
            return
            
        try:
            self._running_executions.add(execution_id)
            
            # Update status to running
            await memory_store.update_execution_status(execution_id, ExecutionStatus.RUNNING.value)
            context["status"] = ExecutionStatus.RUNNING.value
            context["started_at"] = datetime.utcnow().isoformat()
            
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
                input_data = context["input_data"].copy()
                for dep in node.depends_on:
                    if dep in node_results:
                        input_data.update(node_results[dep].get("output_data", {}))
                
                # Execute node
                result = await self._execute_node(execution_id, node, input_data)
                node_results[node_id] = result
                
                # Store result
                await memory_store.store_node_result(result)
                
                # Check if execution should continue
                if result.get("status") == ExecutionStatus.FAILED.value:
                    await memory_store.update_execution_status(
                        execution_id, 
                        ExecutionStatus.FAILED.value,
                        error_message=result.get("error_message")
                    )
                    context["status"] = ExecutionStatus.FAILED.value
                    context["error_message"] = result.get("error_message")
                    break
            
            # Update final status
            if context["status"] != ExecutionStatus.FAILED.value:
                # Prepare output data
                output_data = {}
                for exit_point in flow_def.exit_points:
                    if exit_point in node_results:
                        output_data[exit_point] = node_results[exit_point].get("output_data", {})
                
                await memory_store.update_execution_status(
                    execution_id,
                    ExecutionStatus.COMPLETED.value,
                    output_data=output_data
                )
                context["status"] = ExecutionStatus.COMPLETED.value
                context["output_data"] = output_data
                context["completed_at"] = datetime.utcnow().isoformat()
            
            logger.info("Flow execution completed", execution_id=str(execution_id), status=context["status"])
            
        except Exception as e:
            logger.error("Flow execution failed", execution_id=str(execution_id), error=str(e))
            await memory_store.update_execution_status(
                execution_id,
                ExecutionStatus.FAILED.value,
                error_message=str(e)
            )
            context["status"] = ExecutionStatus.FAILED.value
            context["error_message"] = str(e)
            context["completed_at"] = datetime.utcnow().isoformat()
        finally:
            self._running_executions.discard(execution_id)

    async def _execute_node(self, execution_id: UUID, node: FlowNode, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single node"""
        start_time = time.time()
        result = {
            "id": str(uuid4()),
            "execution_id": str(execution_id),
            "node_id": node.id,
            "agent_id": node.agent_id,
            "status": ExecutionStatus.PENDING.value,
            "input_data": input_data,
            "output_data": {},
            "created_at": datetime.utcnow().isoformat()
        }
        
        try:
            # Get agent info
            agent = registry.get_agent(node.agent_id) if node.agent_id else None
            if not agent:
                raise ValueError(f"Agent '{node.agent_id}' not found or not active")
            
            # Prepare request
            request_data = {
                "execution_id": str(execution_id),
                "node_id": node.id,
                "input": input_data,
                "config": node.config
            }
            
            # Call agent endpoint
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{agent.endpoint}/execute",
                    json=request_data
                )
                response.raise_for_status()
                
                response_data = response.json()
                result["output_data"] = response_data.get("output", {})
                result["status"] = ExecutionStatus.COMPLETED.value
            
        except Exception as e:
            logger.error("Node execution failed", node_id=node.id, error=str(e))
            result["status"] = ExecutionStatus.FAILED.value
            result["error_message"] = str(e)
        
        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)
        result["execution_time_ms"] = execution_time_ms
        result["updated_at"] = datetime.utcnow().isoformat()
        
        if result["status"] in [ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value]:
            result["completed_at"] = datetime.utcnow().isoformat()
        
        return result

    async def get_execution_status(self, execution_id: UUID) -> Optional[Dict]:
        """Get execution status"""
        # Try memory first
        if execution_id in self._executions:
            return self._executions[execution_id]
        
        # Try database
        return await memory_store.get_execution(execution_id)

    async def cancel_execution(self, execution_id: UUID) -> bool:
        """Cancel a running execution"""
        if execution_id not in self._running_executions:
            return False
        
        try:
            await memory_store.update_execution_status(
                execution_id,
                ExecutionStatus.CANCELLED.value,
                error_message="Execution cancelled by user"
            )
            
            if execution_id in self._executions:
                self._executions[execution_id]["status"] = ExecutionStatus.CANCELLED.value
            
            self._running_executions.discard(execution_id)
            logger.info("Execution cancelled", execution_id=str(execution_id))
            return True
        except Exception as e:
            logger.error("Failed to cancel execution", execution_id=str(execution_id), error=str(e))
            return False

    async def list_executions(self, flow_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List executions with optional filtering"""
        return await memory_store.list_executions(flow_id, limit, offset)

    async def get_node_results(self, execution_id: UUID) -> List[Dict]:
        """Get node results for an execution"""
        return await memory_store.get_node_results(execution_id)

    def list_flows(self) -> List[FlowDefinition]:
        """List all registered flows"""
        return list(self._flows.values())

    def get_flow(self, flow_id: str) -> Optional[FlowDefinition]:
        """Get a specific flow"""
        return self._flows.get(flow_id)

    async def add_flow(self, flow_def: FlowDefinition) -> bool:
        """Add a new flow"""
        if await self._validate_flow(flow_def):
            self._flows[flow_def.flow_id] = flow_def
            await memory_store.store_flow(flow_def.dict())
            logger.info("Flow added", flow_id=flow_def.flow_id)
            return True
        return False

    async def update_flow(self, flow_id: str, flow_def: FlowDefinition) -> bool:
        """Update an existing flow"""
        if flow_id not in self._flows:
            return False
        
        if await self._validate_flow(flow_def):
            self._flows[flow_id] = flow_def
            await memory_store.store_flow(flow_def.dict())
            logger.info("Flow updated", flow_id=flow_id)
            return True
        return False

    async def delete_flow(self, flow_id: str) -> bool:
        """Delete a flow"""
        if flow_id in self._flows:
            del self._flows[flow_id]
            logger.info("Flow deleted", flow_id=flow_id)
            return True
        return False


# Singleton instance
orchestrator = FlowOrchestrator()