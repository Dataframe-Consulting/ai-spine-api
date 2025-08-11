import httpx
import uuid
import secrets
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from .models import (
    MarketplaceAgent, MarketplacePurchase, MarketplaceUsage, 
    MarketplaceReview, MarketplacePayout, AgentHealthCheck,
    AgentExecuteRequest, AgentExecuteResponse
)

class MarketplaceService:
    def __init__(self, db: Session):
        self.db = db

    async def publish_agent(self, agent_data: Dict[str, Any]) -> MarketplaceAgent:
        """Publish a new agent to the marketplace"""
        
        # Validate agent endpoint
        health_check = await self._validate_agent_endpoint(agent_data["endpoint"])
        if not health_check["ready"]:
            raise ValueError("Agent endpoint is not ready")
        
        # Create marketplace agent
        agent = MarketplaceAgent(
            id=uuid.uuid4(),
            name=agent_data["name"],
            description=agent_data["description"],
            endpoint=agent_data["endpoint"],
            price_per_call=agent_data["price_per_call"],
            owner_id=uuid.UUID(agent_data["owner_id"]),
            capabilities=agent_data.get("capabilities", []),
            tags=agent_data.get("tags", []),
            version=agent_data.get("version", "v1.0"),
            status="active"
        )
        
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        
        return agent

    async def get_agents(
        self, 
        tag: Optional[str] = None,
        capability: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0
    ) -> List[MarketplaceAgent]:
        """Get marketplace agents with filtering and sorting"""
        
        query = self.db.query(MarketplaceAgent).filter(
            MarketplaceAgent.status == "active"
        )
        
        if tag:
            query = query.filter(MarketplaceAgent.tags.contains([tag]))
        
        if capability:
            query = query.filter(MarketplaceAgent.capabilities.contains([capability]))
        
        # Sorting
        if sort_by == "price":
            order_col = MarketplaceAgent.price_per_call
        elif sort_by == "rating":
            order_col = MarketplaceAgent.rating
        elif sort_by == "popularity":
            order_col = MarketplaceAgent.total_calls
        else:
            order_col = MarketplaceAgent.created_at
        
        if sort_order == "desc":
            query = query.order_by(desc(order_col))
        else:
            query = query.order_by(order_col)
        
        return query.offset(offset).limit(limit).all()

    async def get_agent_by_id(self, agent_id: str) -> Optional[MarketplaceAgent]:
        """Get a specific marketplace agent"""
        return self.db.query(MarketplaceAgent).filter(
            MarketplaceAgent.id == uuid.UUID(agent_id)
        ).first()

    async def purchase_agent_access(
        self, 
        agent_id: str, 
        buyer_id: str,
        credits: int = 100
    ) -> MarketplacePurchase:
        """Purchase access to a marketplace agent"""
        
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        
        if agent.status != "active":
            raise ValueError("Agent is not available for purchase")
        
        # Generate API key
        api_key = f"mk_{secrets.token_urlsafe(32)}"
        
        # Create purchase record
        purchase = MarketplacePurchase(
            id=uuid.uuid4(),
            agent_id=uuid.UUID(agent_id),
            buyer_id=uuid.UUID(buyer_id),
            api_key=api_key,
            status="active",
            credits_remaining=credits,
            expires_at=datetime.utcnow() + timedelta(days=365)  # 1 year
        )
        
        self.db.add(purchase)
        self.db.commit()
        self.db.refresh(purchase)
        
        return purchase

    async def execute_marketplace_agent(
        self,
        agent_id: str,
        buyer_id: str,
        execution_id: str,
        node_id: str,
        input_data: Dict[str, Any],
        config: Dict[str, Any]
    ) -> AgentExecuteResponse:
        """Execute a marketplace agent"""
        
        # Get agent and validate purchase
        agent = await self.get_agent_by_id(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        
        purchase = self.db.query(MarketplacePurchase).filter(
            and_(
                MarketplacePurchase.agent_id == uuid.UUID(agent_id),
                MarketplacePurchase.buyer_id == uuid.UUID(buyer_id),
                MarketplacePurchase.status == "active"
            )
        ).first()
        
        if not purchase:
            raise ValueError("No active purchase found for this agent")
        
        if purchase.credits_remaining <= 0:
            raise ValueError("No credits remaining")
        
        # Execute agent
        start_time = datetime.utcnow()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{agent.endpoint}/execute",
                    json={
                        "execution_id": execution_id,
                        "node_id": node_id,
                        "input": input_data,
                        "config": config
                    },
                    headers={"Authorization": f"Bearer {purchase.api_key}"}
                )
                
                response_time = (datetime.utcnow() - start_time).total_seconds()
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Log usage
                    usage = MarketplaceUsage(
                        id=uuid.uuid4(),
                        execution_id=execution_id,
                        agent_id=uuid.UUID(agent_id),
                        buyer_id=uuid.UUID(buyer_id),
                        purchase_id=purchase.id,
                        cost_charged=agent.price_per_call,
                        response_time=response_time,
                        status="success"
                    )
                    
                    # Update credits
                    purchase.credits_remaining -= 1
                    agent.total_calls += 1
                    
                    self.db.add(usage)
                    self.db.commit()
                    
                    return AgentExecuteResponse(**result)
                else:
                    # Log failed usage
                    usage = MarketplaceUsage(
                        id=uuid.uuid4(),
                        execution_id=execution_id,
                        agent_id=uuid.UUID(agent_id),
                        buyer_id=uuid.UUID(buyer_id),
                        purchase_id=purchase.id,
                        cost_charged=0,
                        response_time=response_time,
                        status="error"
                    )
                    
                    self.db.add(usage)
                    self.db.commit()
                    
                    raise ValueError(f"Agent execution failed: {response.text}")
                    
        except Exception as e:
            # Log error usage
            usage = MarketplaceUsage(
                id=uuid.uuid4(),
                execution_id=execution_id,
                agent_id=uuid.UUID(agent_id),
                buyer_id=uuid.UUID(buyer_id),
                purchase_id=purchase.id,
                cost_charged=0,
                response_time=(datetime.utcnow() - start_time).total_seconds(),
                status="error"
            )
            
            self.db.add(usage)
            self.db.commit()
            
            raise e

    async def add_review(
        self,
        agent_id: str,
        reviewer_id: str,
        rating: int,
        comment: Optional[str] = None
    ) -> MarketplaceReview:
        """Add a review to a marketplace agent"""
        
        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5")
        
        # Check if user has purchased this agent
        purchase = self.db.query(MarketplacePurchase).filter(
            and_(
                MarketplacePurchase.agent_id == uuid.UUID(agent_id),
                MarketplacePurchase.buyer_id == uuid.UUID(reviewer_id),
                MarketplacePurchase.status == "active"
            )
        ).first()
        
        if not purchase:
            raise ValueError("You must purchase this agent before reviewing it")
        
        # Create review
        review = MarketplaceReview(
            id=uuid.uuid4(),
            agent_id=uuid.UUID(agent_id),
            reviewer_id=uuid.UUID(reviewer_id),
            rating=rating,
            comment=comment
        )
        
        self.db.add(review)
        
        # Update agent rating
        agent = await self.get_agent_by_id(agent_id)
        if agent:
            # Recalculate average rating
            reviews = self.db.query(MarketplaceReview).filter(
                MarketplaceReview.agent_id == uuid.UUID(agent_id)
            ).all()
            
            if reviews:
                total_rating = sum(r.rating for r in reviews)
                agent.rating = total_rating / len(reviews)
                agent.total_reviews = len(reviews)
        
        self.db.commit()
        self.db.refresh(review)
        
        return review

    async def get_agent_reviews(self, agent_id: str, limit: int = 10) -> List[MarketplaceReview]:
        """Get reviews for a marketplace agent"""
        return self.db.query(MarketplaceReview).filter(
            MarketplaceReview.agent_id == uuid.UUID(agent_id)
        ).order_by(desc(MarketplaceReview.created_at)).limit(limit).all()

    async def get_user_purchases(self, buyer_id: str) -> List[MarketplacePurchase]:
        """Get all purchases for a user"""
        return self.db.query(MarketplacePurchase).filter(
            and_(
                MarketplacePurchase.buyer_id == uuid.UUID(buyer_id),
                MarketplacePurchase.status == "active"
            )
        ).all()

    async def _validate_agent_endpoint(self, endpoint: str) -> Dict[str, Any]:
        """Validate agent endpoint by calling health check"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{endpoint}/health")
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"ready": False, "error": f"Health check failed: {response.status_code}"}
                    
        except Exception as e:
            return {"ready": False, "error": str(e)}

    async def calculate_payouts(self, owner_id: str) -> List[MarketplacePayout]:
        """Calculate payouts for an agent owner"""
        # This would integrate with Stripe for actual payments
        # For now, we'll just create payout records
        
        # Get all usage for this owner's agents
        usage = self.db.query(MarketplaceUsage).join(
            MarketplaceAgent
        ).filter(
            MarketplaceAgent.owner_id == uuid.UUID(owner_id)
        ).all()
        
        payouts = []
        for usage_record in usage:
            agent = await self.get_agent_by_id(str(usage_record.agent_id))
            if agent and usage_record.cost_charged > 0:
                commission_rate = 0.10  # 10% commission
                net_amount = usage_record.cost_charged * (1 - commission_rate)
                
                payout = MarketplacePayout(
                    id=uuid.uuid4(),
                    agent_id=usage_record.agent_id,
                    owner_id=uuid.UUID(owner_id),
                    amount=usage_record.cost_charged,
                    commission_rate=commission_rate,
                    net_amount=net_amount,
                    status="pending"
                )
                
                payouts.append(payout)
        
        return payouts 