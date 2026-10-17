#!/usr/bin/env bash
set -euo pipefail
image=${1:?Usage: smoke.sh IMAGE [PLATFORM]}
platform=${2:-linux/amd64}
container="minio-qualification-${RANDOM}-${RANDOM}"
scratch=$(mktemp -d)
cleanup() {
  status=$?
  if (( status != 0 )); then docker logs "$container" >&2 || true; fi
  docker rm -fv "$container" >/dev/null 2>&1 || true
  rm -rf "$scratch"
  exit "$status"
}
trap cleanup EXIT
docker run --rm --platform "$platform" "$image" minio --version | tee "$scratch/minio-version"
docker run --rm --platform "$platform" "$image" mc --version | tee "$scratch/mc-version"
python3 - "$scratch" <<'PY'
import json, pathlib, sys
inputs = json.loads(pathlib.Path('inputs.json').read_text())
for name, key in [('minio', 'server'), ('mc', 'client')]:
    version = (pathlib.Path(sys.argv[1]) / f'{name}-version').read_text()
    assert inputs[key]['release'] in version and inputs[key]['commit'] in version, version
PY
docker run --detach --platform "$platform" --name "$container" \
  -e MINIO_ROOT_USER=qualification_root -e MINIO_ROOT_PASSWORD=qualification_root_secret \
  "$image" server /data --console-address :9001 >/dev/null
ready=false
for (( attempt=0; attempt<60; attempt++ )); do
  if docker exec "$container" mc ready local; then ready=true; break; fi
  sleep 1
done
[[ $ready == true ]]
mc() { docker exec "$container" mc "$@"; }
must_deny() {
  if "$@"; then echo "Unexpected authorization success: $*" >&2; return 1; fi
}
mc alias set root http://127.0.0.1:9000 qualification_root qualification_root_secret
mc mb root/qualification
printf 'owned MinIO image qualification\n' > "$scratch/object"
docker cp "$scratch/object" "$container:/tmp/qualification-object"
mc cp /tmp/qualification-object root/qualification/object
mc cat root/qualification/object > "$scratch/download"
cmp "$scratch/object" "$scratch/download"
cat > "$scratch/policy.json" <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket"],"Resource":["arn:aws:s3:::qualification"]},{"Effect":"Allow","Action":["s3:GetObject"],"Resource":["arn:aws:s3:::qualification/*"]}]}
JSON
docker cp "$scratch/policy.json" "$container:/tmp/reader-policy.json"
mc admin user add root qualification_reader qualification_reader_secret
mc admin policy create root qualification-reader /tmp/reader-policy.json
mc admin policy attach root qualification-reader --user qualification_reader
mc alias set reader http://127.0.0.1:9000 qualification_reader qualification_reader_secret
mc cat reader/qualification/object > "$scratch/reader-download"
cmp "$scratch/object" "$scratch/reader-download"
must_deny mc cp /tmp/qualification-object reader/qualification/forbidden
must_deny mc rm reader/qualification/object
must_deny mc admin user add reader unauthorized unauthorized_secret
mc stat root/qualification/object
mc rm root/qualification/object
mc rb root/qualification
echo "PASS: $platform versions, readiness, object round trip, restricted reader, cleanup"
