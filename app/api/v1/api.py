from fastapi import APIRouter

# Import only the basic endpoints that exist
from app.api.v1.endpoints import extract

api_router = APIRouter()

# Include only the core extract endpoint for now
api_router.include_router(extract.router, prefix="/extract", tags=["extract"])