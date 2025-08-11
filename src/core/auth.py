import os
import secrets
import structlog
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps

logger = structlog.get_logger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

class AuthManager:
    def __init__(self):
        self.api_key_required = os.getenv("API_KEY_REQUIRED", "false").lower() == "true"
        self.master_api_key = os.getenv("API_KEY", self._generate_default_key())
        self.valid_keys = set([self.master_api_key])  # In production, this would come from DB
        
        if not self.api_key_required:
            logger.info("API key authentication is disabled")
        else:
            logger.info("API key authentication is enabled")
            logger.info("Master API Key", key=self.master_api_key[:8] + "..." if len(self.master_api_key) > 8 else self.master_api_key)

    def _generate_default_key(self) -> str:
        """Generate a default API key for development"""
        return "ai-spine-dev-key-" + secrets.token_urlsafe(16)

    def add_api_key(self, api_key: str) -> None:
        """Add a valid API key"""
        self.valid_keys.add(api_key)
        logger.info("API key added", key=api_key[:8] + "...")

    def remove_api_key(self, api_key: str) -> None:
        """Remove an API key"""
        self.valid_keys.discard(api_key)
        logger.info("API key removed", key=api_key[:8] + "...")

    def validate_api_key(self, api_key: str) -> bool:
        """Validate if an API key is valid"""
        return api_key in self.valid_keys

    async def get_current_user(self, credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[str]:
        """
        Get current user from API key
        Returns the API key if valid, None if auth is disabled
        """
        if not self.api_key_required:
            return "anonymous"
        
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        api_key = credentials.credentials
        if not self.validate_api_key(api_key):
            logger.warning("Invalid API key attempted", key=api_key[:8] + "..." if len(api_key) > 8 else api_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        logger.debug("Valid API key used", key=api_key[:8] + "...")
        return api_key

# Global auth manager
auth_manager = AuthManager()

# Dependency for protected endpoints
async def require_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    """Dependency that requires a valid API key"""
    return await auth_manager.get_current_user(credentials)

# Dependency for optional authentication
async def optional_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[str]:
    """Dependency for optional authentication"""
    if not auth_manager.api_key_required:
        return "anonymous"
    
    if not credentials:
        return None
    
    api_key = credentials.credentials
    if auth_manager.validate_api_key(api_key):
        return api_key
    
    return None