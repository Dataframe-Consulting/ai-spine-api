import os
import secrets
import structlog
from typing import Optional, Union
from fastapi import HTTPException, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from functools import wraps
from src.core.user_auth import user_manager
from src.core.models import UserInfo
from uuid import UUID
import time

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

    async def get_current_user(self, credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[Union[str, UserInfo]]:
        """
        Get current user from API key
        Returns UserInfo if valid user key, "master" if master key, None if auth disabled
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
        
        # Check if it's the master key
        if user_manager.is_master_key(api_key):
            logger.debug("Master API key used")
            return "master"
        
        # Check if it's a user key
        user_info = await user_manager.validate_api_key(api_key)
        if user_info:
            logger.debug("Valid user API key", user_id=user_info.id)
            return user_info
        
        # Check legacy keys (backwards compatibility)
        if self.validate_api_key(api_key):
            logger.debug("Valid legacy API key used", key=api_key[:8] + "...")
            return api_key
        
        logger.warning("Invalid API key attempted", key=api_key[:8] + "..." if len(api_key) > 8 else api_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Global auth manager
auth_manager = AuthManager()

# Dependency for protected endpoints
async def require_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Union[str, UserInfo]:
    """Dependency that requires a valid API key"""
    start_time = time.time()
    user = await auth_manager.get_current_user(credentials)
    
    # Log usage for user keys
    if isinstance(user, UserInfo):
        response_time_ms = (time.time() - start_time) * 1000
        await user_manager.log_usage(
            user_id=UUID(user.id),
            endpoint=str(request.url.path),
            method=request.method,
            status_code=200,  # Will be updated by middleware
            response_time_ms=response_time_ms,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent")
        )
    
    return user

# Dependency for master key only endpoints
async def require_master_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> str:
    """Dependency that requires the master API key"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    api_key = credentials.credentials
    if not user_manager.is_master_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Master key required for this operation",
        )
    
    return "master"

# Dependency for optional authentication
async def optional_api_key(credentials: Optional[HTTPAuthorizationCredentials] = Security(security)) -> Optional[Union[str, UserInfo]]:
    """Dependency for optional authentication"""
    if not auth_manager.api_key_required:
        return "anonymous"
    
    if not credentials:
        return None
    
    api_key = credentials.credentials
    
    # Check user key
    user_info = await user_manager.validate_api_key(api_key)
    if user_info:
        return user_info
    
    # Check legacy keys
    if auth_manager.validate_api_key(api_key):
        return api_key
    
    return None