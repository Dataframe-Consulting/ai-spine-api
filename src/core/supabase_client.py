"""
Supabase client for database operations
Replaces SQLAlchemy with native Supabase client
"""
import os
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class SupabaseDB:
    """Supabase database client for all operations"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_SERVICE_KEY")  # Service key for admin operations
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        
        self.client: Client = create_client(self.url, self.key)
        logger.info("Supabase client initialized", url=self.url)
    
    # User operations
    async def create_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user"""
        try:
            result = self.client.table('users').insert(user_data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Failed to create user", error=str(e))
            raise
    
    async def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Get user by API key"""
        try:
            result = self.client.table('api_users')\
                .select("*")\
                .eq('api_key', api_key)\
                .execute()
            
            if result.data:
                # Update last_used_at
                self.client.table('api_users')\
                    .update({'last_used_at': datetime.utcnow().isoformat()})\
                    .eq('id', result.data[0]['id'])\
                    .execute()
                
                return result.data[0]
            return None
        except Exception as e:
            logger.error("Failed to get user by API key", error=str(e))
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            result = self.client.table('users')\
                .select("*")\
                .eq('email', email)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Failed to get user by email", error=str(e))
            return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID"""
        try:
            result = self.client.table('api_users')\
                .select("*")\
                .eq('id', user_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Failed to get user by ID", error=str(e))
            return None
    
    async def update_user_api_key(self, user_id: str, new_api_key: str) -> Optional[str]:
        """Update user's API key"""
        try:
            result = self.client.table('api_users')\
                .update({
                    'api_key': new_api_key,
                    'updated_at': datetime.utcnow().isoformat()
                })\
                .eq('id', user_id)\
                .execute()
            return new_api_key if result.data else None
        except Exception as e:
            logger.error("Failed to update API key", error=str(e))
            return None
    
    async def update_user_credits(self, user_id: str, credits_delta: int) -> Optional[int]:
        """Add or subtract credits from user"""
        try:
            # Get current credits
            user = await self.get_user_by_id(user_id)
            if not user:
                return None
            
            new_credits = max(0, user['credits'] + credits_delta)
            
            result = self.client.table('api_users')\
                .update({'credits': new_credits})\
                .eq('id', user_id)\
                .execute()
            
            return new_credits if result.data else None
        except Exception as e:
            logger.error("Failed to update credits", error=str(e))
            return None
    
    # Usage logging
    async def log_usage(self, usage_data: Dict[str, Any]) -> bool:
        """Log API usage"""
        try:
            result = self.client.table('usage_logs').insert(usage_data).execute()
            return bool(result.data)
        except Exception as e:
            logger.error("Failed to log usage", error=str(e))
            return False
    
    async def get_user_usage(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get usage logs for a user"""
        try:
            result = self.client.table('usage_logs')\
                .select("*")\
                .eq('user_id', user_id)\
                .order('timestamp', desc=True)\
                .limit(limit)\
                .execute()
            return result.data
        except Exception as e:
            logger.error("Failed to get usage logs", error=str(e))
            return []
    
    # Execution operations (for future use)
    async def save_execution(self, execution_data: Dict[str, Any]) -> bool:
        """Save execution context"""
        try:
            result = self.client.table('execution_contexts').insert(execution_data).execute()
            return bool(result.data)
        except Exception as e:
            logger.error("Failed to save execution", error=str(e))
            return False
    
    async def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution by ID"""
        try:
            result = self.client.table('execution_contexts')\
                .select("*")\
                .eq('execution_id', execution_id)\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("Failed to get execution", error=str(e))
            return None


# Global Supabase client instance (initialized on first use)
_supabase_db = None

def get_supabase_db():
    """Get or create Supabase client instance"""
    global _supabase_db
    if _supabase_db is None:
        _supabase_db = SupabaseDB()
    return _supabase_db

# For backwards compatibility
supabase_db = None  # Will be set when needed