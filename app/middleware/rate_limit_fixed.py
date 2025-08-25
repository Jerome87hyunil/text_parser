"""
Fixed rate limiting middleware without CallableSchema issues
"""
from fastapi import Request, HTTPException, status
from typing import Dict, Optional
import time
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()


class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self, requests: int = 10, window: int = 60):
        """
        Initialize rate limiter
        
        Args:
            requests: Number of allowed requests
            window: Time window in seconds
        """
        self.requests = requests
        self.window = window
        self.clients: Dict[str, list] = defaultdict(list)
        self._cleanup_task = None
        
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier from request"""
        # Try to get from auth header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return f"user:{auth_header[7:20]}"  # Use part of token
        
        # Fallback to IP address
        client = request.client
        if client:
            return f"ip:{client.host}"
        
        return "ip:unknown"
    
    def _cleanup_old_requests(self, client_id: str, current_time: float):
        """Remove requests older than the window"""
        cutoff = current_time - self.window
        self.clients[client_id] = [
            req_time for req_time in self.clients[client_id]
            if req_time > cutoff
        ]
    
    async def check_rate_limit(self, request: Request) -> bool:
        """
        Check if request is within rate limit
        
        Returns:
            True if allowed, raises HTTPException if not
        """
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Clean up old requests
        self._cleanup_old_requests(client_id, current_time)
        
        # Check rate limit
        if len(self.clients[client_id]) >= self.requests:
            # Calculate retry after
            oldest_request = min(self.clients[client_id])
            retry_after = int(self.window - (current_time - oldest_request))
            
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                requests=len(self.clients[client_id]),
                limit=self.requests,
                retry_after=retry_after
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds",
                headers={"Retry-After": str(retry_after)}
            )
        
        # Add current request
        self.clients[client_id].append(current_time)
        return True
    
    async def cleanup_loop(self):
        """Periodic cleanup of old entries"""
        while True:
            try:
                await asyncio.sleep(self.window)
                current_time = time.time()
                cutoff = current_time - self.window
                
                # Clean up all clients
                empty_clients = []
                for client_id in list(self.clients.keys()):
                    self.clients[client_id] = [
                        req_time for req_time in self.clients[client_id]
                        if req_time > cutoff
                    ]
                    if not self.clients[client_id]:
                        empty_clients.append(client_id)
                
                # Remove empty entries
                for client_id in empty_clients:
                    del self.clients[client_id]
                    
            except Exception as e:
                logger.error("Error in cleanup loop", error=str(e))


# Create rate limiter instances
# Higher limits for development/testing
default_limiter = RateLimiter(requests=100, window=60)  # 100 requests per minute
auth_limiter = RateLimiter(requests=1000, window=60)  # 1000 requests per minute for authenticated users


# Dependency functions
async def rate_limit_dependency(request: Request):
    """Rate limit dependency for normal endpoints"""
    await default_limiter.check_rate_limit(request)
    return True


async def auth_rate_limit_dependency(request: Request):
    """Rate limit dependency for authenticated endpoints"""
    await auth_limiter.check_rate_limit(request)
    return True