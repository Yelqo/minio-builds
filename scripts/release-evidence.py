#!/usr/bin/env python3
"""Record the actual manifest and immutable build inputs beside the source."""
import json
import os
from pathlib import Path
import sys

version, digest = sys.argv[1:]
inputs = json.loads(Path("inputs.json").read_text())
manifest = json.loads(Path("dist/manifest.json").read_text())
platforms = {
    entry["platform"]["architecture"]: entry["digest"]
    for entry in manifest["manifests"]
    if entry["platform"]["os"] == "linux"
}
assert set(platforms) == {"amd64", "arm64"}, platforms
workflow = f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
evidence = {
    "image": f"ghcr.io/yelqo/minio-builds:{version}@{digest}",
    "digest": digest,
    "version": version,
    "build_repository": os.environ["GITHUB_REPOSITORY"],
    "build_revision": os.environ["GITHUB_SHA"],
    "workflow": workflow,
    "platform_manifests": platforms,
    "inputs": inputs,
    "qualification": "Draft until both independent anonymous-pull qualification jobs pass",
    "reproducibility": "Controlled-input build; bit-for-bit reproducibility not verified",
}
Path("dist/release.json").write_text(json.dumps(evidence, indent=2) + "\n")
Path("dist/release-notes.md").write_text(
    f"Unofficial MinIO Community Edition, independently published by Yelqo.\n\n"
    f"Image: `{evidence['image']}`\n\nBuild revision: `{evidence['build_revision']}`. "
    f"[Build and qualification evidence]({workflow}).\n\n"
    "This release is promoted from draft only after amd64 and arm64 anonymous "
    "fresh-store pulls, constrained provenance verification, readiness and S3/policy checks pass.\n\n"
    "Source, vendored dependencies, complete recipe, licenses, dependency locks, platform SBOMs, "
    "checksums and release inputs accompany this release. BuildKit SBOM and provenance "
    "are also attached to the platform OCI indexes; GitHub build provenance binds the final digest.\n\n"
    "**Known upstream vulnerabilities remain.** See SECURITY.md at the build revision. "
    "For isolated disposable tests only; distribution ownership is not security support. "
    "Bit-for-bit reproducibility is not claimed.\n\n"
    "On first publication the owner may need to change GHCR package visibility to Public "
    "and grant repository Actions package access. Any actual setting is recorded in the "
    "consumer qualification notes. Public pull checks are mandatory.\n"
)
