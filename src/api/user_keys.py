"""
User API Key management endpoints
Permite a los usuarios generar y gestionar sus propias API keys
"""
from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional, Dict
from uuid import UUID
import structlog

from src.core.models import UserInfo
from src.core.user_auth_supabase import user_manager_supabase as user_manager
from src.core.supabase_client import get_supabase_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/user/keys", tags=["User Keys"])


@router.post("/generate", response_model=Dict)
async def generate_user_api_key(
    request: Request,
    user_id: str
):
    """
    Generate or regenerate API key for a specific user
    
    Este endpoint será llamado por tu frontend cuando el usuario
    haga click en "Generar API Key" en su dashboard.
    
    El frontend debe enviar el user_id del usuario autenticado.
    """
    try:
        db = get_supabase_db()
        
        # Verificar si el usuario ya tiene una API key
        existing = db.client.table("api_users")\
            .select("api_key")\
            .eq("id", user_id)\
            .single()\
            .execute()
        
        if existing.data:
            # El usuario ya tiene API key, regenerarla
            logger.info("Regenerating API key for user", user_id=user_id)
            
            # Generar nueva API key
            import secrets
            new_api_key = f"sk_{secrets.token_urlsafe(32)}"
            
            # Actualizar en la base de datos
            result = db.client.table("api_users")\
                .update({
                    "api_key": new_api_key,
                    "updated_at": "now()"
                })\
                .eq("id", user_id)\
                .execute()
            
            # Guardar en historial
            db.client.table("api_key_history")\
                .insert({
                    "user_id": user_id,
                    "old_api_key": existing.data["api_key"],
                    "new_api_key": new_api_key,
                    "changed_by": "user"
                })\
                .execute()
            
            return {
                "message": "API key regenerated successfully",
                "api_key": new_api_key,
                "action": "regenerated"
            }
        else:
            # Primera vez generando API key
            logger.info("Creating first API key for user", user_id=user_id)
            
            # Generar API key
            import secrets
            api_key = f"sk_{secrets.token_urlsafe(32)}"
            
            # Insertar en la base de datos
            result = db.client.table("api_users")\
                .insert({
                    "id": user_id,
                    "api_key": api_key,
                    "credits": 1000,
                    "rate_limit": 100
                })\
                .execute()
            
            return {
                "message": "API key created successfully",
                "api_key": api_key,
                "action": "created"
            }
            
    except Exception as e:
        logger.error("Failed to generate API key", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate API key: {str(e)}"
        )


@router.get("/my-key", response_model=Dict)
async def get_my_api_key(
    user_id: str
):
    """
    Get current API key for a user
    
    Returns the API key if it exists, or null if not generated yet
    """
    try:
        db = get_supabase_db()
        
        result = db.client.table("api_users")\
            .select("api_key, credits, rate_limit, created_at, last_used_at")\
            .eq("id", user_id)\
            .single()\
            .execute()
        
        if result.data:
            return {
                "has_api_key": True,
                "api_key": result.data["api_key"],
                "credits": result.data["credits"],
                "rate_limit": result.data["rate_limit"],
                "created_at": result.data["created_at"],
                "last_used_at": result.data["last_used_at"]
            }
        else:
            return {
                "has_api_key": False,
                "api_key": None,
                "message": "No API key generated yet. Click 'Generate API Key' to create one."
            }
            
    except Exception as e:
        logger.error("Failed to get API key", user_id=user_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key"
        )


@router.delete("/revoke", response_model=Dict)
async def revoke_my_api_key(
    user_id: str
):
    """
    Revoke (delete) API key for a user
    
    This completely removes the API key. User will need to generate a new one.
    """
    try:
        db = get_supabase_db()
        
        # Obtener la API key actual para el historial
        current = db.client.table("api_users")\
            .select("api_key")\
            .eq("id", user_id)\
            .single()\
            .execute()
        
        if not current.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No API key found to revoke"
            )
        
        # Eliminar el registro
        result = db.client.table("api_users")\
            .delete()\
            .eq("id", user_id)\
            .execute()
        
        # Guardar en historial
        db.client.table("api_key_history")\
            .insert({
                "user_id": user_id,
                "old_api_key": current.data["api_key"],
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