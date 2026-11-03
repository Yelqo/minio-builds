#!/usr/bin/env bash
set -euo pipefail
platform=${1:?Usage: scan-image.sh linux/amd64|linux/arm64 [docker:LOCAL_IMAGE|registry:IMAGE@DIGEST]}
(( $# <= 2 ))
[[ $platform == linux/amd64 || $platform == linux/arm64 ]]
case $(uname -m) in
  x86_64) host_arch=amd64 ;;
  aarch64|arm64) host_arch=arm64 ;;
  *) echo 'Scanner requires a Linux amd64 or arm64 host.' >&2; exit 1 ;;
esac
mkdir -p reports
tools=$(mktemp -d)
trap 'rm -rf "$tools"' EXIT
read -r version checksum digest < <(python3 - "$host_arch" <<'PY'
import json, sys
p = json.load(open('monitoring.json'))
print(p['grype']['version'], p['grype'][f'linux_{sys.argv[1]}_sha256'], p['digest'])
PY
)
source=${2:-registry:ghcr.io/yelqo/minio-builds@$digest}
[[ $source == docker:?* || $source =~ ^registry:ghcr.io/yelqo/minio-builds@sha256:[0-9a-f]{64}$ ]]
python3 - "$platform" "$source" "$version" <<'PY'
import json, pathlib, sys
pathlib.Path('reports/scan-target.json').write_text(json.dumps({
    'platform': sys.argv[1], 'source': sys.argv[2], 'scanner_version': sys.argv[3],
}, indent=2) + '\n')
PY
curl --fail --silent --show-error --location --retry 3 \
  "https://github.com/anchore/grype/releases/download/v$version/grype_${version}_linux_${host_arch}.tar.gz" \
  --output "$tools/grype.tar.gz"
printf '%s  %s\n' "$checksum" "$tools/grype.tar.gz" | sha256sum -c -
tar -xzf "$tools/grype.tar.gz" -C "$tools" grype
export GRYPE_DB_CACHE_DIR="$tools/db" GRYPE_DB_AUTO_UPDATE=true
export GRYPE_DB_VALIDATE_AGE=true GRYPE_DB_MAX_ALLOWED_BUILT_AGE=120h
export GRYPE_CHECK_FOR_APP_UPDATE=false
"$tools/grype" "$source" --platform "$platform" -o json > reports/grype.json
python3 scripts/monitor.py scan --report reports/grype.json
