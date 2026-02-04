"""
Memory management utilities

v2.0: RSS 기반 메모리 모니터링으로 변경
- 시스템 메모리 대신 프로세스 RSS 기준 사용
- Railway 512MB 환경에 최적화된 임계값
- 주기적 GC 대신 임계값 초과 시에만 GC 실행
"""
import gc
import psutil
import structlog
from typing import Optional
from contextlib import contextmanager
import asyncio

logger = structlog.get_logger()

# Railway 환경 메모리 임계값 (MB)
RSS_WARNING_MB = 300  # 300MB 초과 시 경고
RSS_CRITICAL_MB = 400  # 400MB 초과 시 GC 강제 실행


class MemoryManager:
    """
    Manage memory usage and prevent OOM errors

    v2.0: RSS 기반 모니터링
    - 시스템 메모리 대신 프로세스 RSS 기준
    - 컨테이너 환경에서 더 정확한 측정
    """

    def __init__(self,
                 rss_warning_mb: float = RSS_WARNING_MB,
                 rss_critical_mb: float = RSS_CRITICAL_MB):
        self.rss_warning_mb = rss_warning_mb
        self.rss_critical_mb = rss_critical_mb
        self.process = psutil.Process()
        self._last_gc_time = 0
        self._gc_cooldown_seconds = 30  # GC 최소 간격

    def get_memory_usage(self) -> dict:
        """Get current memory usage statistics (v2.0: RSS 중심)"""
        memory_info = self.process.memory_info()
        rss_mb = memory_info.rss / 1024 / 1024

        # RSS 기반 상태 결정
        if rss_mb > self.rss_critical_mb:
            status = "critical"
        elif rss_mb > self.rss_warning_mb:
            status = "warning"
        else:
            status = "ok"

        return {
            "process_rss_mb": rss_mb,
            "process_vms_mb": memory_info.vms / 1024 / 1024,
            "status": status,
            "threshold_warning_mb": self.rss_warning_mb,
            "threshold_critical_mb": self.rss_critical_mb,
        }

    def check_memory_available(self, required_mb: float) -> bool:
        """Check if enough memory is available based on RSS"""
        stats = self.get_memory_usage()
        # RSS + 요청량이 critical 임계값을 넘지 않으면 허용
        return (stats["process_rss_mb"] + required_mb) < self.rss_critical_mb

    def force_cleanup(self) -> float:
        """Force garbage collection with cooldown"""
        import time
        current_time = time.time()

        # GC 쿨다운 체크 (너무 자주 실행 방지)
        if current_time - self._last_gc_time < self._gc_cooldown_seconds:
            return 0.0

        before = self.get_memory_usage()
        gc.collect()
        after = self.get_memory_usage()

        self._last_gc_time = current_time
        freed_mb = before["process_rss_mb"] - after["process_rss_mb"]

        if freed_mb > 0:
            logger.info(f"Memory cleanup freed {freed_mb:.2f} MB",
                       before_mb=before["process_rss_mb"],
                       after_mb=after["process_rss_mb"])

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

    async def monitor_memory_async(self, interval: float = 10.0):
        """Monitor memory usage asynchronously (v2.0: RSS 기반)

        Args:
            interval: 모니터링 간격 (초) - 기본 10초로 증가
        """
        logger.info("Memory monitoring started",
                   warning_threshold_mb=self.rss_warning_mb,
                   critical_threshold_mb=self.rss_critical_mb)

        while True:
            try:
                stats = self.get_memory_usage()
                rss_mb = stats["process_rss_mb"]

                if stats["status"] == "critical":
                    logger.error(
                        "CRITICAL: Memory usage exceeds threshold",
                        rss_mb=rss_mb,
                        threshold_mb=self.rss_critical_mb
                    )
                    self.force_cleanup()

                elif stats["status"] == "warning":
                    logger.warning(
                        "WARNING: Memory usage elevated",
                        rss_mb=rss_mb,
                        threshold_mb=self.rss_warning_mb
                    )
                    # Warning 상태에서는 GC 시도하지 않음 (불필요한 CPU 사용 방지)

            except Exception as e:
                logger.error("Memory monitoring error", error=str(e))

            await asyncio.sleep(interval)


# Global memory manager instance (v2.0: RSS 기반 임계값)
memory_manager = MemoryManager()