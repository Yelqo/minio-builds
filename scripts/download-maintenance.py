#!/usr/bin/env python3
"""Download only artifacts produced by our main-branch maintenance workflow."""
import json
import os
from pathlib import Path
import subprocess

repository = os.environ["GITHUB_REPOSITORY"]
source = os.environ.get("SOURCE_RUN_ID", "")
if not source:
    listing = json.loads(subprocess.check_output([
        "gh", "api", f"repos/{repository}/actions/workflows/maintenance.yml/runs?branch=main&status=completed&per_page=20"
    ]))
    source = next((str(run["id"]) for run in listing["workflow_runs"] if run["event"] in ("schedule", "workflow_dispatch")), "")
if not source.isdecimal():
    raise SystemExit("No completed main-branch maintenance run is available; dispatch maintenance.yml first")
run = json.loads(subprocess.check_output(["gh", "api", f"repos/{repository}/actions/runs/{source}"]))
if (run["head_branch"] != "main" or run["event"] not in ("schedule", "workflow_dispatch")
        or run["path"] != ".github/workflows/maintenance.yml"
        or run["head_repository"]["full_name"].lower() != repository.lower()):
    raise SystemExit("Refusing artifacts from an untrusted workflow, branch, event, or repository")
if run["status"] != "completed":
    raise SystemExit("Maintenance evidence is still being collected")
Path("reports").mkdir(exist_ok=True)
subprocess.run(["gh", "run", "download", source, "--repo", repository,
                "--name", "maintenance-evidence", "--dir", "reports"], check=True)
for arch in ("amd64", "arm64"):
    result = subprocess.run(["gh", "run", "download", source, "--repo", repository,
                             "--name", f"maintenance-security-{arch}", "--dir", f"reports/security-{arch}"])
    if result.returncode:
        Path(f"reports/missing-security-{arch}.txt").write_text("Security artifact unavailable; coverage incomplete\n")
Path("reports/maintenance-run.json").write_text(json.dumps({
    "id": run["id"], "url": run["html_url"], "revision": run["head_sha"], "conclusion": run["conclusion"]
}, indent=2) + "\n")
