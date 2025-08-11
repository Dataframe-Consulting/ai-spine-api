from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import uuid

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

# Mock data for development
MOCK_AGENTS = [
    {
        "id": str(uuid.uuid4()),
        "name": "GPT-4 Assistant",
        "description": "Advanced conversational AI assistant",
        "price_per_call": 0.03,
        "owner_id": "openai",
        "capabilities": ["conversation", "text_generation", "code_help"],
        "tags": ["ai", "assistant", "gpt"],
        "version": "v1.0",
        "status": "active",
        "rating": 4.8,
        "total_reviews": 1250,
        "total_calls": 50000
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Claude Analytics",
        "description": "Data analysis and insights agent",
        "price_per_call": 0.05,
        "owner_id": "anthropic",
        "capabilities": ["data_analysis", "visualization", "insights"],
        "tags": ["analytics", "data", "claude"],
        "version": "v2.1",
        "status": "active",
        "rating": 4.9,
        "total_reviews": 890,
        "total_calls": 25000
    }
]

@router.get("/agents")
async def list_marketplace_agents(
    search: str = None,
    category: str = None,
    min_rating: float = 0.0,
    max_price: float = None,
    sort_by: str = "rating",
    limit: int = 20,
    offset: int = 0
):
    """List marketplace agents with filtering and pagination"""
    try:
        agents = MOCK_AGENTS.copy()
        
        # Apply filters
        if search:
            agents = [a for a in agents if search.lower() in a["name"].lower() or search.lower() in a["description"].lower()]
        
        if min_rating:
            agents = [a for a in agents if a["rating"] >= min_rating]
        
        if max_price:
            agents = [a for a in agents if a["price_per_call"] <= max_price]
        
        # Apply sorting
        if sort_by == "rating":
            agents.sort(key=lambda x: x["rating"], reverse=True)
        elif sort_by == "price":
            agents.sort(key=lambda x: x["price_per_call"])
        elif sort_by == "popularity":
            agents.sort(key=lambda x: x["total_calls"], reverse=True)
        
        # Apply pagination
        total = len(agents)
        agents = agents[offset:offset + limit]
        
        return {
            "agents": agents,
            "count": len(agents),
            "total": total,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/agents/{agent_id}")
async def get_marketplace_agent(agent_id: str):
    """Get details of a specific marketplace agent"""
    try:
        agent = next((a for a in MOCK_AGENTS if a["id"] == agent_id), None)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agents/{agent_id}/test")
async def test_marketplace_agent(agent_id: str, test_input: Dict[str, Any]):
    """Test a marketplace agent with sample input"""
    try:
        agent = next((a for a in MOCK_AGENTS if a["id"] == agent_id), None)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Mock test response
        return {
            "agent_id": agent_id,
            "agent_name": agent["name"],
            "test_input": test_input,
            "test_output": {
                "message": f"Mock response from {agent['name']} for input: {test_input}",
                "status": "success",
                "execution_time": 0.5
            },
            "cost": agent["price_per_call"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/categories")
async def get_marketplace_categories():
    """Get available marketplace categories"""
    return {
        "categories": [
            "conversation",
            "data_analysis", 
            "text_generation",
            "code_help",
            "translation",
            "image_processing",
            "audio_processing",
            "workflow_automation"
        ]
    }

@router.get("/stats")
async def get_marketplace_stats():
    """Get marketplace statistics"""
    return {
        "total_agents": len(MOCK_AGENTS),
        "active_agents": len([a for a in MOCK_AGENTS if a["status"] == "active"]),
        "total_calls": sum(a["total_calls"] for a in MOCK_AGENTS),
        "average_rating": sum(a["rating"] for a in MOCK_AGENTS) / len(MOCK_AGENTS),
        "categories": 8
    }