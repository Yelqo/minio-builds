#!/bin/sh
set -eu
# shellcheck source=/dev/null
. /inputs.env
export CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off
mkdir -p /out
cd /src/minio
GOOS=linux GOARCH="$TARGETARCH" go build -mod=vendor -trimpath -buildvcs=false \
  -ldflags="-s -w -X github.com/minio/minio/cmd.Version=$MINIO_VERSION -X github.com/minio/minio/cmd.ReleaseTag=$MINIO_RELEASE -X github.com/minio/minio/cmd.CommitID=$MINIO_COMMIT -X github.com/minio/minio/cmd.ShortCommitID=$(printf %.12s "$MINIO_COMMIT") -X github.com/minio/minio/cmd.CopyrightYear=2025" \
  -o /out/minio .
cd /src/mc
GOOS=linux GOARCH="$TARGETARCH" go build -mod=vendor -trimpath -buildvcs=false \
  -ldflags="-s -w -X github.com/minio/mc/cmd.Version=$MC_VERSION -X github.com/minio/mc/cmd.ReleaseTag=$MC_RELEASE -X github.com/minio/mc/cmd.CommitID=$MC_COMMIT -X github.com/minio/mc/cmd.ShortCommitID=$(printf %.12s "$MC_COMMIT") -X github.com/minio/mc/cmd.CopyrightYear=2025" \
  -o /out/mc .
