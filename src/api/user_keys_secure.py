"""
User API Key management endpoints - SECURE VERSION
Uses Supabase JWT for authentication instead of public endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Optional, Dict
import structlog
import secrets

from src.core.supabase_auth import verify_supabase_token, mask_api_key
from src.core.supabase_client import get_supabase_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/user/account", tags=["User Account"])


@router.get("/api-key/status", response_model=Dict)
async def get_api_key_status(
    user_id: str = Depends(verify_supabase_token)
):
    """
    Get API key status for authenticated user
    
    Requires Supabase JWT token in Authorization header
    Returns masked API key for security
    """
    try:
        db = get_supabase_db()
        
        # Use select without .single() to avoid error when no record exists
        result = db.client.table("api_users")\
            .select("api_key, credits, rate_limit, created_at, last_used_at")\
            .eq("id", user_id)\
            .execute()
        
        if result.data and len(result.data) > 0:
            user_data = result.data[0]
            return {
                "has_api_key": True,
                "api_key_masked": mask_api_key(user_data["api_key"]),
                "credits": user_data["credits"],
                "rate_limit": user_data["rate_limit"],
                "created_at": user_data["created_at"],
                "last_used_at": user_data["last_used_at"]
            }
        else:
            return {
                "has_api_key": False,
                "api_key_masked": None,
                "message": "No API key generated yet"
            }
            
    except Exception as e:
        logger.error("Failed to get API key status", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key status"
        )


@router.post("/api-key/generate", response_model=Dict)
async def generate_api_key(
    user_id: str = Depends(verify_supabase_token)
):
    """
    Generate or regenerate API key for authenticated user
    
    Requires Supabase JWT token in Authorization header
    Returns FULL API key (only time it's shown in full)
    """
    try:
        db = get_supabase_db()
        
        # Check if user already has an API key (don't use .single() to avoid error)
        existing = db.client.table("api_users")\
            .select("api_key")\
            .eq("id", user_id)\
            .execute()
        
        # Generate new API key
        new_api_key = f"sk_{secrets.token_urlsafe(32)}"
        
        if existing.data and len(existing.data) > 0:
            # Update existing
            logger.info("Regenerating API key", user_id=user_id)
            
            result = db.client.table("api_users")\
                .update({
                    "api_key": new_api_key,
                    "updated_at": "now()"
                })\
                .eq("id", user_id)\
                .execute()
            
            # Log to history
            db.client.table("api_key_history")\
                .insert({
                    "user_id": user_id,
                    "old_api_key": mask_api_key(existing.data["api_key"]),  # Mask old key in logs
                    "new_api_key": mask_api_key(new_api_key),  # Mask new key in logs
                    "changed_by": "user"
                })\
                .execute()
            
            return {
                "message": "API key regenerated successfully",
                "api_key": new_api_key,  # Full key returned
                "action": "regenerated",
                "warning": "Store this key securely. It won't be shown again in full."
            }
        else:
            # Create new
            logger.info("Creating first API key", user_id=user_id)
            
            result = db.client.table("api_users")\
                .insert({
                    "id": user_id,
                    "api_key": new_api_key,
                    "credits": 1000,
                    "rate_limit": 100
                })\
                .execute()
            
            return {
                "message": "API key created successfully",
                "api_key": new_api_key,  # Full key returned
                "action": "created",
                "warning": "Store this key securely. It won't be shown again in full."
            }
            
    except Exception as e:
        logger.error("Failed to generate API key", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate API key"
        )


@router.post("/api-key/revoke", response_model=Dict)
async def revoke_api_key(
    user_id: str = Depends(verify_supabase_token)
):
    """
    Revoke API key for authenticated user
    
    Requires Supabase JWT token in Authorization header
    Completely removes the API key
    """
    try:
        db = get_supabase_db()
        
        # Get current key for history (don't use .single())
        current = db.client.table("api_users")\
            .select("api_key")\
            .eq("id", user_id)\
            .execute()
        
        if not current.data or len(current.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No API key found to revoke"
            )
        
        # Delete the API user record
        result = db.client.table("api_users")\
            .delete()\
            .eq("id", user_id)\
            .execute()
        
        # Log to history
        db.client.table("api_key_history")\
            .insert({
                "user_id": user_id,
                "old_api_key": mask_api_key(current.data[0]["api_key"]),
                "new_api_key": "REVOKED",
                "changed_by": "user"
            })\
            .execute()
        
        logger.info("API key revoked", user_id=user_id)
        
        return {
            "message": "API key revoked successfully",
            "status": "revoked"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to revoke API key", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@router.get("/profile", response_model=Dict)
async def get_user_profile(
    user_id: str = Depends(verify_supabase_token)
):
    """
    Get user profile including API usage stats
    
    Requires Supabase JWT token in Authorization header
    """
    try:
        db = get_supabase_db()
        
        # Get user API info
        api_info = db.client.table("api_users")\
            .select("credits, rate_limit, created_at, last_used_at")\
            .eq("id", user_id)\
            .single()\
            .execute()
        
        # Get usage stats
        usage_stats = db.client.table("usage_logs")\
            .select("*", count="exact")\
            .eq("user_id", user_id)\
            .execute()
        
        return {
            "user_id": user_id,
            "api_status": {
                "has_api_key": bool(api_info.data),
                "credits": api_info.data.get("credits", 0) if api_info.data else 0,
                "rate_limit": api_info.data.get("rate_limit", 0) if api_info.data else 0,
            },
            "usage": {
                "total_requests": usage_stats.count if hasattr(usage_stats, 'count') else 0,
                "last_used_at": api_info.data.get("last_used_at") if api_info.data else None
            }
        }
        
    except Exception as e:
        logger.error("Failed to get user profile", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user profile"
        )