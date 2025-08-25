"""
Memory management utilities
"""
import gc
import psutil
import structlog
from typing import Optional
from contextlib import contextmanager
import asyncio

logger = structlog.get_logger()


class MemoryManager:
    """
    Manage memory usage and prevent OOM errors
    """
    
    def __init__(self, threshold_percent: float = 80.0):
        self.threshold_percent = threshold_percent
        self.process = psutil.Process()
        
    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics"""
        memory_info = self.process.memory_info()
        system_memory = psutil.virtual_memory()
        
        return {
            "process_rss_mb": memory_info.rss / 1024 / 1024,
            "process_vms_mb": memory_info.vms / 1024 / 1024,
            "system_percent": system_memory.percent,
            "system_available_mb": system_memory.available / 1024 / 1024
        }
    
    def check_memory_available(self, required_mb: float) -> bool:
        """Check if enough memory is available"""
        stats = self.get_memory_usage()
        available_mb = stats["system_available_mb"]
        
        # Leave some buffer
        return available_mb > (required_mb * 1.5)
    
    def force_cleanup(self):
        """Force garbage collection"""
        before = self.get_memory_usage()
        gc.collect()
        after = self.get_memory_usage()
        
        freed_mb = before["process_rss_mb"] - after["process_rss_mb"]
        logger.info(f"Memory cleanup freed {freed_mb:.2f} MB")
        
        return freed_mb
    
    @contextmanager
    def memory_limit_context(self, max_mb: float):
        """Context manager to limit memory usage"""
        initial_usage = self.get_memory_usage()
        
        try:
            yield
        finally:
            current_usage = self.get_memory_usage()
            used_mb = current_usage["process_rss_mb"] - initial_usage["process_rss_mb"]
            
            if used_mb > max_mb:
                logger.warning(
                    f"Memory limit exceeded: used {used_mb:.2f} MB, limit {max_mb:.2f} MB"
                )
                self.force_cleanup()
    
    async def monitor_memory_async(self, interval: float = 5.0):
        """Monitor memory usage asynchronously"""
        while True:
            stats = self.get_memory_usage()
            
            if stats["system_percent"] > self.threshold_percent:
                logger.warning(
                    "High memory usage detected",
                    **stats
                )
                self.force_cleanup()
            
            await asyncio.sleep(interval)


# Global memory manager instance
memory_manager = MemoryManager()