#!/usr/bin/env python3
"""
Demo script for AI Spine - Credit Analysis Flow
This script demonstrates how to interact with the AI Spine API
"""

import asyncio
import json
import time
import httpx
import structlog
from typing import Dict, Any

logger = structlog.get_logger(__name__)


class AISpineDemo:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.client = httpx.AsyncClient()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    async def check_health(self) -> bool:
        """Check if the API is healthy"""
        try:
            response = await self.client.get(f"{self.api_url}/health")
            if response.status_code == 200:
                logger.info("API is healthy", status=response.json())
                return True
            else:
                logger.error("API health check failed", status_code=response.status_code)
                return False
        except Exception as e:
            logger.error("Failed to check API health", error=str(e))
            return False

    async def list_flows(self):
        """List all available flows"""
        try:
            response = await self.client.get(f"{self.api_url}/flows")
            if response.status_code == 200:
                flows = response.json()
                logger.info("Available flows", flows=flows)
                return flows
            else:
                logger.error("Failed to list flows", status_code=response.status_code)
                return None
        except Exception as e:
            logger.error("Failed to list flows", error=str(e))
            return None

    async def list_agents(self):
        """List all registered agents"""
        try:
            response = await self.client.get(f"{self.api_url}/agents")
            if response.status_code == 200:
                agents = response.json()
                logger.info("Registered agents", agents=agents)
                return agents
            else:
                logger.error("Failed to list agents", status_code=response.status_code)
                return None
        except Exception as e:
            logger.error("Failed to list agents", error=str(e))
            return None

    async def execute_credit_analysis(self, user_input: dict) -> str:
        """Execute the credit analysis flow"""
        try:
            request_data = {
                "flow_id": "credit_analysis",
                "input_data": user_input,
                "metadata": {
                    "source": "demo_script",
                    "timestamp": time.time()
                }
            }
            
            response = await self.client.post(
                f"{self.api_url}/flows/execute",
                json=request_data
            )
            
            if response.status_code == 200:
                result = response.json()
                execution_id = result["execution_id"]
                logger.info("Flow execution started", execution_id=execution_id, status=result["status"])
                return execution_id
            else:
                logger.error("Failed to execute flow", status_code=response.status_code, response=response.text)
                return None
        except Exception as e:
            logger.error("Failed to execute credit analysis", error=str(e))
            return None

    async def monitor_execution(self, execution_id: str, max_wait: int = 300):
        """Monitor execution status"""
        try:
            start_time = time.time()
            while time.time() - start_time < max_wait:
                response = await self.client.get(f"{self.api_url}/executions/{execution_id}")
                
                if response.status_code == 200:
                    execution = response.json()
                    status = execution["status"]
                    logger.info("Execution status", execution_id=execution_id, status=status)
                    
                    if status in ["completed", "failed", "cancelled"]:
                        logger.info("Execution finished", execution_id=execution_id, status=status)
                        if status == "completed":
                            logger.info("Execution result", result=execution.get("output_data"))
                        elif status == "failed":
                            logger.error("Execution failed", error=execution.get("error_message"))
                        return execution
                    
                    await asyncio.sleep(2)  # Wait 2 seconds before next check
                else:
                    logger.error("Failed to get execution status", status_code=response.status_code)
                    return None
            
            logger.warning("Execution monitoring timeout", execution_id=execution_id)
            return None
        except Exception as e:
            logger.error("Failed to monitor execution", execution_id=execution_id, error=str(e))
            return None

    async def get_execution_messages(self, execution_id: str):
        """Get messages for an execution"""
        try:
            response = await self.client.get(f"{self.api_url}/messages/{execution_id}")
            if response.status_code == 200:
                messages = response.json()
                logger.info("Execution messages", messages=messages)
                return messages
            else:
                logger.error("Failed to get messages", status_code=response.status_code)
                return None
        except Exception as e:
            logger.error("Failed to get execution messages", error=str(e))
            return None

    async def get_system_stats(self):
        """Get system statistics"""
        try:
            response = await self.client.get(f"{self.api_url}/status")
            if response.status_code == 200:
                stats = response.json()
                logger.info("System status", stats=stats)
                return stats
            else:
                logger.error("Failed to get system stats", status_code=response.status_code)
                return None
        except Exception as e:
            logger.error("Failed to get system stats", error=str(e))
            return None


async def main():
    """Main demo function"""
    logger.info("Starting AI Spine Demo")
    
    async with AISpineDemo() as demo:
        # Check API health
        if not await demo.check_health():
            logger.error("API is not healthy, exiting")
            return
        
        # Get system status
        await demo.get_system_stats()
        
        # List available flows
        flows = await demo.list_flows()
        if not flows:
            logger.error("No flows available")
            return
        
        # List registered agents
        agents = await demo.list_agents()
        if not agents:
            logger.error("No agents registered")
            return
        
        # Execute credit analysis flow
        user_input = {
            "user_query": "Quiero solicitar un préstamo de $50,000",
            "user_info": {
                "name": "Juan Pérez",
                "email": "juan.perez@email.com"
            },
            "initial_context": "El usuario está interesado en un préstamo personal"
        }
        
        execution_id = await demo.execute_credit_analysis(user_input)
        if not execution_id:
            logger.error("Failed to start execution")
            return
        
        # Monitor execution
        result = await demo.monitor_execution(execution_id)
        if result:
            logger.info("Demo completed successfully", result=result)
        
        # Get execution messages
        await demo.get_execution_messages(execution_id)


if __name__ == "__main__":
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    asyncio.run(main()) 