"""
User authentication and management system for multi-tenant API access
"""
import os
import secrets
import structlog
from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from src.core.database import get_db_session
from src.core.models import User, UsageLog, UserCreate, UserResponse, UserInfo

logger = structlog.get_logger(__name__)


class UserManager:
    """Manages user creation, authentication, and usage tracking"""
    
    def __init__(self):
        self.master_api_key = os.getenv("API_KEY", "")
        
    def _generate_api_key(self) -> str:
        """Generate a secure API key"""
        return f"sk_{secrets.token_urlsafe(32)}"
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user with API key"""
        try:
            async with get_db_session() as session:
                # Check if user already exists
                result = await session.execute(
                    select(User).where(User.email == user_data.email)
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    raise ValueError(f"User with email {user_data.email} already exists")
                
                # Create new user
                new_user = User(
                    id=uuid4(),
                    email=user_data.email,
                    name=user_data.name,
                    organization=user_data.organization,
                    api_key=self._generate_api_key(),
                    rate_limit=user_data.rate_limit,
                    credits=user_data.credits,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
                logger.info("User created", user_id=str(new_user.id), email=new_user.email)
                
                return UserResponse(
                    id=str(new_user.id),
                    email=new_user.email,
                    name=new_user.name,
                    organization=new_user.organization,
                    api_key=new_user.api_key,
                    is_active=new_user.is_active,
                    rate_limit=new_user.rate_limit,
                    credits=new_user.credits,
                    created_at=new_user.created_at
                )
                
        except IntegrityError as e:
            logger.error("Database integrity error", error=str(e))
            raise ValueError("User with this email already exists")
        except Exception as e:
            logger.error("Failed to create user", error=str(e))
            raise
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[UserInfo]:
        """Get user by API key and return UserInfo"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(User).where(
                        User.api_key == api_key,
                        User.is_active == True
                    )
                )
                user = result.scalar_one_or_none()
                
                if user:
                    # Update last_used_at
                    await session.execute(
                        update(User)
                        .where(User.id == user.id)
                        .values(last_used_at=datetime.utcnow())
                    )
                    await session.commit()
                    
                    # Return UserInfo instead of the ORM object
                    return UserInfo(
                        id=str(user.id),
                        email=user.email,
                        name=user.name,
                        organization=user.organization,
                        credits=user.credits,
                        rate_limit=user.rate_limit
                    )
                
                return None
                
        except Exception as e:
            logger.error("Failed to get user by API key", error=str(e))
            return None
    
    async def validate_api_key(self, api_key: str) -> Optional[UserInfo]:
        """Validate API key and return user info"""
        user_info = await self.get_user_by_api_key(api_key)
        
        if not user_info:
            return None
        
        if user_info.credits <= 0:
            logger.warning("User has no credits", user_id=user_info.id)
            return None
        
        return user_info
    
    async def deduct_credits(self, user_id: UUID, credits: int = 1) -> bool:
        """Deduct credits from user account"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id, User.credits >= credits)
                    .values(credits=User.credits - credits)
                    .returning(User.credits)
                )
                
                new_balance = result.scalar_one_or_none()
                if new_balance is not None:
                    await session.commit()
                    logger.info("Credits deducted", user_id=str(user_id), credits=credits, new_balance=new_balance)
                    return True
                
                logger.warning("Insufficient credits", user_id=str(user_id))
                return False
                
        except Exception as e:
            logger.error("Failed to deduct credits", user_id=str(user_id), error=str(e))
            return False
    
    async def log_usage(
        self,
        user_id: UUID,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        execution_id: Optional[str] = None,
        credits_used: int = 1,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Log API usage for analytics and billing"""
        try:
            async with get_db_session() as session:
                usage_log = UsageLog(
                    id=uuid4(),
                    user_id=user_id,
                    execution_id=execution_id,
                    endpoint=endpoint,
                    method=method,
                    status_code=status_code,
                    credits_used=credits_used,
                    response_time_ms=response_time_ms,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    timestamp=datetime.utcnow()
                )
                
                session.add(usage_log)
                await session.commit()
                
                return True
                
        except Exception as e:
            logger.error("Failed to log usage", user_id=str(user_id), error=str(e))
            return False
    
    async def get_user_info(self, user_id: UUID) -> Optional[UserInfo]:
        """Get user information by ID"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return None
                
                return UserInfo(
                    id=str(user.id),
                    email=user.email,
                    name=user.name,
                    organization=user.organization,
                    credits=user.credits,
                    rate_limit=user.rate_limit
                )
                
        except Exception as e:
            logger.error("Failed to get user info", user_id=str(user_id), error=str(e))
            return None
    
    async def regenerate_api_key(self, user_id: UUID) -> Optional[str]:
        """Regenerate API key for a user"""
        try:
            async with get_db_session() as session:
                new_api_key = self._generate_api_key()
                
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(api_key=new_api_key, updated_at=datetime.utcnow())
                    .returning(User.api_key)
                )
                
                updated_key = result.scalar_one_or_none()
                if updated_key:
                    await session.commit()
                    logger.info("API key regenerated", user_id=str(user_id))
                    return updated_key
                
                return None
                
        except Exception as e:
            logger.error("Failed to regenerate API key", user_id=str(user_id), error=str(e))
            return None
    
    async def add_credits(self, user_id: UUID, credits: int) -> Optional[int]:
        """Add credits to user account"""
        try:
            async with get_db_session() as session:
                result = await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(credits=User.credits + credits)
                    .returning(User.credits)
                )
                
                new_balance = result.scalar_one_or_none()
                if new_balance is not None:
                    await session.commit()
                    logger.info("Credits added", user_id=str(user_id), credits=credits, new_balance=new_balance)
                    return new_balance
                
                return None
                
        except Exception as e:
            logger.error("Failed to add credits", user_id=str(user_id), error=str(e))
            return None
    
    def is_master_key(self, api_key: str) -> bool:
        """Check if the provided key is the master API key"""
        return api_key == self.master_api_key and self.master_api_key != ""


# Global user manager instance
user_manager = UserManager()