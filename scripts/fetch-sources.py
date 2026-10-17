#!/usr/bin/env python3
"""Fetch only recorded source archives; a release's assets work as an offline cache."""
import hashlib
import json
from pathlib import Path
import re
import shlex
import urllib.request

root = Path(__file__).resolve().parent.parent
inputs = json.loads((root / "inputs.json").read_text())
build = root / ".build"
build.mkdir(exist_ok=True)
environment = []
for component, name in (("server", "minio"), ("client", "mc")):
    source = inputs[component]
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise ValueError("Source revision must be a full commit ID")
    archive = build / f"{name}.tar.gz"
    if not archive.exists():
        url = f'https://codeload.github.com/{source["repository"]}/tar.gz/{source["commit"]}'
        temporary = archive.with_suffix(".download")
        with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.rename(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != source["sha256"]:
        raise ValueError(f"SHA-256 mismatch: {archive}")
    for key in ("release", "version", "commit"):
        environment.append(f"{name.upper()}_{key.upper()}={shlex.quote(source[key])}")
    environment.append(f"{name.upper()}_SHA256={source['sha256']}")
(build / "inputs.env").write_text("\n".join(environment) + "\n")
print("Both source archive checksums verified")
