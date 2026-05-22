#!/bin/sh
set -e

# Railway injects PORT at runtime
exec gunicorn \
  --bind "0.0.0.0:${PORT:-5050}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 120 \
  --chdir /app/src \
  app:app
