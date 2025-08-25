from fastapi import APIRouter

from app.api.v1.endpoints import convert, extract, cache, async_extract, metrics, auth, stream_extract, extract_auth, security, api_keys, extract_protected

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["api-keys"])
api_router.include_router(convert.router, prefix="/convert", tags=["convert"])
api_router.include_router(extract.router, prefix="/extract", tags=["extract"])
api_router.include_router(extract_auth.router, prefix="/extract/auth", tags=["extract", "authenticated"])
api_router.include_router(extract_protected.router, prefix="/extract/protected", tags=["extract", "api-key-required"])
api_router.include_router(cache.router, prefix="/cache", tags=["cache"])
api_router.include_router(async_extract.router, prefix="/async", tags=["async"])
api_router.include_router(stream_extract.router, prefix="/stream", tags=["stream"])
api_router.include_router(security.router, prefix="/security", tags=["security"])
api_router.include_router(metrics.router, tags=["monitoring"])