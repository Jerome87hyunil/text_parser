#!/usr/bin/env bash
# Render build script

set -e  # Exit on error

echo "Starting build process..."

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Collect static files if needed
# python manage.py collectstatic --noinput

echo "Build completed successfully!"