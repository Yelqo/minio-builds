#!/usr/bin/env bash
set -euo pipefail
sources=$(realpath "${1:?Usage: rebuild.sh EXTRACTED_SRC IMAGE}")
image=${2:?Supply a local image name}
builder=$(python3 -c 'import json; print(json.load(open("inputs.json"))["builder"])')
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cp -a "$sources" "$scratch/src"
cp Dockerfile inputs.json LICENSE NOTICE.md README.md SECURITY.md "$scratch/"
cp -a scripts "$scratch/scripts"
cp .build/inputs.env "$scratch/inputs.env"
cat > "$scratch/Dockerfile" <<'DOCKER'
ARG BUILDER
FROM --platform=$BUILDPLATFORM ${BUILDER} AS sources
COPY src /src
COPY inputs.env /inputs.env
COPY scripts /recipe/scripts
RUN mkdir -p /licenses/go && cp /usr/local/go/LICENSE /usr/local/go/PATENTS /licenses/go/ && \
    find /src -type f \( -iname '*license*' -o -iname '*notice*' -o -iname '*copying*' \
    -o -iname '*copyright*' -o -iname '*credits*' -o -iname '*patents*' \) \
    -exec cp --parents -t /licenses {} +
DOCKER
# Reuse the reviewed offline compiler and identical runtime recipe.
sed -n '/^FROM sources AS builder/,$p' Dockerfile >> "$scratch/Dockerfile"
runtime=$(python3 -c 'import json; print(json.load(open("inputs.json"))["runtime"])')
sed -i "1a ARG RUNTIME=$runtime" "$scratch/Dockerfile"
docker buildx build --network=none --load --build-arg "BUILDER=$builder" -t "$image" "$scratch"
