"""
API Key management endpoints
"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.base import get_db
from app.models.database import APIKey, User
from app.models.auth import User as UserModel
from app.api.v1.endpoints.auth import get_current_active_user
from app.core.security import generate_api_key
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()

router = APIRouter()


class APIKeyCreate(BaseModel):
    """API Key creation request"""
    name: str = Field(..., min_length=1, max_length=100, description="API 키 이름")
    expires_in_days: Optional[int] = Field(
        None, 
        ge=1, 
        le=365, 
        description="만료 기간 (일 단위, 최대 365일)"
    )


class APIKeyResponse(BaseModel):
    """API Key response"""
    id: int
    key: str
    name: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    
    class Config:
        from_attributes = True


class APIKeyListResponse(BaseModel):
    """API Key list response (without actual key)"""
    id: int
    name: str
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    key_preview: str  # First 8 characters only
    
    class Config:
        from_attributes = True


@router.post("/create",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="API 키 생성",
    description="새로운 API 키를 생성합니다. 키는 생성 시에만 전체 값을 확인할 수 있습니다."
)
async def create_api_key(
    request: APIKeyCreate,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    새로운 API 키를 생성합니다.
    
    - **name**: API 키를 식별하기 위한 이름
    - **expires_in_days**: 만료 기간 (일 단위, 선택사항)
    
    생성된 키는 이 응답에서만 전체 값을 확인할 수 있으므로 안전하게 보관하세요.
    """
    try:
        # Generate new API key
        api_key = generate_api_key()
        
        # Calculate expiration date if specified
        expires_at = None
        if request.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        
        # Get user from database
        db_user = db.query(User).filter(User.username == current_user.username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create new API key record
        db_api_key = APIKey(
            key=api_key,
            name=request.name,
            user_id=db_user.id,
            is_active=True,
            expires_at=expires_at
        )
        
        db.add(db_api_key)
        db.commit()
        db.refresh(db_api_key)
        
        logger.info(
            "API key created",
            user_id=db_user.id,
            api_key_id=db_api_key.id,
            expires_at=expires_at
        )
        
        return APIKeyResponse(
            id=db_api_key.id,
            key=db_api_key.key,
            name=db_api_key.name,
            is_active=db_api_key.is_active,
            created_at=db_api_key.created_at,
            expires_at=db_api_key.expires_at,
            last_used=db_api_key.last_used
        )
        
    except Exception as e:
        logger.error("Failed to create API key", error=str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.get("/list",
    response_model=List[APIKeyListResponse],
    summary="API 키 목록 조회",
    description="현재 사용자의 모든 API 키 목록을 조회합니다."
)
async def list_api_keys(
    include_inactive: bool = Query(False, description="비활성 키 포함 여부"),
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    현재 사용자의 API 키 목록을 조회합니다.
    보안을 위해 키의 전체 값은 표시되지 않습니다.
    """
    try:
        # Get user from database
        db_user = db.query(User).filter(User.username == current_user.username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Query API keys
        query = db.query(APIKey).filter(APIKey.user_id == db_user.id)
        
        if not include_inactive:
            query = query.filter(APIKey.is_active == True)
        
        api_keys = query.order_by(APIKey.created_at.desc()).all()
        
        # Convert to response format with key preview
        response = []
        for key in api_keys:
            response.append(APIKeyListResponse(
                id=key.id,
                name=key.name,
                is_active=key.is_active,
                created_at=key.created_at,
                expires_at=key.expires_at,
                last_used=key.last_used,
                key_preview=key.key[:8] + "..." if key.key else "..."
            ))
        
        return response
        
    except Exception as e:
        logger.error("Failed to list API keys", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.delete("/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="API 키 삭제",
    description="지정된 API 키를 삭제합니다."
)
async def delete_api_key(
    api_key_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    API 키를 삭제합니다. 삭제된 키는 복구할 수 없습니다.
    """
    try:
        # Get user from database
        db_user = db.query(User).filter(User.username == current_user.username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Find API key
        api_key = db.query(APIKey).filter(
            and_(
                APIKey.id == api_key_id,
                APIKey.user_id == db_user.id
            )
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Delete API key
        db.delete(api_key)
        db.commit()
        
        logger.info(
            "API key deleted",
            user_id=db_user.id,
            api_key_id=api_key_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete API key", error=str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete API key"
        )


@router.patch("/{api_key_id}/deactivate",
    status_code=status.HTTP_200_OK,
    summary="API 키 비활성화",
    description="API 키를 비활성화합니다. 나중에 다시 활성화할 수 있습니다."
)
async def deactivate_api_key(
    api_key_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    API 키를 비활성화합니다. 비활성화된 키는 사용할 수 없지만 삭제되지는 않습니다.
    """
    try:
        # Get user from database
        db_user = db.query(User).filter(User.username == current_user.username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Find API key
        api_key = db.query(APIKey).filter(
            and_(
                APIKey.id == api_key_id,
                APIKey.user_id == db_user.id
            )
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Deactivate API key
        api_key.is_active = False
        db.commit()
        
        logger.info(
            "API key deactivated",
            user_id=db_user.id,
            api_key_id=api_key_id
        )
        
        return {"message": "API key deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to deactivate API key", error=str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate API key"
        )


@router.patch("/{api_key_id}/activate",
    status_code=status.HTTP_200_OK,
    summary="API 키 활성화",
    description="비활성화된 API 키를 다시 활성화합니다."
)
async def activate_api_key(
    api_key_id: int,
    current_user: UserModel = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    비활성화된 API 키를 다시 활성화합니다.
    """
    try:
        # Get user from database
        db_user = db.query(User).filter(User.username == current_user.username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Find API key
        api_key = db.query(APIKey).filter(
            and_(
                APIKey.id == api_key_id,
                APIKey.user_id == db_user.id
            )
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Check if expired
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot activate expired API key"
            )
        
        # Activate API key
        api_key.is_active = True
        db.commit()
        
        logger.info(
            "API key activated",
            user_id=db_user.id,
            api_key_id=api_key_id
        )
        
        return {"message": "API key activated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to activate API key", error=str(e))
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate API key"
        )