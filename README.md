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

## Scheduled maintenance and landscape review

`maintenance.yml` runs weekly on Monday at 05:17 UTC and supports manual dispatch.
It checks the consumed digest in `monitoring.json`, independently of whichever
producer release was published most recently. Update that record, including its
original build revision, when a consumer moves to another qualified release.

The workflow collects upstream server/client advisories, releases, repository
status, community-project READMEs/releases/issues, GitHub and Hacker News samples,
Go releases, monitoring-tool versions, official-image manifest observations, and
builder/runtime tag digests. It also scans **both** image architectures with a
checksum-pinned Grype binary and a fresh, age-validated vulnerability database,
and repeats anonymous fresh-store pulls, original release provenance verification,
and storage smoke checks on native amd64/arm64 runners.

New/revised upstream advisories, a different upstream release or base digest,
newly reachable official image candidates, or incomplete primary evidence fail
the evidence gate for human review. Fixable High/Critical scanner findings fail
the security jobs. Full JSON reports retain all findings, including unfixed and
unknown-fix vulnerabilities. A failed scanner or unavailable database is a failed
check, not a clean scan. The initial 2026-10-17 scan already identified fixable
toolchain/dependency findings; compatibility qualification did not establish
absence of vulnerabilities. Inspect the current report before deciding changes.

`monitoring-advisories.json` records observed advisory timestamps. It is an
inventory for detecting new/revised publications, **not** a vulnerability
suppression or risk-acceptance list. Update it only after reviewing the referenced
advisories and documenting any required follow-up. Image updates require a new
reviewed release and consumer qualification; scheduled jobs never publish images,
edit pins, or update this inventory automatically.

After maintenance completes, `landscape-review.lock.yml` starts a bounded,
read-only Copilot review, including when maintenance reports security findings.
It evaluates captured evidence, identifies actionable updates and community
direction with dated citations, and uploads `landscape-review.md` as a run
artifact. Missing sources produce an incomplete assessment. Registry manifest
access is only a candidate lead; adoption still requires complete anonymous pulls,
edition/support assessment, and compatibility qualification. Community sampling
does not measure consensus. The agent has no repository write permissions, issue
or PR output tools, publication credentials, or automatic issue reporters. Its
only safe output is the report artifact. Inference has turn/tool limits and a
10-AI-credit guardrail for each of the review and output-detection stages; no paid
subscription or additional billing is enabled. Both stages use the concrete
`gpt-5.6-luna-free-auto` route observed in the account's Copilot model catalog.
The framework's generic `auto` alias selected an unsupported catalog model during
verification, so it is not used. If the recorded route becomes unavailable, the
review must fail explicitly rather than silently select another model.

To activate inference in this personal repository, add the Actions secret
`COPILOT_GITHUB_TOKEN` using a fine-grained PAT from an account with Copilot
access, with **Account permissions → Copilot Requests: Read** and no repository
write permissions. [GitHub's authentication instructions](https://github.github.com/gh-aw/reference/auth/#copilot_github_token)
describe this path. Never put a token in source or a report. With no credential,
the AI workflow fails explicitly; evidence collection, scans and distribution
checks still run independently. Free-plan quota/model access must be verified by
an actual inference run; this setup does not assume unlimited free inference.

Reports are in each run's job summaries and artifacts (90-day retention). GitHub
workflow failure notifications provide alerts without granting an agent issue
write access. Review the most recent run's date: GitHub can disable public-repo
schedules after 60 days without repository activity. Manual dispatch remains an
available recovery path; an external missed-run monitor is needed if this must be
an always-on alerting service.

Regenerate the checked-in agent lock with the checksum-pinned gh-aw compiler
version in `monitoring.json`: `gh aw compile landscape-review`. Commit the Markdown,
generated lock and `.github/aw/actions-lock.json` together. Keep every generated
job free of repository write permissions. Run `python3 -m unittest discover -s
scripts -p 'test_*.py' -v` after changing monitoring policy or report parsing.
