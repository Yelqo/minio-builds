#!/bin/sh
set -eu
if [ "${1:-}" = server ]; then
  # Explicit S3v4 skips endpoint probing before startup and safely serializes
  # credentials for independent `docker exec mc ready local` health checks.
  mc alias set --api S3v4 local http://127.0.0.1:9000 \
    "${MINIO_ROOT_USER:-minioadmin}" "${MINIO_ROOT_PASSWORD:-minioadmin}" >/dev/null
  exec minio "$@"
fi
exec "$@"
