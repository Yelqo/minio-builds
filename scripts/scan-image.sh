#!/usr/bin/env bash
set -euo pipefail
platform=${1:?Usage: scan-image.sh linux/amd64|linux/arm64}
[[ $platform == linux/amd64 || $platform == linux/arm64 ]]
mkdir -p reports
tools=$(mktemp -d)
trap 'rm -rf "$tools"' EXIT
read -r version checksum digest < <(python3 - <<'PY'
import json
p = json.load(open('monitoring.json'))
print(p['grype']['version'], p['grype']['linux_amd64_sha256'], p['digest'])
PY
)
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/anchore/grype/releases/download/v$version/grype_${version}_linux_amd64.tar.gz" \
  --output "$tools/grype.tar.gz"
printf '%s  %s\n' "$checksum" "$tools/grype.tar.gz" | sha256sum -c -
tar -xzf "$tools/grype.tar.gz" -C "$tools" grype
export GRYPE_DB_CACHE_DIR="$tools/db" GRYPE_DB_AUTO_UPDATE=true
export GRYPE_DB_VALIDATE_AGE=true GRYPE_DB_MAX_ALLOWED_BUILT_AGE=120h
export GRYPE_CHECK_FOR_APP_UPDATE=false
"$tools/grype" "registry:ghcr.io/yelqo/minio-builds@$digest" --platform "$platform" -o json > reports/grype.json
python3 scripts/monitor.py scan --report reports/grype.json
