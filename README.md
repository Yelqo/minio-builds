# Owned MinIO builds

Unofficial MinIO Community Edition server **and mc**, independently built and
published by Yelqo for isolated integration testing. Read [SECURITY.md](SECURITY.md)
for the source choice and remaining upstream vulnerabilities. Distribution
ownership is not upstream maintenance. License and attribution: [NOTICE.md](NOTICE.md).

Image: `ghcr.io/yelqo/minio-builds`. Releases use distinct `vMAJOR.MINOR.PATCH`
identities and publish a multi-platform manifest for Linux amd64 and arm64.
Consumers must use `ghcr.io/yelqo/minio-builds:vVERSION@sha256:MANIFEST_DIGEST`
from a **published, qualified release**, never a moving tag or candidate alone.
There is no `latest` tag. Never rebuild or overwrite a consumed version; use a
new release identity for changed source, toolchain, base or recipe inputs.

## Build and inspect

`inputs.json` records full server/client commit IDs, human-readable releases,
source archive SHA-256 values, toolchain/runtime multi-platform digests, and
the SBOM generator digest. Actions are pinned to full revisions. Source
archives are checked before unpacking. Go's recorded `go.mod`/`go.sum` files
and checksum verification fix dependencies; vendor sources are preserved.
Compilation disables networking and automatic toolchain downloads.

```sh
python3 scripts/fetch-sources.py
docker buildx build --load --platform linux/amd64 -t minio-builds:local .
bash scripts/smoke.sh minio-builds:local linux/amd64
docker buildx build --target source-bundle --output type=local,dest=dist .
```

The container accepts `server /data`, optionally `--console-address :9001`,
and `MINIO_ROOT_USER`/`MINIO_ROOT_PASSWORD`. Data and policy paths can be
mounted normally. `docker exec CONTAINER mc ready local` works without a
separate client image. Root execution matches the existing test contract.
Only throwaway test credentials and networks are appropriate.

## Release process

1. Review inputs, remaining advisories and recipe changes on `main`. The
   validation workflow builds and smoke-tests each native architecture without
   registry write permissions. This includes version/commit checks, readiness,
   bucket/object round trips and restricted-user policy enforcement.
2. Push a new `vMAJOR.MINOR.PATCH` tag whose commit is on `main`. The release
   workflow rejects existing version manifests. Its repository-scoped Actions
   token alone writes packages, provenance and release assets; no personal
   registry token is needed.
3. Both architectures are built and tested before publication of their
   versioned platform candidates. The final manifest, GitHub build attestation,
   BuildKit provenance, SBOMs, source/recipe archive, dependency locks, checksums
   and `release.json` are attached to a draft GitHub release.
4. **First publication:** GHCR may create a **private** package even though
   this repository is public. The owner must open
   https://github.com/users/Yelqo/packages/container/minio-builds/settings and
   set package visibility to **Public**. The workflow's OCI source label links
   the package to this repository. If Actions package access is not inherited,
   grant this repository Actions write access in the package settings. Record
   any setting actually needed in release notes. Repository visibility alone
   does not establish anonymous access. No consumer change is allowed yet.
5. Verification jobs run each published architecture in a fresh disposable
   Docker daemon with an empty client configuration and no registry login.
   They resolve both manifest entries, pull the exact manifest digest, verify
   the GitHub attestation against this repository, tagged source commit and
   `.github/workflows/release.yml` identity, then repeat all smoke checks.
   Cleanup runs after success and failure. A manifest-only check is insufficient.
6. If the first verification failed while the package was private, change the
   setting and **rerun failed jobs only**. Do not rerun builds to replace a tag.
   The release becomes public only after both verification jobs pass. Record
   the verified digest and workflow URL in the consumer PR, run existing
   recovery and full integration qualification, and retain corpus/latency gates.

No release is qualified merely because an image/tag exists. Failed verification
leaves the GitHub release in draft; platform candidates must not be consumed.
Release evidence records actual inputs and architecture manifest digests. This
is controlled-input rebuilding and traceability; bit-for-bit reproducibility
has not been established.

## Rebuild when upstream disappears

Download `corresponding-source.tar.gz`, `release.json`, `SHA256SUMS` and the SBOMs
from the same release as the image. Verify checksums and provenance first.
The archive contains full upstream source and vendored dependency source,
original source archives, locks, licenses, and recipe, under owner-controlled
GitHub release storage. No upstream Git repository is needed to inspect it.

```sh
tar -xzf corresponding-source.tar.gz
cd recipe
mkdir -p .build
cp ../archives/*.tar.gz .build/
python3 scripts/fetch-sources.py  # verifies cached archives; no fetch
# Restore vendors to the Docker sources stage using the archived src trees.
# Build the two trees with scripts/compile.sh in the recorded builder image,
# GOTOOLCHAIN=local, GOPROXY=off and -mod=vendor; see scripts/rebuild.sh.
bash scripts/rebuild.sh ../src minio-builds:rebuilt
```

Base/toolchain images must still be retrievable by their recorded digests or
retained in your own OCI archive. This project preserves corresponding source
for the bundled applications and dependencies; it does not promise perpetual
availability of Docker Hub's toolchain/distribution images.
