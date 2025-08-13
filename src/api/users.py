"""
User management endpoints for AI Spine API
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import List, Optional
from uuid import UUID

from src.core.auth import require_master_key, require_api_key
from src.core.user_auth import user_manager
from src.core.models import UserCreate, UserResponse, UserInfo
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/create", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    master: str = Depends(require_master_key)
):
    """
    Create a new user with API key (requires master key)
    
    This endpoint is intended to be called by your website backend
    with the master API key to create new user accounts.
    """
    try:
        new_user = await user_manager.create_user(user_data)
        logger.info("User created via API", email=user_data.email)
        return new_user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("Failed to create user", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(
    request: Request,
    current_user = Depends(require_api_key)
):
    """
    Get current user information
    
    Returns information about the user associated with the API key
    """
    if isinstance(current_user, str):
        # Master key or legacy key
        return UserInfo(
            id="master",
            email="master@ai-spine.com",
            name="Master User",
            organization="AI Spine",
            credits=999999,
            rate_limit=10000
        )
    
    return current_user


@router.post("/regenerate-key", response_model=dict)
async def regenerate_api_key(
    user_id: UUID,
    master: str = Depends(require_master_key)
):
    """
    Regenerate API key for a user (requires master key)
    
    This endpoint allows regenerating a user's API key if it's compromised
    """
    try:
        new_key = await user_manager.regenerate_api_key(user_id)
        if not new_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info("API key regenerated", user_id=str(user_id))
        return {
            "message": "API key regenerated successfully",
            "new_api_key": new_key
        }
    except Exception as e:
        logger.error("Failed to regenerate API key", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate API key"
        )


@router.post("/add-credits", response_model=dict)
async def add_credits_to_user(
    user_id: UUID,
    credits: int,
    master: str = Depends(require_master_key)
):
    """
    Add credits to a user account (requires master key)
    
    This endpoint is used to top up user credits for API usage
    """
    if credits <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credits must be positive"
        )
    
    try:
        new_balance = await user_manager.add_credits(user_id, credits)
        if new_balance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        logger.info("Credits added", user_id=str(user_id), credits=credits, new_balance=new_balance)
        return {
            "message": f"Successfully added {credits} credits",
            "new_balance": new_balance
        }
    except Exception as e:
        logger.error("Failed to add credits", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add credits"
        )


@router.get("/{user_id}", response_model=UserInfo)
async def get_user_info(
    user_id: UUID,
    master: str = Depends(require_master_key)
):
    """
    Get user information by ID (requires master key)
    
    This endpoint allows admins to view user information
    """
    try:
        user_info = await user_manager.get_user_info(user_id)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return user_info
    except Exception as e:
        logger.error("Failed to get user info", user_id=str(user_id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user information"
        )