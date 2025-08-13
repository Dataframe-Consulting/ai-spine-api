"""
User authentication using Supabase
"""
import os
import secrets
import structlog
from typing import Optional
from datetime import datetime
from uuid import uuid4

from src.core.supabase_client import get_supabase_db
from src.core.models import UserCreate, UserResponse, UserInfo

logger = structlog.get_logger(__name__)


class UserManagerSupabase:
    """Manages users with Supabase backend"""
    
    def __init__(self):
        self.master_api_key = os.getenv("API_KEY", "")
        self._db = None
    
    @property
    def db(self):
        """Lazy load database connection"""
        if self._db is None:
            self._db = get_supabase_db()
        return self._db
    
    def _generate_api_key(self) -> str:
        """Generate a secure API key"""
        return f"sk_{secrets.token_urlsafe(32)}"
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create a new user with API key"""
        try:
            # Check if user exists
            existing = await self.db.get_user_by_email(user_data.email)
            if existing:
                raise ValueError(f"User with email {user_data.email} already exists")
            
            # Create new user
            new_user_data = {
                'id': str(uuid4()),
                'email': user_data.email,
                'name': user_data.name,
                'organization': user_data.organization,
                'api_key': self._generate_api_key(),
                'rate_limit': user_data.rate_limit or 100,
                'credits': user_data.credits or 1000,
                'is_active': True,
                'created_at': datetime.utcnow().isoformat()
            }
            
            created_user = await self.db.create_user(new_user_data)
            
            if not created_user:
                raise Exception("Failed to create user in database")
            
            logger.info("User created", user_id=created_user['id'], email=created_user['email'])
            
            return UserResponse(
                id=created_user['id'],
                email=created_user['email'],
                name=created_user.get('name'),
                organization=created_user.get('organization'),
                api_key=created_user['api_key'],
                is_active=created_user['is_active'],
                rate_limit=created_user['rate_limit'],
                credits=created_user['credits'],
                created_at=datetime.fromisoformat(created_user['created_at'])
            )
            
        except Exception as e:
            logger.error("Failed to create user", error=str(e))
            raise
    
    async def validate_api_key(self, api_key: str) -> Optional[UserInfo]:
        """Validate API key and return user info"""
        try:
            user = await self.db.get_user_by_api_key(api_key)
            
            if not user:
                return None
            
            if user['credits'] <= 0:
                logger.warning("User has no credits", user_id=user['id'])
                return None
            
            return UserInfo(
                id=user['id'],
                email=user['email'],
                name=user.get('name'),
                organization=user.get('organization'),
                credits=user['credits'],
                rate_limit=user['rate_limit']
            )
        except Exception as e:
            logger.error("Failed to validate API key", error=str(e))
            return None
    
    async def get_user_info(self, user_id: str) -> Optional[UserInfo]:
        """Get user information by ID"""
        try:
            user = await self.db.get_user_by_id(user_id)
            
            if not user:
                return None
            
            return UserInfo(
                id=user['id'],
                email=user['email'],
                name=user.get('name'),
                organization=user.get('organization'),
                credits=user['credits'],
                rate_limit=user['rate_limit']
            )
        except Exception as e:
            logger.error("Failed to get user info", error=str(e))
            return None
    
    async def regenerate_api_key(self, user_id: str) -> Optional[str]:
        """Regenerate API key for a user"""
        try:
            new_api_key = self._generate_api_key()
            result = await self.db.update_user_api_key(user_id, new_api_key)
            
            if result:
                logger.info("API key regenerated", user_id=user_id)
                return new_api_key
            
            return None
        except Exception as e:
            logger.error("Failed to regenerate API key", error=str(e))
            return None
    
    async def add_credits(self, user_id: str, credits: int) -> Optional[int]:
        """Add credits to user account"""
        try:
            new_balance = await self.db.update_user_credits(user_id, credits)
            
            if new_balance is not None:
                logger.info("Credits added", user_id=user_id, credits=credits, new_balance=new_balance)
                return new_balance
            
            return None
        except Exception as e:
            logger.error("Failed to add credits", error=str(e))
            return None
    
    async def deduct_credits(self, user_id: str, credits: int = 1) -> bool:
        """Deduct credits from user account"""
        try:
            new_balance = await self.db.update_user_credits(user_id, -credits)
            
            if new_balance is not None:
                logger.info("Credits deducted", user_id=user_id, credits=credits, new_balance=new_balance)
                return True
            
            return False
        except Exception as e:
            logger.error("Failed to deduct credits", error=str(e))
            return False
    
    async def log_usage(
        self,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        execution_id: Optional[str] = None,
        credits_used: int = 1,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Log API usage"""
        try:
            usage_data = {
                'id': str(uuid4()),
                'user_id': user_id,
                'execution_id': execution_id,
                'endpoint': endpoint,
                'method': method,
                'status_code': status_code,
                'credits_used': credits_used,
                'response_time_ms': response_time_ms,
                'ip_address': ip_address,
                'user_agent': user_agent,
                'timestamp': datetime.utcnow().isoformat()
            }
            
            return await self.db.log_usage(usage_data)
        except Exception as e:
            logger.error("Failed to log usage", error=str(e))
            return False
    
    def is_master_key(self, api_key: str) -> bool:
        """Check if the provided key is the master API key"""
        return api_key == self.master_api_key and self.master_api_key != ""


# Global user manager instance
user_manager_supabase = UserManagerSupabase()