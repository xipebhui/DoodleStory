#!/usr/bin/env sh

set -eu

mkdir -p /app/data/storage

alembic upgrade head

exec "$@"
