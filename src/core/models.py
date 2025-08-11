from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, Float, ForeignKey, JSON, ARRAY
from sqlalchemy.dialects.postgresql import UUID as SQL_UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()

# Enums
class AgentType(str, Enum):
    """Types of agents in the system"""
    INPUT = "input"
    PROCESSOR = "processor" 
    OUTPUT = "output"
    CONDITIONAL = "conditional"

class ExecutionStatus(str, Enum):
    """Status of flow executions"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentCapability(str, Enum):
    """Common agent capabilities"""
    CONVERSATION = "conversation"
    INFORMATION_GATHERING = "information_gathering"
    CREDIT_ANALYSIS = "credit_analysis"
    RISK_ASSESSMENT = "risk_assessment"
    DOCUMENT_PROCESSING = "document_processing"
    DECISION_MAKING = "decision_making"

# Pydantic Models
class AgentInfo(BaseModel):
    """Information about a registered agent"""
    agent_id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[AgentCapability]
    agent_type: AgentType
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class FlowNode(BaseModel):
    """A node in a flow definition"""
    id: str
    agent_id: Optional[str] = None
    type: AgentType
    depends_on: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)
    conditions: Optional[Dict[str, Any]] = None

class FlowDefinition(BaseModel):
    """Complete flow definition"""
    flow_id: str
    name: str
    description: str
    version: str = "1.0.0"
    nodes: List[FlowNode]
    entry_point: str
    exit_points: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionRequest(BaseModel):
    """Request to execute a flow"""
    flow_id: str
    input_data: Dict[str, Any]
    user_id: Optional[str] = None
    priority: int = Field(default=0, ge=0, le=10)
    timeout: Optional[int] = None  # seconds
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ExecutionResponse(BaseModel):
    """Response from flow execution"""
    execution_id: UUID
    status: ExecutionStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None  # seconds
    
    class Config:
        json_encoders = {
            UUID: str
        }

class ExecutionContextResponse(BaseModel):
    """Response model for execution context"""
    execution_id: str
    flow_id: str
    status: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @classmethod
    def from_sqlalchemy(cls, db_obj):
        """Convert SQLAlchemy object to Pydantic model"""
        return cls(
            execution_id=db_obj.execution_id,
            flow_id=db_obj.flow_id,
            status=db_obj.status,
            input_data=db_obj.input_data or {},
            output_data=db_obj.output_data or {},
            created_at=db_obj.created_at,
            updated_at=db_obj.updated_at,
            completed_at=db_obj.completed_at
        )

class Metrics(BaseModel):
    """Execution metrics"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class AgentMessagePydantic(BaseModel):
    """Message passed between agents (Pydantic model)"""
    message_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    from_agent: str
    to_agent: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: str
        }

class Agent(Base):
    __tablename__ = "agents"
    
    agent_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    capabilities = Column(JSON, default=list)
    type = Column(String, default="custom")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExecutionContext(Base):
    __tablename__ = "execution_contexts"
    
    execution_id = Column(String, primary_key=True)
    flow_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

class NodeExecutionResult(Base):
    __tablename__ = "node_execution_results"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("execution_contexts.execution_id"))
    node_id = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending, running, completed, failed
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)

class AgentMessage(Base):
    __tablename__ = "agent_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    execution_id = Column(String, ForeignKey("execution_contexts.execution_id"))
    node_id = Column(String, nullable=False)
    agent_id = Column(String, nullable=False)
    message_type = Column(String, default="request")  # request, response
    content = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow)

# Marketplace Models
class MarketplaceAgent(Base):
    __tablename__ = "marketplace_agents"
    
    id = Column(SQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(Text)
    endpoint = Column(String, nullable=False)
    price_per_call = Column(Float, nullable=False)
    owner_id = Column(SQL_UUID(as_uuid=True), nullable=False)  # References users table
    capabilities = Column(JSON, default=list)
    tags = Column(ARRAY(String), default=list)
    version = Column(String, default="v1.0")
    status = Column(String, default="active")  # active, inactive, suspended
    rating = Column(Float, default=0.0)
    total_reviews = Column(Integer, default=0)
    total_calls = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MarketplacePurchase(Base):
    __tablename__ = "marketplace_purchases"
    
    id = Column(SQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(SQL_UUID(as_uuid=True), ForeignKey("marketplace_agents.id"))
    buyer_id = Column(SQL_UUID(as_uuid=True), nullable=False)  # References users table
    api_key = Column(String, nullable=False, unique=True)
    status = Column(String, default="active")  # active, expired, revoked
    credits_remaining = Column(Integer, default=0)  # For credit-based purchases
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class MarketplaceUsage(Base):
    __tablename__ = "marketplace_usage"
    
    id = Column(SQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(String, nullable=False)
    agent_id = Column(SQL_UUID(as_uuid=True), ForeignKey("marketplace_agents.id"))
    buyer_id = Column(SQL_UUID(as_uuid=True), nullable=False)
    purchase_id = Column(SQL_UUID(as_uuid=True), ForeignKey("marketplace_purchases.id"))
    cost_charged = Column(Float, nullable=False)
    response_time = Column(Float)  # in seconds
    status = Column(String, default="success")  # success, error, timeout
    timestamp = Column(DateTime, default=datetime.utcnow)

class MarketplaceReview(Base):
    __tablename__ = "marketplace_reviews"
    
    id = Column(SQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(SQL_UUID(as_uuid=True), ForeignKey("marketplace_agents.id"))
    reviewer_id = Column(SQL_UUID(as_uuid=True), nullable=False)  # References users table
    rating = Column(Integer, nullable=False)  # 1-5 stars
    comment = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class MarketplacePayout(Base):
    __tablename__ = "marketplace_payouts"
    
    id = Column(SQL_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(SQL_UUID(as_uuid=True), ForeignKey("marketplace_agents.id"))
    owner_id = Column(SQL_UUID(as_uuid=True), nullable=False)
    amount = Column(Float, nullable=False)
    commission_rate = Column(Float, default=0.10)  # 10% commission
    net_amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, processed, failed
    stripe_payout_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime) 

# Marketplace Pydantic Models
class MarketplaceAgentCreate(BaseModel):
    name: str
    description: str
    endpoint: str
    price_per_call: float
    owner_id: str
    capabilities: List[str] = []
    tags: List[str] = []
    version: str = "v1.0"

class MarketplaceAgentResponse(BaseModel):
    id: str
    name: str
    description: str
    endpoint: str
    price_per_call: float
    owner_id: str
    capabilities: List[str]
    tags: List[str]
    version: str
    status: str
    rating: float
    total_reviews: int
    total_calls: int
    created_at: datetime
    updated_at: datetime

class MarketplacePurchaseCreate(BaseModel):
    agent_id: str
    buyer_id: str
    credits_remaining: int = 0
    expires_at: Optional[datetime] = None

class MarketplaceReviewCreate(BaseModel):
    agent_id: str
    reviewer_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None

class MarketplaceUsageCreate(BaseModel):
    execution_id: str
    agent_id: str
    buyer_id: str
    purchase_id: str
    cost_charged: float
    response_time: Optional[float] = None
    status: str = "success"

class AgentHealthCheck(BaseModel):
    agent_id: str
    version: str
    capabilities: List[str]
    ready: bool
    endpoint: str
    rate_limit: Dict[str, int]

class AgentExecuteRequest(BaseModel):
    execution_id: str
    node_id: str
    input: Dict[str, Any]
    config: Dict[str, Any]

class AgentExecuteResponse(BaseModel):
    status: str
    output: Dict[str, Any]
    error_message: Optional[str] = None
    execution_id: str