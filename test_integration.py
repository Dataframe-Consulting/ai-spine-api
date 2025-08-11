#!/usr/bin/env python3
"""
AI Spine Integration Test Script
Tests the complete functionality of the AI Spine platform
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import requests
import time
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

class AISpineIntegrationTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.api_key = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        self.test_results.append({
            "test": test_name,
            "success": success,
            "details": details
        })

    async def test_health_check(self):
        """Test basic health check"""
        try:
            response = requests.get(f"{self.base_url}/health")
            success = response.status_code == 200
            self.log_test("Health Check", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False

    async def test_auth_status(self):
        """Test authentication status"""
        try:
            response = requests.get(f"{self.base_url}/auth/status")
            success = response.status_code == 200
            if success:
                data = response.json()
                auth_required = data.get("api_key_required", False)
                if not auth_required:
                    self.api_key = "anonymous"
                self.log_test("Authentication Status", success, 
                            f"Auth required: {auth_required}")
            else:
                self.log_test("Authentication Status", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Authentication Status", False, str(e))
            return False

    def make_request(self, method: str, endpoint: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None):
        """Make authenticated request"""
        headers = {}
        if self.api_key and self.api_key != "anonymous":
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        url = f"{self.base_url}{endpoint}"
        
        if method == "GET":
            return requests.get(url, headers=headers, params=params)
        elif method == "POST":
            return requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            return requests.put(url, headers=headers, json=data)
        elif method == "DELETE":
            return requests.delete(url, headers=headers)

    async def test_list_agents(self):
        """Test listing agents"""
        try:
            response = self.make_request("GET", "/agents")
            success = response.status_code == 200
            if success:
                data = response.json()
                agent_count = data.get("count", 0)
                self.log_test("List Agents", success, f"Found {agent_count} agents")
            else:
                self.log_test("List Agents", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("List Agents", False, str(e))
            return False

    async def test_list_flows(self):
        """Test listing flows"""
        try:
            response = self.make_request("GET", "/flows")
            success = response.status_code == 200
            if success:
                data = response.json()
                flow_count = data.get("count", 0)
                self.log_test("List Flows", success, f"Found {flow_count} flows")
            else:
                self.log_test("List Flows", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("List Flows", False, str(e))
            return False

    async def test_system_status(self):
        """Test system status endpoint"""
        try:
            response = self.make_request("GET", "/status")
            success = response.status_code == 200
            if success:
                data = response.json()
                status = data.get("status", "unknown")
                self.log_test("System Status", success, f"Status: {status}")
            else:
                self.log_test("System Status", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("System Status", False, str(e))
            return False

    async def test_metrics(self):
        """Test metrics endpoint"""
        try:
            response = self.make_request("GET", "/metrics")
            success = response.status_code == 200
            if success:
                data = response.json()
                total_executions = data.get("total_executions", 0)
                self.log_test("Metrics", success, f"Total executions: {total_executions}")
            else:
                self.log_test("Metrics", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Metrics", False, str(e))
            return False

    async def test_create_flow(self):
        """Test creating a flow"""
        try:
            test_flow = {
                "flow_id": "test_integration_flow",
                "name": "Test Integration Flow",
                "description": "Flow created for integration testing",
                "version": "1.0.0",
                "nodes": [
                    {
                        "id": "input_node",
                        "agent_id": "zoe",
                        "type": "input",
                        "depends_on": [],
                        "config": {
                            "system_prompt": "Test input node",
                            "timeout": 30
                        }
                    },
                    {
                        "id": "output_node",
                        "type": "output",
                        "depends_on": ["input_node"],
                        "config": {}
                    }
                ],
                "entry_point": "input_node",
                "exit_points": ["output_node"],
                "metadata": {"test": True}
            }
            
            response = self.make_request("POST", "/flows", data=test_flow)
            success = response.status_code == 200
            self.log_test("Create Flow", success, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Create Flow", False, str(e))
            return False

    async def test_flow_execution(self):
        """Test executing a flow"""
        try:
            # First, try to execute an existing flow
            execution_request = {
                "flow_id": "credit_analysis",
                "input_data": {
                    "user_name": "Test User",
                    "requested_amount": 50000,
                    "monthly_income": 10000
                },
                "metadata": {"test": True}
            }
            
            response = self.make_request("POST", "/flows/execute", data=execution_request)
            success = response.status_code == 200
            if success:
                data = response.json()
                execution_id = data.get("execution_id")
                self.log_test("Flow Execution", success, f"Execution ID: {execution_id}")
                return execution_id
            else:
                self.log_test("Flow Execution", False, f"Status: {response.status_code}")
                return None
        except Exception as e:
            self.log_test("Flow Execution", False, str(e))
            return None

    async def test_execution_status(self, execution_id: str):
        """Test getting execution status"""
        try:
            response = self.make_request("GET", f"/executions/{execution_id}")
            success = response.status_code == 200
            if success:
                data = response.json()
                status = data.get("status", "unknown")
                self.log_test("Execution Status", success, f"Status: {status}")
            else:
                self.log_test("Execution Status", False, f"Status: {response.status_code}")
            return success
        except Exception as e:
            self.log_test("Execution Status", False, str(e))
            return False

    async def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting AI Spine Integration Tests")
        print("=" * 50)
        
        # Basic connectivity tests
        if not await self.test_health_check():
            print("❌ Cannot connect to AI Spine. Make sure the server is running!")
            return False
        
        await self.test_auth_status()
        
        # Core functionality tests
        await self.test_list_agents()
        await self.test_list_flows()
        await self.test_system_status()
        await self.test_metrics()
        
        # Flow management tests
        await self.test_create_flow()
        
        # Execution tests (may fail if agents are not available)
        execution_id = await self.test_flow_execution()
        if execution_id:
            # Wait a bit for execution to start
            await asyncio.sleep(2)
            await self.test_execution_status(execution_id)
        
        # Print summary
        print("\n" + "=" * 50)
        print("📊 Test Summary:")
        
        passed = sum(1 for result in self.test_results if result["success"])
        total = len(self.test_results)
        
        print(f"   Total Tests: {total}")
        print(f"   Passed: {passed}")
        print(f"   Failed: {total - passed}")
        print(f"   Success Rate: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("\n🎉 All tests passed! AI Spine is fully functional.")
        else:
            print("\n⚠️  Some tests failed. Check the details above.")
            
        return passed == total

async def main():
    """Main test runner"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Spine Integration Test")
    parser.add_argument("--url", default="http://localhost:8000", 
                       help="AI Spine API URL (default: http://localhost:8000)")
    
    args = parser.parse_args()
    
    tester = AISpineIntegrationTest(args.url)
    success = await tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())