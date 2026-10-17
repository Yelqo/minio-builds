#!/usr/bin/env bash
set -euo pipefail
image=${1:?Usage: verify-distribution.sh IMAGE@DIGEST PLATFORM}
platform=${2:?Supply linux/amd64 or linux/arm64}
[[ $image =~ ^ghcr.io/yelqo/minio-builds@sha256:[0-9a-f]{64}$ ]]
[[ $platform == linux/amd64 || $platform == linux/arm64 ]]
daemon="minio-distribution-${RANDOM}-${RANDOM}"
client=$(mktemp -d)
cleanup() {
  status=$?
  if (( status != 0 )); then docker logs "$daemon" >&2 || true; fi
  docker rm -fv "$daemon" >/dev/null 2>&1 || true
  rm -rf "$client"
  exit "$status"
}
trap cleanup EXIT
# Fresh /var/lib/docker lives in a disposable daemon volume, never the shared
# runner image store. The inner client has no auth/config or inherited context.
docker run --detach --privileged --name "$daemon" \
  -e DOCKER_TLS_CERTDIR= -p 127.0.0.1::2375 \
  docker:29.8.2-dind@sha256:1e08cdb63405ca788aea94ef35b792d1e299607c667d33d7bcbcae1fd2611ced \
  --tls=false >/dev/null
port=$(docker port "$daemon" 2375/tcp)
host="tcp://$port"
ready=false
for (( attempt=0; attempt<60; attempt++ )); do
  if DOCKER_HOST="$host" DOCKER_CONFIG="$client" docker info >/dev/null 2>&1; then ready=true; break; fi
  sleep 1
done
[[ $ready == true ]]
(
  unset DOCKER_CONTEXT DOCKER_AUTH_CONFIG
  export DOCKER_HOST="$host" DOCKER_CONFIG="$client"
  [[ $(docker image ls -q | wc -l) == 0 ]]
  docker manifest inspect "$image" > "$client/manifest.json"
  python3 - "$client/manifest.json" <<'PY'
import json, sys
entries = json.load(open(sys.argv[1]))['manifests']
architectures = {e['platform']['architecture'] for e in entries if e['platform']['os'] == 'linux'}
assert architectures == {'amd64', 'arm64'}, architectures
PY
  docker pull --platform "$platform" "$image"
  bash scripts/smoke.sh "$image" "$platform"
)
