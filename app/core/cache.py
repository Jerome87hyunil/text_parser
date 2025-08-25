"""
Redis cache configuration and management
"""
import redis.asyncio as redis
from typing import Optional, Any, Union, Dict
import json
import hashlib
import structlog
from app.core.config import settings

logger = structlog.get_logger()


class CacheManager:
    """
    Manage Redis cache operations for extracted content with optimized strategies
    """
    
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.enabled = settings.CACHE_ENABLED
        self.ttl = settings.CACHE_TTL
        self.max_size = getattr(settings, 'CACHE_MAX_SIZE', 100 * 1024 * 1024)  # 100MB default
        self.compression_threshold = getattr(settings, 'CACHE_COMPRESSION_THRESHOLD', 1024)  # 1KB
        
    async def connect(self):
        """Connect to Redis server"""
        if not self.enabled:
            logger.info("Cache disabled in configuration")
            return
            
        try:
            self.redis_client = await redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("Connected to Redis cache")
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e))
            self.enabled = False
    
    async def disconnect(self):
        """Disconnect from Redis server"""
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis cache")
    
    def _generate_cache_key(self, file_content: bytes, extraction_type: str, options: Optional[Dict] = None) -> str:
        """Generate cache key from file content hash and options"""
        content_hash = hashlib.sha256(file_content).hexdigest()
        
        # Include extraction options in cache key for different configurations
        if options:
            options_str = json.dumps(options, sort_keys=True)
            options_hash = hashlib.md5(options_str.encode()).hexdigest()[:8]
            return f"hwp_extract:{extraction_type}:{content_hash}:{options_hash}"
        
        return f"hwp_extract:{extraction_type}:{content_hash}"
    
    async def get(self, file_content: bytes, extraction_type: str, options: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Get cached extraction result with compression support"""
        if not self.enabled or not self.redis_client:
            return None
            
        key = self._generate_cache_key(file_content, extraction_type, options)
        
        try:
            # Try to get cached data
            cached_data = await self.redis_client.get(key)
            if cached_data:
                # Update access time for LRU tracking
                await self.redis_client.expire(key, self.ttl)
                
                # Check if data is compressed
                if cached_data.startswith('gzip:'):
                    import gzip
                    import base64
                    compressed_data = base64.b64decode(cached_data[5:])
                    decompressed = gzip.decompress(compressed_data).decode('utf-8')
                    data = json.loads(decompressed)
                else:
                    data = json.loads(cached_data)
                
                logger.info("Cache hit", key=key)
                return data
            
            logger.debug("Cache miss", key=key)
            return None
        except Exception as e:
            logger.error("Cache get error", error=str(e), key=key)
            return None
    
    async def set(self, file_content: bytes, extraction_type: str, data: Dict[str, Any], options: Optional[Dict] = None):
        """Set extraction result in cache with compression and size management"""
        if not self.enabled or not self.redis_client:
            return
            
        key = self._generate_cache_key(file_content, extraction_type, options)
        
        try:
            # Serialize data
            json_data = json.dumps(data, ensure_ascii=False)
            data_size = len(json_data.encode('utf-8'))
            
            # Check size limit
            if data_size > self.max_size:
                logger.warning("Data too large for cache", key=key, size=data_size)
                return
            
            # Compress if above threshold
            if data_size > self.compression_threshold:
                import gzip
                import base64
                compressed = gzip.compress(json_data.encode('utf-8'))
                cache_value = 'gzip:' + base64.b64encode(compressed).decode('ascii')
                logger.debug("Compressing cache data", original_size=data_size, compressed_size=len(cache_value))
            else:
                cache_value = json_data
            
            # Set with TTL based on data type and size
            ttl = self._calculate_ttl(extraction_type, data_size)
            await self.redis_client.setex(key, ttl, cache_value)
            
            logger.info("Cache set", key=key, ttl=ttl, size=data_size)
        except Exception as e:
            logger.error("Cache set error", error=str(e), key=key)
    
    async def delete(self, file_content: bytes, extraction_type: str):
        """Delete specific cache entry"""
        if not self.enabled or not self.redis_client:
            return
            
        key = self._generate_cache_key(file_content, extraction_type)
        
        try:
            await self.redis_client.delete(key)
            logger.info("Cache deleted", key=key)
        except Exception as e:
            logger.error("Cache delete error", error=str(e), key=key)
    
    async def clear_all(self):
        """Clear all cache entries"""
        if not self.enabled or not self.redis_client:
            return
            
        try:
            pattern = "hwp_extract:*"
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=pattern, count=100
                )
                if keys:
                    deleted_count += await self.redis_client.delete(*keys)
                if cursor == 0:
                    break
                    
            logger.info("Cache cleared", deleted_count=deleted_count)
        except Exception as e:
            logger.error("Cache clear error", error=str(e))
    
    def _calculate_ttl(self, extraction_type: str, data_size: int) -> int:
        """Calculate dynamic TTL based on extraction type and data size"""
        base_ttl = self.ttl
        
        # Longer TTL for larger, more expensive extractions
        if extraction_type == 'json':
            base_ttl = int(base_ttl * 1.5)  # JSON extractions are expensive
        elif extraction_type == 'text':
            base_ttl = int(base_ttl * 0.8)  # Text extractions are cheaper
        
        # Adjust based on size
        if data_size > 10 * 1024 * 1024:  # > 10MB
            base_ttl = int(base_ttl * 2)  # Double TTL for large files
        elif data_size > 1024 * 1024:  # > 1MB
            base_ttl = int(base_ttl * 1.5)
        
        # Cap at 24 hours
        return min(base_ttl, 86400)
    
    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache entries matching pattern"""
        if not self.enabled or not self.redis_client:
            return 0
            
        try:
            cursor = 0
            deleted_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=f"hwp_extract:{pattern}", count=100
                )
                if keys:
                    deleted_count += await self.redis_client.delete(*keys)
                if cursor == 0:
                    break
            
            logger.info("Cache pattern invalidated", pattern=pattern, deleted_count=deleted_count)
            return deleted_count
        except Exception as e:
            logger.error("Cache invalidation error", error=str(e), pattern=pattern)
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled or not self.redis_client:
            return {"enabled": False}
            
        try:
            info = await self.redis_client.info()
            pattern = "hwp_extract:*"
            cursor = 0
            key_count = 0
            
            while True:
                cursor, keys = await self.redis_client.scan(
                    cursor, match=pattern, count=100
                )
                key_count += len(keys)
                if cursor == 0:
                    break
            
            # Calculate hit rate from stats
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            total_ops = hits + misses
            hit_rate = (hits / total_ops * 100) if total_ops > 0 else 0
            
            # Get more detailed memory stats
            memory_stats = {
                "used": info.get("used_memory_human", "N/A"),
                "peak": info.get("used_memory_peak_human", "N/A"),
                "rss": info.get("used_memory_rss_human", "N/A"),
                "fragmentation_ratio": info.get("mem_fragmentation_ratio", 0)
            }
            
            return {
                "enabled": True,
                "connected": True,
                "key_count": key_count,
                "memory": memory_stats,
                "hit_rate": round(hit_rate, 2),
                "total_hits": hits,
                "total_misses": misses,
                "uptime_seconds": info.get("uptime_in_seconds", 0),
                "evicted_keys": info.get("evicted_keys", 0),
                "expired_keys": info.get("expired_keys", 0)
            }
        except Exception as e:
            logger.error("Cache stats error", error=str(e))
            return {"enabled": True, "connected": False, "error": str(e)}


# Global cache instance
cache_manager = CacheManager()


async def get_cache() -> CacheManager:
    """Get cache manager instance"""
    return cache_manager