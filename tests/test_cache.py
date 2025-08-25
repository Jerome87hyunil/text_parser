"""
Test cases for cache functionality
"""
import pytest
from app.core.cache import CacheManager
import asyncio


class TestCacheManager:
    """Test cases for CacheManager"""
    
    @pytest.fixture
    async def cache(self):
        """Create a test cache manager"""
        cache = CacheManager()
        # Use test database (db 1)
        cache.redis_url = "redis://localhost:6379/1"
        await cache.connect()
        yield cache
        # Cleanup
        await cache.clear_all()
        await cache.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test cache when disabled"""
        cache = CacheManager()
        cache.enabled = False
        await cache.connect()
        
        # Should return None when disabled
        result = await cache.get(b"test", "test_key")
        assert result is None
        
        # Set should not fail when disabled
        await cache.set(b"test", "test_key", {"data": "test"})
        
        await cache.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_connection_failure(self):
        """Test cache with connection failure"""
        cache = CacheManager()
        cache.redis_url = "redis://invalid:6379"
        await cache.connect()
        
        # Should be disabled after connection failure
        assert cache.enabled is False
        
        # Should return None when connection failed
        result = await cache.get(b"test", "test_key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_key_generation(self, cache):
        """Test cache key generation"""
        content1 = b"test content 1"
        content2 = b"test content 2"
        
        key1 = cache._generate_cache_key(content1, "json")
        key2 = cache._generate_cache_key(content2, "json")
        key3 = cache._generate_cache_key(content1, "text")
        
        # Different content should have different keys
        assert key1 != key2
        
        # Same content with different type should have different keys
        assert key1 != key3
        
        # Same content and type should have same key
        key4 = cache._generate_cache_key(content1, "json")
        assert key1 == key4
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache):
        """Test basic cache set and get"""
        if not cache.enabled:
            pytest.skip("Redis not available")
            
        content = b"test content"
        data = {"text": "extracted text", "metadata": {"title": "Test"}}
        
        # Set cache
        await cache.set(content, "json", data)
        
        # Get cache
        result = await cache.get(content, "json")
        assert result == data
        
        # Different type should miss
        result = await cache.get(content, "text")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_ttl(self, cache):
        """Test cache TTL"""
        if not cache.enabled:
            pytest.skip("Redis not available")
            
        content = b"test content"
        data = {"text": "test"}
        
        # Set cache with short TTL
        cache.ttl = 1  # 1 second
        await cache.set(content, "test", data)
        
        # Should exist immediately
        result = await cache.get(content, "test")
        assert result == data
        
        # Wait for expiration
        await asyncio.sleep(2)
        
        # Should be expired
        result = await cache.get(content, "test")
        assert result is None