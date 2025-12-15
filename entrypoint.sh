#!/bin/bash
set -e

echo "Running database migrations (alembic upgrade head)..."
alembic upgrade head

echo "Starting application..."
exec "$@"
