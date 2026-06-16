#!/usr/bin/env bash
set -e

echo "Starting Celery worker..."
exec celery -A app.worker.celery_app.celery_app worker --loglevel=info
