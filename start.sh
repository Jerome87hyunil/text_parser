#!/bin/bash
set -e

# Use PORT environment variable provided by Render, default to 8000
PORT=${PORT:-8000}

echo "Starting FastAPI application on port $PORT..."

# Start the application
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --workers 4 \
    --loop uvloop \
    --access-log \
    --log-level info