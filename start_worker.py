#!/usr/bin/env python3
"""
Start Celery worker
"""
import os
import sys

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.celery_app import celery_app

if __name__ == "__main__":
    # Start worker with info log level
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=2',
        '-Q', 'default,extraction,heavy'
    ])