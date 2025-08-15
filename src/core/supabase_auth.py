"""
Supabase token authentication for user management endpoints
Uses modern Supabase client to verify tokens
"""
from fastapi import HTTPException, Header, Depends
from typing import Optional
import os
import structlog
from supabase import create_client

logger = structlog.get_logger(__name__)

# Get Supabase configuration from environment
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

def get_supabase_client():
    """Get Supabase client for verification using service key"""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Supabase configuration missing")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def verify_supabase_token(authorization: Optional[str] = Header(None)) -> str:
    """
    Verify Supabase access token and return user_id
    
    This uses the Supabase service key to verify user tokens
    Used for user management endpoints (/api/v1/user/*)
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing"
        )
    
    try:
        # Extract token from Bearer scheme
        token = authorization.replace("Bearer ", "")
        
        # Use Supabase client with service key to verify token
        client = get_supabase_client()
        
        # Get user from token using service key privileges
        user_response = client.auth.get_user(token)
        
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        # Additional security checks
        user = user_response.user
        
        # Verify user is confirmed (optional but recommended)
        if not user.confirmed_at:
            raise HTTPException(
                status_code=403,
                detail="Email not confirmed"
            )
        
        # Verify user is not banned (TODO)
        if user.user_metadata and user.user_metadata.get("banned"):
            raise HTTPException(
                status_code=403,
                detail="User account suspended"
            )
        
        user_id = user.id
        logger.info("Token verified via Supabase", user_id=user_id)
        return user_id
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Auth verification failed", error=str(e))
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

async def optional_supabase_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Optional token verification - returns user_id if valid, None otherwise
    """
    if not authorization:
        return None
    
    try:
        return await verify_supabase_token(authorization)
    except:
        return None

def mask_api_key(api_key: str) -> str:
    """
    Mask API key for security (show only first and last 4 chars)
    Example: sk_abc...xyz
    """
    if not api_key or len(api_key) < 12:
        return "***"
    
    return f"{api_key[:6]}...{api_key[-4:]}"