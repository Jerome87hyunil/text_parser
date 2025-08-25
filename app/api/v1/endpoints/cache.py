"""
Cache management endpoints
"""
import structlog
from fastapi import APIRouter, HTTPException
from typing import Dict

from app.core.cache import cache_manager
from app.models.status import CacheStats

logger = structlog.get_logger()
router = APIRouter()


@router.get("/stats", 
    tags=["cache"],
    summary="캐시 통계 확인",
    responses={
        200: {
            "description": "캐시 통계",
            "content": {
                "application/json": {
                    "example": {
                        "enabled": True,
                        "connected": True,
                        "key_count": 42,
                        "memory_used": "1.2MB",
                        "hit_rate": 0.85,
                        "uptime_seconds": 3600
                    }
                }
            }
        }
    }
)
async def get_cache_stats() -> CacheStats:
    """
    Redis 캐시 통계를 반환합니다.
    
    Returns:
        캐시 상태 및 통계 정보
    """
    stats = await cache_manager.get_stats()
    return CacheStats(
        enabled=stats.get('enabled', False),
        backend=stats.get('backend', 'unknown'),
        items_count=stats.get('key_count', 0),
        memory_usage=stats.get('memory_used'),
        hit_rate=stats.get('hit_rate'),
        miss_rate=stats.get('miss_rate'),
        ttl=stats.get('ttl', 3600)
    )


@router.delete("/clear",
    tags=["cache"],
    summary="캐시 전체 삭제",
    responses={
        200: {"description": "캐시가 성공적으로 삭제됨"},
        500: {"description": "캐시 삭제 실패"}
    }
)
async def clear_cache() -> Dict[str, str]:
    """
    모든 캐시 엔트리를 삭제합니다.
    
    Returns:
        삭제 결과 메시지
    """
    try:
        await cache_manager.clear_all()
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        logger.error("Failed to clear cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")