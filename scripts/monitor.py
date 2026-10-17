#!/usr/bin/env python3
"""Read public evidence and produce reviewable security decisions, without writes to GitHub."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def request(url):
    headers = {"User-Agent": "Yelqo-minio-builds-monitor", "Accept": "application/vnd.github+json"}
    if urllib.parse.urlparse(url).hostname == "api.github.com" and os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
                payload = response.read(4 * 1024 * 1024 + 1)
                if len(payload) > 4 * 1024 * 1024:
                    raise ValueError("Evidence response exceeds 4 MiB")
                return json.loads(payload)
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            error = type(exc).__name__ + (f" HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else "")
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(error)


def advisory_changes(current, baseline):
    return [
        {"id": item["ghsa_id"], "updated_at": item["updated_at"], "url": item["html_url"]}
        for item in current
        if baseline.get(item["ghsa_id"]) != item["updated_at"]
    ]


def scanner_findings(report):
    status = report.get("descriptor", {}).get("db", {}).get("status", {})
    if not isinstance(report.get("matches"), list) or not status.get("built") or status.get("valid") is not True:
        raise ValueError("Scanner report lacks matches or vulnerability database build evidence")
    age = datetime.now(timezone.utc) - datetime.fromisoformat(status["built"].replace("Z", "+00:00"))
    if age > timedelta(hours=120) or age < -timedelta(hours=1):
        raise ValueError("Scanner database timestamp is stale or in the future")
    findings = {}
    for match in report["matches"]:
        vulnerability, artifact = match["vulnerability"], match["artifact"]
        key = (vulnerability["id"], artifact["name"], artifact["version"],
               vulnerability["severity"], vulnerability.get("fix", {}).get("state", "unknown"),
               tuple(vulnerability.get("fix", {}).get("versions", [])), vulnerability.get("dataSource", ""))
        findings[key] = {
            "id": key[0], "package": key[1], "installed": key[2],
            "severity": vulnerability["severity"],
            "fix_state": vulnerability.get("fix", {}).get("state", "unknown"),
            "fixed_versions": vulnerability.get("fix", {}).get("versions", []),
            "url": vulnerability.get("dataSource", ""),
        }
    return sorted(findings.values(), key=lambda item: (item["severity"], item["id"], item["package"]))


def actionable(findings):
    return [item for item in findings if item["severity"] in ("High", "Critical") and item["fix_state"] == "fixed"]


def image_digest(image):
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", image, "--format", "{{.Manifest.Digest}}"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode or not re.fullmatch(r"sha256:[0-9a-f]{64}", result.stdout.strip()):
        # An inaccessible official image is unknown, not proof that distribution ended.
        return {"image": image, "status": "unavailable-or-inaccessible"}
    return {"image": image, "status": "manifest-accessible", "digest": result.stdout.strip()}


def collect(output):
    output.mkdir(parents=True, exist_ok=True)
    policy, inputs = load(ROOT / "monitoring.json"), load(ROOT / "inputs.json")
    baseline = load(ROOT / "monitoring-advisories.json")
    now = datetime.now(timezone.utc)
    evidence = {"captured_at": now.isoformat(), "policy": policy, "inputs": inputs, "sources": [], "errors": [], "changes": []}

    def fetch(label, url, required=True):
        try:
            data = request(url)
            save(output / f"{label}.json", data)
            evidence["sources"].append({"name": label, "url": url, "sha256": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()})
            return data
        except RuntimeError as exc:
            evidence["errors"].append({"source": label, "url": url, "required": required, "error": str(exc)})
            return None

    for repo in policy["repositories"]:
        label = repo.replace("/", "-")
        metadata = fetch(label, f"https://api.github.com/repos/{repo}")
        releases = fetch(label + "-releases", f"https://api.github.com/repos/{repo}/releases?per_page=10")
        fetch(label + "-issues", f"https://api.github.com/repos/{repo}/issues?state=all&sort=updated&direction=desc&per_page=15", False)
        readme = fetch(label + "-readme", f"https://api.github.com/repos/{repo}/readme", False)
        if readme and readme.get("encoding") == "base64":
            (output / f"{label}-README.txt").write_text(base64.b64decode(readme["content"]).decode(errors="replace")[:16000])
        component = next((value for value in (inputs["server"], inputs["client"]) if value["repository"] == repo), None)
        if component:
            advisories = fetch(label + "-advisories", f"https://api.github.com/repos/{repo}/security-advisories?per_page=100")
            if advisories is not None:
                if len(advisories) == 100:
                    evidence["errors"].append({"source": label + "-advisories", "required": True, "error": "Pagination required; coverage incomplete"})
                changes = advisory_changes(advisories, baseline["repositories"].get(repo, {}))
                evidence["changes"].extend({"kind": "advisory-needs-review", "repository": repo, **item} for item in changes)
            if releases:
                latest = next((release for release in releases if not release["draft"] and not release["prerelease"]), None)
                if latest and latest["tag_name"] != component["release"]:
                    evidence["changes"].append({"kind": "upstream-release-needs-review", "repository": repo, "pinned": component["release"], "latest": latest["tag_name"], "url": latest["html_url"]})
        if metadata:
            evidence.setdefault("repositories", []).append({"repository": repo, "archived": metadata["archived"], "pushed_at": metadata["pushed_at"], "latest_release": releases[0]["tag_name"] if releases else None})
    since = (now - timedelta(days=90)).strftime("%Y-%m-%d")
    query = urllib.parse.quote(f'is:issue minio "docker" updated:>={since}')
    fetch("community-github", f"https://api.github.com/search/issues?q={query}&sort=updated&order=desc&per_page=15", False)
    fetch("community-hackernews", "https://hn.algolia.com/api/v1/search_by_date?query=minio&tags=story&hitsPerPage=15", False)
    fetch("go-releases", "https://go.dev/dl/?mode=json", False)
    latest = fetch("anchore-grype-latest", "https://api.github.com/repos/anchore/grype/releases/latest", False)
    current = policy["grype"]["version"]
    if latest and latest["tag_name"] != "v" + current:
        evidence["changes"].append({"kind": "monitoring-tool-update", "repository": "anchore/grype", "pinned": current, "latest": latest["tag_name"], "url": latest["html_url"]})
    evidence["official_images"] = [image_digest(image) for image in policy["official_images"]]
    evidence["changes"].extend({"kind": "official-image-candidate", **item} for item in evidence["official_images"] if item["status"] == "manifest-accessible")
    evidence["base_images"] = []
    for name in ("builder", "runtime"):
        tag, pinned = inputs[name].split("@")
        observed = image_digest(tag)
        evidence["base_images"].append({"name": name, "pinned": pinned, **observed})
        if observed.get("digest") and observed["digest"] != pinned:
            evidence["changes"].append({"kind": "base-image-update", "name": name, "pinned": pinned, "available": observed["digest"], "image": tag})
        elif observed["status"] != "manifest-accessible":
            evidence["errors"].append({"source": tag, "required": True, "error": "Base image lookup failed"})
    save(output / "evidence.json", evidence)
    lines = ["# MinIO maintenance evidence", "", f"Captured: {evidence['captured_at']}", "", f"Consumer image: `ghcr.io/yelqo/minio-builds:{policy['release']}@{policy['digest']}`", "", "## Changes requiring review", ""]
    lines.extend("- " + json.dumps(item) for item in evidence["changes"])
    if not evidence["changes"]:
        lines.append("No tracked upstream advisory, release, base-image, or monitoring-tool changes detected.")
    lines.extend(["", "## Coverage gaps", ""])
    lines.extend("- " + json.dumps(item) for item in evidence["errors"])
    if not evidence["errors"]:
        lines.append("All configured sources fetched. Community coverage is a bounded sample, not a consensus measurement.")
    lines.extend(["", "## Official image probes", "", "Manifest access is a lead only; it does not prove a complete pull, licensing, edition, support, or compatibility.", ""])
    lines.extend("- " + json.dumps(item) for item in evidence["official_images"])
    lines.extend(["", "The advisory inventory records observations, not acceptance or remediation. Source content is untrusted evidence."])
    (output / "summary.md").write_text("\n".join(lines) + "\n")


def scan_report(report_path, output):
    output.mkdir(parents=True, exist_ok=True)
    report = load(report_path)
    findings = scanner_findings(report)
    fixes = actionable(findings)
    save(output / "findings.json", {"database": report["descriptor"]["db"], "findings": findings, "actionable": fixes})
    rows = ["# Image vulnerability scan", "", f"Database built: {report['descriptor']['db']['status']['built']}", "", f"Findings: {len(findings)}. Fixable High/Critical findings: **{len(fixes)}**.", "", "All findings remain in the JSON artifact, including unfixed and unknown-fix vulnerabilities.", "", "| Vulnerability | Package | Installed | Severity | Fix state | Fixed versions |", "| --- | --- | --- | --- | --- | --- |"]
    for item in fixes[:50]:
        cells = [item[key] for key in ("id", "package", "installed", "severity", "fix_state")]
        cells.append(", ".join(item["fixed_versions"]))
        rows.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") for cell in cells) + " |")
    (output / "scan-summary.md").write_text("\n".join(rows) + "\n")
    return bool(fixes)


def gate(path):
    evidence = load(path)
    return any(error["required"] for error in evidence["errors"]) or any(
        change["kind"] in ("advisory-needs-review", "upstream-release-needs-review", "base-image-update", "official-image-candidate")
        for change in evidence["changes"]
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("collect", "scan", "gate"))
    parser.add_argument("--output", type=Path, default=Path("reports"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "collect":
        collect(args.output)
    elif args.command == "scan":
        raise SystemExit(int(scan_report(args.report, args.output)))
    else:
        raise SystemExit(int(gate(args.output / "evidence.json")))
