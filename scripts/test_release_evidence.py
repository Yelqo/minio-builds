#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class ReleaseEvidence(unittest.TestCase):
    def test_release_records_exact_inputs_platforms_and_scanner(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / "dist"
            dist.mkdir()
            for name in ("inputs.json", "monitoring.json"):
                (root / name).write_text((ROOT / name).read_text())
            entries = [{"digest": "sha256:" + digit * 64,
                        "platform": {"os": "linux", "architecture": arch}}
                       for arch, digit in (("amd64", "a"), ("arm64", "b"))]
            (dist / "manifest.json").write_text(json.dumps({"manifests": entries}))
            digest = "sha256:" + "c" * 64
            env = dict(os.environ, GITHUB_REPOSITORY="Yelqo/minio-builds",
                       GITHUB_SHA="d" * 40, GITHUB_RUN_ID="123")
            subprocess.run(["python3", str(ROOT / "scripts/release-evidence.py"), "v0.1.1", digest],
                           cwd=root, env=env, check=True, capture_output=True, text=True)
            evidence = json.loads((dist / "release.json").read_text())
            self.assertEqual(evidence["digest"], digest)
            self.assertEqual(evidence["build_revision"], env["GITHUB_SHA"])
            self.assertEqual(evidence["platform_manifests"],
                             {item["platform"]["architecture"]: item["digest"] for item in entries})
            self.assertEqual(evidence["inputs"], json.loads((root / "inputs.json").read_text()))
            self.assertEqual(evidence["security_scanner"],
                             json.loads((root / "monitoring.json").read_text())["grype"])
            notes = (dist / "release-notes.md").read_text()
            self.assertIn(evidence["image"], notes)
            for component in ("server", "client"):
                self.assertIn(evidence["inputs"][component]["commit"], notes)
            self.assertIn("Fixable High/Critical scanner findings block promotion", notes)


if __name__ == "__main__":
    unittest.main()
