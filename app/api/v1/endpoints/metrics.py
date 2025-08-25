"""
Prometheus metrics endpoint
"""
from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import psutil

# Define metrics
extraction_counter = Counter(
    'hwp_api_extractions_total',
    'Total number of extractions',
    ['file_type', 'extraction_type', 'status']
)

extraction_duration = Histogram(
    'hwp_api_extraction_duration_seconds',
    'Time spent processing extractions',
    ['file_type', 'extraction_type']
)

active_tasks = Gauge(
    'hwp_api_active_tasks',
    'Number of active background tasks'
)

system_cpu_usage = Gauge(
    'hwp_api_system_cpu_percent',
    'System CPU usage percentage'
)

system_memory_usage = Gauge(
    'hwp_api_system_memory_percent',
    'System memory usage percentage'
)

router = APIRouter()


def update_system_metrics():
    """Update system metrics"""
    system_cpu_usage.set(psutil.cpu_percent(interval=0.1))
    system_memory_usage.set(psutil.virtual_memory().percent)


@router.get("/metrics",
    tags=["monitoring"],
    summary="Prometheus 메트릭스",
    response_class=Response,
    responses={
        200: {
            "description": "Prometheus 형식의 메트릭스",
            "content": {
                "text/plain": {
                    "example": """# HELP hwp_api_extractions_total Total number of extractions
# TYPE hwp_api_extractions_total counter
hwp_api_extractions_total{file_type="hwp",extraction_type="json",status="success"} 42.0
"""
                }
            }
        }
    }
)
async def get_metrics():
    """
    Prometheus 형식의 메트릭스를 반환합니다.
    
    수집되는 메트릭:
    - 추출 요청 수 (파일 타입, 추출 타입, 상태별)
    - 추출 처리 시간
    - 활성 백그라운드 작업 수
    - 시스템 CPU 사용률
    - 시스템 메모리 사용률
    """
    # Update system metrics
    update_system_metrics()
    
    # Generate metrics
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


# Export functions to track metrics
def track_extraction(file_type: str, extraction_type: str, status: str):
    """Track extraction metrics"""
    extraction_counter.labels(
        file_type=file_type,
        extraction_type=extraction_type,
        status=status
    ).inc()


def track_extraction_duration(file_type: str, extraction_type: str, duration: float):
    """Track extraction duration"""
    extraction_duration.labels(
        file_type=file_type,
        extraction_type=extraction_type
    ).observe(duration)