from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from ..core.marketplace import MarketplaceService
from ..core.models import (
    MarketplaceAgentCreate, MarketplaceAgentResponse,
    MarketplacePurchaseCreate, MarketplaceReviewCreate
)
# Marketplace database functionality disabled for now
# from ..core.database import get_db_session

router = APIRouter(prefix="/marketplace", tags=["marketplace"])

@router.post("/agents", response_model=MarketplaceAgentResponse)
async def publish_agent(
    agent_data: MarketplaceAgentCreate
    # db: Session = Depends(get_db_session)  # Disabled for now
):
    """Publish a new agent to the marketplace"""
    try:
        service = MarketplaceService(db)
        agent = await service.publish_agent(agent_data.dict())
        
        return MarketplaceAgentResponse(
            id=str(agent.id),
            name=agent.name,
            description=agent.description,
            endpoint=agent.endpoint,
            price_per_call=agent.price_per_call,
            owner_id=str(agent.owner_id),
            capabilities=agent.capabilities,
            tags=agent.tags,
            version=agent.version,
            status=agent.status,
            rating=agent.rating,
            total_reviews=agent.total_reviews,
            total_calls=agent.total_calls,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish agent: {str(e)}")

@router.get("/agents", response_model=List[MarketplaceAgentResponse])
async def get_marketplace_agents(
    tag: Optional[str] = Query(None, description="Filter by tag"),
    capability: Optional[str] = Query(None, description="Filter by capability"),
    sort_by: str = Query("created_at", description="Sort by: created_at, price, rating, popularity"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    limit: int = Query(50, ge=1, le=100, description="Number of agents to return"),
    offset: int = Query(0, ge=0, description="Number of agents to skip"),
    db: Session = Depends(get_db)
):
    """Get marketplace agents with filtering and sorting"""
    try:
        service = MarketplaceService(db)
        agents = await service.get_agents(
            tag=tag,
            capability=capability,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset
        )
        
        return [
            MarketplaceAgentResponse(
                id=str(agent.id),
                name=agent.name,
                description=agent.description,
                endpoint=agent.endpoint,
                price_per_call=agent.price_per_call,
                owner_id=str(agent.owner_id),
                capabilities=agent.capabilities,
                tags=agent.tags,
                version=agent.version,
                status=agent.status,
                rating=agent.rating,
                total_reviews=agent.total_reviews,
                total_calls=agent.total_calls,
                created_at=agent.created_at,
                updated_at=agent.updated_at
            )
            for agent in agents
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agents: {str(e)}")

@router.get("/agents/{agent_id}", response_model=MarketplaceAgentResponse)
async def get_marketplace_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific marketplace agent"""
    try:
        service = MarketplaceService(db)
        agent = await service.get_agent_by_id(agent_id)
        
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        return MarketplaceAgentResponse(
            id=str(agent.id),
            name=agent.name,
            description=agent.description,
            endpoint=agent.endpoint,
            price_per_call=agent.price_per_call,
            owner_id=str(agent.owner_id),
            capabilities=agent.capabilities,
            tags=agent.tags,
            version=agent.version,
            status=agent.status,
            rating=agent.rating,
            total_reviews=agent.total_reviews,
            total_calls=agent.total_calls,
            created_at=agent.created_at,
            updated_at=agent.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent: {str(e)}")

@router.post("/agents/{agent_id}/purchase")
async def purchase_agent_access(
    agent_id: str,
    purchase_data: MarketplacePurchaseCreate,
    db: Session = Depends(get_db)
):
    """Purchase access to a marketplace agent"""
    try:
        service = MarketplaceService(db)
        purchase = await service.purchase_agent_access(
            agent_id=agent_id,
            buyer_id=purchase_data.buyer_id,
            credits=purchase_data.credits_remaining
        )
        
        return {
            "purchase_id": str(purchase.id),
            "agent_id": str(purchase.agent_id),
            "buyer_id": str(purchase.buyer_id),
            "api_key": purchase.api_key,
            "status": purchase.status,
            "credits_remaining": purchase.credits_remaining,
            "expires_at": purchase.expires_at,
            "created_at": purchase.created_at
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to purchase agent: {str(e)}")

@router.post("/agents/{agent_id}/review")
async def add_agent_review(
    agent_id: str,
    review_data: MarketplaceReviewCreate,
    db: Session = Depends(get_db)
):
    """Add a review to a marketplace agent"""
    try:
        service = MarketplaceService(db)
        review = await service.add_review(
            agent_id=agent_id,
            reviewer_id=review_data.reviewer_id,
            rating=review_data.rating,
            comment=review_data.comment
        )
        
        return {
            "review_id": str(review.id),
            "agent_id": str(review.agent_id),
            "reviewer_id": str(review.reviewer_id),
            "rating": review.rating,
            "comment": review.comment,
            "created_at": review.created_at
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add review: {str(e)}")

@router.get("/agents/{agent_id}/reviews")
async def get_agent_reviews(
    agent_id: str,
    limit: int = Query(10, ge=1, le=50, description="Number of reviews to return"),
    db: Session = Depends(get_db)
):
    """Get reviews for a marketplace agent"""
    try:
        service = MarketplaceService(db)
        reviews = await service.get_agent_reviews(agent_id, limit=limit)
        
        return [
            {
                "review_id": str(review.id),
                "agent_id": str(review.agent_id),
                "reviewer_id": str(review.reviewer_id),
                "rating": review.rating,
                "comment": review.comment,
                "created_at": review.created_at
            }
            for review in reviews
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get reviews: {str(e)}")

@router.get("/users/{user_id}/purchases")
async def get_user_purchases(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get all purchases for a user"""
    try:
        service = MarketplaceService(db)
        purchases = await service.get_user_purchases(user_id)
        
        return [
            {
                "purchase_id": str(purchase.id),
                "agent_id": str(purchase.agent_id),
                "buyer_id": str(purchase.buyer_id),
                "status": purchase.status,
                "credits_remaining": purchase.credits_remaining,
                "expires_at": purchase.expires_at,
                "created_at": purchase.created_at
            }
            for purchase in purchases
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get purchases: {str(e)}")

@router.post("/agents/{agent_id}/test")
async def test_marketplace_agent(
    agent_id: str,
    test_data: dict,
    db: Session = Depends(get_db)
):
    """Test a marketplace agent with sample data"""
    try:
        service = MarketplaceService(db)
        
        # This would require a valid purchase, but for testing we'll use a mock
        # In production, you'd validate the user has purchased this agent
        
        result = await service.execute_marketplace_agent(
            agent_id=agent_id,
            buyer_id="test-user",  # Mock user for testing
            execution_id="test-execution",
            node_id="test-node",
            input_data=test_data.get("input", {}),
            config=test_data.get("config", {})
        )
        
        return {
            "status": "success",
            "result": result.dict(),
            "message": "Agent test completed successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test agent: {str(e)}") 