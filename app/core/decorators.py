"""
Decorators for API endpoints
"""
from functools import wraps
from typing import Callable
import structlog
from fastapi import UploadFile
from app.core.cache import cache_manager

logger = structlog.get_logger()


def with_cache(extraction_type: str):
    """
    Decorator to add caching functionality to extraction endpoints
    
    Args:
        extraction_type: Type of extraction (json, text, markdown)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(file: UploadFile, *args, **kwargs):
            # Read file content
            content = await file.read()
            await file.seek(0)  # Reset file pointer
            
            # Build cache key from parameters
            cache_key_parts = [extraction_type]
            for key, value in kwargs.items():
                if key.startswith('include_') or key == 'preserve_formatting':
                    cache_key_parts.append(f"{key}:{value}")
            cache_key = "_".join(cache_key_parts)
            
            # Check cache
            cached_result = await cache_manager.get(content, cache_key)
            if cached_result:
                logger.info("Cache hit", filename=file.filename, cache_key=cache_key)
                # Return cached result with modified message
                result = await func(file, *args, **kwargs)
                result.content = cached_result
                result.message = f"{result.message} (cached)"
                return result
            
            # Call original function
            result = await func(file, *args, **kwargs)
            
            # Cache the result
            if result.success:
                await cache_manager.set(content, cache_key, result.content)
                logger.info("Cached result", filename=file.filename, cache_key=cache_key)
            
            return result
        
        return wrapper
    return decorator