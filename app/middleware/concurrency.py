"""
Concurrency limiting middleware
"""
import asyncio
from typing import Dict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import structlog

logger = structlog.get_logger()


class ConcurrencyLimitMiddleware(BaseHTTPMiddleware):
    """
    Limit concurrent requests to prevent resource exhaustion
    """
    
    def __init__(self, app, max_concurrent_requests: int = 10):
        super().__init__(app)
        self.max_concurrent_requests = max_concurrent_requests
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.active_requests = 0
        
    async def dispatch(self, request: Request, call_next):
        # Check if we're at capacity
        if self.active_requests >= self.max_concurrent_requests:
            logger.warning(
                "Max concurrent requests reached",
                active=self.active_requests,
                max=self.max_concurrent_requests
            )
            raise HTTPException(
                status_code=503,
                detail="Server is busy. Please try again later."
            )
        
        # Acquire semaphore
        async with self.semaphore:
            self.active_requests += 1
            try:
                response = await call_next(request)
                return response
            finally:
                self.active_requests -= 1