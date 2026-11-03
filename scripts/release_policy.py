#!/usr/bin/env python3
"""Require monotonically increasing distribution versions before publication."""
import json
from pathlib import Path
import re
import sys


def version_tuple(version):
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError(f"Expected vMAJOR.MINOR.PATCH, got {version!r}")
    return tuple(int(part) for part in version[1:].split("."))


def require_new_release(version, releases):
    candidate = version_tuple(version)
    for release in releases:
        if release["draft"] or release["prerelease"]:
            continue
        published = version_tuple(release["tag_name"])
        if candidate <= published:
            raise ValueError(f"{version} must be newer than published {release['tag_name']}")


if __name__ == "__main__":
    version, path = sys.argv[1:]
    releases = [json.loads(line) for line in Path(path).read_text().splitlines()]
    require_new_release(version, releases)
    print(f"{version} is a new distribution release")
