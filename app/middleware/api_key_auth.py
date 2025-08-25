"""
API Key authentication middleware
"""
from typing import Optional
from datetime import datetime
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.base import get_db
from app.models.database import APIKey, User
import structlog

logger = structlog.get_logger()


class APIKeyAuth(HTTPBearer):
    """API Key authentication scheme"""
    
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Optional[str]:
        """
        Extract and validate API key from request headers
        
        Accepts API key in two formats:
        1. Authorization: Bearer {api_key}
        2. X-API-Key: {api_key}
        """
        # Try to get API key from Authorization header
        credentials: Optional[HTTPAuthorizationCredentials] = await super().__call__(request)
        api_key = None
        
        if credentials:
            if credentials.scheme.lower() == "bearer":
                api_key = credentials.credentials
        
        # If not found in Authorization header, try X-API-Key header
        if not api_key:
            api_key = request.headers.get("X-API-Key")
        
        if not api_key:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        
        return api_key


async def verify_api_key(
    api_key: str,
    db: Session
) -> Optional[User]:
    """
    Verify API key and return associated user
    
    Args:
        api_key: The API key to verify
        db: Database session
        
    Returns:
        User object if valid, None otherwise
    """
    try:
        # Find API key in database
        db_api_key = db.query(APIKey).filter(
            APIKey.key == api_key
        ).first()
        
        if not db_api_key:
            logger.warning("Invalid API key attempted", api_key_preview=api_key[:8] + "...")
            return None
        
        # Check if key is active
        if not db_api_key.is_active:
            logger.warning("Inactive API key used", api_key_id=db_api_key.id)
            return None
        
        # Check if key is expired
        if db_api_key.expires_at and db_api_key.expires_at < datetime.utcnow():
            logger.warning("Expired API key used", api_key_id=db_api_key.id)
            return None
        
        # Update last used timestamp
        db_api_key.last_used = datetime.utcnow()
        db.commit()
        
        # Get associated user
        user = db.query(User).filter(User.id == db_api_key.user_id).first()
        
        if not user or not user.is_active:
            logger.warning("API key associated with invalid user", api_key_id=db_api_key.id)
            return None
        
        logger.info(
            "API key authenticated",
            api_key_id=db_api_key.id,
            user_id=user.id
        )
        
        return user
        
    except Exception as e:
        logger.error("Error verifying API key", error=str(e))
        return None


class RequireAPIKey:
    """
    Dependency to require API key authentication
    
    Usage:
        @router.get("/protected")
        async def protected_endpoint(user = Depends(RequireAPIKey())):
            return {"user": user.username}
    """
    
    def __init__(self, auto_error: bool = True):
        self.auto_error = auto_error
        self.api_key_auth = APIKeyAuth(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Optional[User]:
        """
        Validate API key and return user
        """
        # Get database session
        db = next(get_db())
        
        try:
            # Extract API key from request
            api_key = await self.api_key_auth(request)
            
            if not api_key:
                if self.auto_error:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid authentication credentials",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return None
            
            # Verify API key
            user = await verify_api_key(api_key, db)
            
            if not user:
                if self.auto_error:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired API key",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return None
            
            # Add user to request state for logging
            request.state.user = user
            
            return user
            
        finally:
            db.close()


class OptionalAPIKey:
    """
    Optional API key authentication
    
    If API key is provided, validates it and returns user.
    If not provided, returns None without error.
    
    Usage:
        @router.get("/public")
        async def public_endpoint(user = Depends(OptionalAPIKey())):
            if user:
                return {"message": f"Hello {user.username}"}
            return {"message": "Hello anonymous"}
    """
    
    def __init__(self):
        self.require_api_key = RequireAPIKey(auto_error=False)
    
    async def __call__(self, request: Request) -> Optional[User]:
        """
        Optionally validate API key and return user
        """
        return await self.require_api_key(request)


# Convenience instances
require_api_key = RequireAPIKey()
optional_api_key = OptionalAPIKey()