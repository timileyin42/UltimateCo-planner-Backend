#!/bin/bash
set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
    echo "Running database migrations (alembic upgrade head)..."
    alembic upgrade head
else
    echo "Skipping database migrations (RUN_MIGRATIONS != true)..."
fi

echo "Starting application..."
exec "$@"
