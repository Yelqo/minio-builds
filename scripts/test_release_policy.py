#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from release_policy import require_new_release, version_tuple


def published(tag, **flags):
    return {"tag_name": tag, "draft": False, "prerelease": False, **flags}


class ReleasePolicy(unittest.TestCase):
    def test_cli_checks_every_release_from_paginated_json_lines(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'releases.jsonl'
            path.write_text('\n'.join(json.dumps(published(tag)) for tag in ('v0.1.0', 'v0.1.9')))
            script = Path(__file__).with_name('release_policy.py')
            for version, expected in (('v0.1.1', False), ('v0.1.10', True)):
                result = subprocess.run(['python3', str(script), version, str(path)], capture_output=True)
                self.assertEqual(result.returncode == 0, expected)

    def test_first_release_and_newer_versions_are_allowed(self):
        require_new_release("v0.1.0", [])
        require_new_release("v0.1.10", [published("v0.1.9")])
        require_new_release("v0.2.0", [published("v0.1.10")])

    def test_existing_and_older_versions_cannot_be_promoted_as_latest(self):
        for candidate in ("v0.1.0", "v0.1.1", "v0.1.9"):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                require_new_release(candidate, [published("v0.1.0"), published("v0.1.9")])

    def test_drafts_and_prereleases_do_not_displace_qualified_releases(self):
        require_new_release("v0.1.1", [published("v0.1.0"),
                            published("v0.2.0", draft=True),
                            published("v1.0.0-rc.1", prerelease=True)])

    def test_invalid_versions_are_rejected(self):
        for version in ("latest", "0.1.1", "v0.01.1", "v0.1.1-rc.1", "v0.1.1\n"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                version_tuple(version)


if __name__ == "__main__":
    unittest.main()
