"""
Celery application configuration with optimized worker scaling
"""
from celery import Celery
from kombu import Queue, Exchange
from app.core.config import settings
import os

# Create Celery instance
celery_app = Celery(
    "hwp_api",
    broker=settings.REDIS_URL or "redis://localhost:6379/0",
    backend=settings.REDIS_URL or "redis://localhost:6379/0",
    include=["app.tasks"]
)

# Define exchanges and queues for better task routing
default_exchange = Exchange('default', type='direct')
extraction_exchange = Exchange('extraction', type='direct')
priority_exchange = Exchange('priority', type='direct')

# Configure Celery with optimized settings
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution settings
    task_track_started=True,
    task_time_limit=settings.PROCESS_TIMEOUT,
    task_soft_time_limit=settings.PROCESS_TIMEOUT - 30,
    task_acks_late=True,  # Ensure tasks aren't lost on worker failure
    task_reject_on_worker_lost=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    result_compression='gzip',  # Compress results to save memory
    
    # Worker optimization settings
    worker_prefetch_multiplier=4,  # Increased for better throughput
    worker_max_tasks_per_child=100,  # Prevent memory leaks
    worker_disable_rate_limits=False,
    worker_concurrency=os.cpu_count() * 2,  # Dynamic based on CPU cores
    
    # Memory management
    worker_max_memory_per_child=200000,  # 200MB per worker child
    
    # Queue configuration with priorities
    task_queues=(
        Queue('default', exchange=default_exchange, routing_key='default', priority=5),
        Queue('extraction', exchange=extraction_exchange, routing_key='extraction', priority=7),
        Queue('heavy', exchange=extraction_exchange, routing_key='heavy', priority=3),
        Queue('priority', exchange=priority_exchange, routing_key='priority', priority=10),
    ),
    
    # Task routing
    task_routes={
        "app.tasks.extract_file_async": {"queue": "extraction", "priority": 7},
        "app.tasks.process_large_file": {"queue": "heavy", "priority": 3},
        "app.tasks.extract_priority": {"queue": "priority", "priority": 10},
        "app.tasks.cleanup_old_results": {"queue": "default", "priority": 2},
    },
    
    # Beat schedule for periodic tasks
    beat_schedule={
        'cleanup-old-results': {
            'task': 'app.tasks.cleanup_old_results',
            'schedule': 3600.0,  # Every hour
        },
        'cache-warmup': {
            'task': 'app.tasks.cache_warmup',
            'schedule': 300.0,  # Every 5 minutes
        },
    },
    
    # Performance monitoring
    task_send_sent_event=True,
    worker_send_task_events=True,
    
    # Connection pooling
    broker_pool_limit=10,
    redis_max_connections=20,
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute
    task_max_retries=3,
)

# Configure worker autoscaling if environment variable is set
if os.getenv('CELERY_AUTOSCALE'):
    max_workers = int(os.getenv('CELERY_AUTOSCALE_MAX', os.cpu_count() * 4))
    min_workers = int(os.getenv('CELERY_AUTOSCALE_MIN', os.cpu_count()))
    celery_app.conf.worker_autoscaler = f'{max_workers},{min_workers}'