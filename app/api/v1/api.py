from fastapi import APIRouter

from app.api.v1.endpoints import convert, extract

api_router = APIRouter()

api_router.include_router(convert.router, prefix="/convert", tags=["convert"])
api_router.include_router(extract.router, prefix="/extract", tags=["extract"])