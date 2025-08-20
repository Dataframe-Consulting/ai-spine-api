"""
Pydantic models for AI Spine API
NO SQLAlchemy - todo usa Supabase
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


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


# User Models (for API)
class UserCreate(BaseModel):
    """Request model for creating a new user"""
    email: str
    name: Optional[str] = None
    organization: Optional[str] = None
    rate_limit: Optional[int] = 100
    credits: Optional[int] = 1000

class UserResponse(BaseModel):
    """Response model for user data"""
    id: str
    email: str
    name: Optional[str]
    organization: Optional[str]
    api_key: str
    is_active: bool
    rate_limit: int
    credits: int
    created_at: datetime

class UserInfo(BaseModel):
    """Basic user info without sensitive data"""
    id: str
    email: str
    name: Optional[str]
    organization: Optional[str]
    credits: int
    rate_limit: int


# Agent Models
class AgentInfo(BaseModel):
    """Information about a registered agent"""
    agent_id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[str]
    agent_type: AgentType
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Tool Models
class ToolType(str, Enum):
    """Types of tools available"""
    OCR = "ocr"
    DOCUMENT_GENERATION = "document_generation"
    PDF_PROCESSING = "pdf_processing"
    IMAGE_PROCESSING = "image_processing"
    DATA_EXTRACTION = "data_extraction"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    ANALYSIS = "analysis"
    API_INTEGRATION = "api_integration"
    DATABASE_OPERATION = "database_operation"

class CustomField(BaseModel):
    """Custom field configuration for tools"""
    name: str
    type: str = Field(pattern=r"^(string|number|boolean|array|object)$")
    description: str
    required: bool = False
    default_value: Optional[Any] = None

class ToolInfo(BaseModel):
    """Information about a registered tool"""
    tool_id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[str]
    tool_type: List[ToolType]
    custom_fields: List[CustomField] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None  # User ID for ownership
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ToolRegistration(BaseModel):
    """Request model for tool registration"""
    tool_id: str
    name: str
    description: str
    endpoint: str = Field(pattern=r"^https?://.*")
    capabilities: List[str]
    tool_type: List[ToolType]
    custom_fields: List[CustomField] = Field(default_factory=list)

class ToolUpdate(BaseModel):
    """Request model for tool updates"""
    name: Optional[str] = None
    description: Optional[str] = None
    endpoint: Optional[str] = Field(None, pattern=r"^https?://.*")
    capabilities: Optional[List[str]] = None
    tool_type: Optional[List[ToolType]] = None
    custom_fields: Optional[List[CustomField]] = None
    is_active: Optional[bool] = None

class ToolResponse(BaseModel):
    """Response model for tool operations"""
    tool_id: str
    name: str
    description: str
    endpoint: str
    capabilities: List[str]
    tool_type: List[ToolType]
    custom_fields: List[CustomField]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ToolTestRequest(BaseModel):
    """Request model for testing tool connectivity"""
    endpoint: str = Field(pattern=r"^https?://.*")

class ToolTestResponse(BaseModel):
    """Response model for tool connectivity test"""
    success: bool
    message: str
    response_time_ms: Optional[int] = None
    status_code: Optional[int] = None


# Flow Models
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


# Execution Models
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
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Convert dictionary to Pydantic model"""
        # Handle datetime strings
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        if data.get("completed_at") and isinstance(data["completed_at"], str):
            data["completed_at"] = datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00"))
        
        return cls(
            execution_id=data.get("execution_id", ""),
            flow_id=data.get("flow_id", ""),
            status=data.get("status", "pending"),
            input_data=data.get("input_data", {}),
            output_data=data.get("output_data", {}),
            error_message=data.get("error_message"),
            created_at=data.get("created_at", datetime.utcnow()),
            updated_at=data.get("updated_at", datetime.utcnow()),
            completed_at=data.get("completed_at")
        )

class NodeExecutionResult(BaseModel):
    """Result from executing a single node"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    execution_id: str
    node_id: str
    agent_id: Optional[str] = None
    status: ExecutionStatus
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Message Models
class AgentMessagePydantic(BaseModel):
    """Message passed between agents"""
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


# Metrics Model
class Metrics(BaseModel):
    """Execution metrics"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    cancelled_executions: int = 0
    running_executions: int = 0
    average_execution_time: float = 0.0
    total_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Marketplace Models (Optional - if still needed)
class MarketplaceAgentInfo(BaseModel):
    """Information about a marketplace agent"""
    id: str
    name: str
    description: str
    endpoint: str
    price_per_call: float
    owner_id: str
    capabilities: List[str]
    tags: List[str]
    version: str = "v1.0"
    status: str = "active"
    rating: float = 0.0
    total_reviews: int = 0
    total_calls: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class MarketplacePurchaseRequest(BaseModel):
    """Request to purchase marketplace agent access"""
    agent_id: str
    duration_days: int = 30

class MarketplacePurchaseResponse(BaseModel):
    """Response from marketplace purchase"""
    purchase_id: str
    agent_id: str
    user_id: str
    expires_at: datetime
    credits_charged: int
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }