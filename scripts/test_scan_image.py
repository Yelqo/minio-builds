#!/usr/bin/env python3
"""Exercise the scanner entry point without a registry or scanner download."""
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
DIGEST = "sha256:" + "a" * 64


class ScanImage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "scripts").symlink_to(ROOT / "scripts", target_is_directory=True)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.fixture = {"descriptor": {"db": {"status": {
            "valid": True, "built": datetime.now(timezone.utc).isoformat(),
        }}}, "matches": []}
        scanner = b'''#!/usr/bin/env python3
import json, os, pathlib, sys
pathlib.Path('invocation.json').write_text(json.dumps({'args': sys.argv[1:],
    'fresh_db': os.environ['GRYPE_DB_AUTO_UPDATE'],
    'validate_age': os.environ['GRYPE_DB_VALIDATE_AGE'],
    'max_age': os.environ['GRYPE_DB_MAX_ALLOWED_BUILT_AGE']}))
print(pathlib.Path('fixture.json').read_text())
sys.exit(int(os.environ.get('SCANNER_EXIT', '0')))
'''
        self.archive = self.root / "scanner.tar.gz"
        with tarfile.open(self.archive, "w:gz") as archive:
            member = tarfile.TarInfo("grype")
            member.mode = 0o755
            member.size = len(scanner)
            archive.addfile(member, io.BytesIO(scanner))
        checksum = hashlib.sha256(self.archive.read_bytes()).hexdigest()
        self.policy = {"digest": DIGEST, "grype": {"version": "test",
                       "linux_amd64_sha256": checksum, "linux_arm64_sha256": checksum}}
        self.executable("uname", '#!/bin/sh\nprintf "%s\\n" "$SCANNER_HOST"\n')
        self.executable("curl", '''#!/usr/bin/env python3
import os, pathlib, shutil, sys
pathlib.Path('download-url.txt').write_text(sys.argv[sys.argv.index('--output') - 1])
shutil.copyfile(os.environ['SCANNER_ARCHIVE'], sys.argv[sys.argv.index('--output') + 1])
''')
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        SCANNER_HOST="x86_64", SCANNER_ARCHIVE=str(self.archive))

    def executable(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def scan(self, *args):
        (self.root / "fixture.json").write_text(json.dumps(self.fixture))
        (self.root / "monitoring.json").write_text(json.dumps(self.policy))
        return subprocess.run(["bash", str(ROOT / "scripts/scan-image.sh"), *args],
                              cwd=self.root, env=self.env, capture_output=True, text=True)

    def read(self, path):
        return json.loads((self.root / path).read_text())

    def test_maintenance_scans_consumed_digest_on_requested_platform(self):
        result = self.scan("linux/arm64")
        self.assertEqual(result.returncode, 0, result.stderr)
        invocation = self.read("invocation.json")
        self.assertEqual(invocation["args"], [f"registry:ghcr.io/yelqo/minio-builds@{DIGEST}",
                                            "--platform", "linux/arm64", "-o", "json"])
        self.assertEqual((invocation["fresh_db"], invocation["validate_age"], invocation["max_age"]),
                         ("true", "true", "120h"))
        self.assertEqual(self.read("reports/scan-target.json")["platform"], "linux/arm64")
        self.assertTrue((self.root / "reports/findings.json").exists())

    def test_arm64_host_scans_local_candidate_with_arm64_scanner(self):
        self.env["SCANNER_HOST"] = "aarch64"
        result = self.scan("linux/arm64", "docker:minio-builds:validation")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("linux_arm64.tar.gz", (self.root / "download-url.txt").read_text())
        self.assertEqual(self.read("invocation.json")["args"][0], "docker:minio-builds:validation")

    def test_release_scans_explicit_digest_instead_of_consumed_digest(self):
        source = "registry:ghcr.io/yelqo/minio-builds@sha256:" + "b" * 64
        result = self.scan("linux/amd64", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read("reports/scan-target.json")["source"], source)
        self.assertEqual(self.read("invocation.json")["args"][0], source)

    def test_fixable_critical_findings_fail_and_retain_evidence(self):
        self.fixture["matches"] = [{"artifact": {"name": "dependency", "version": "1"},
                                    "vulnerability": {"id": "CVE-EXAMPLE", "severity": "Critical",
                                    "fix": {"state": "fixed", "versions": ["2"]}}}]
        result = self.scan("linux/amd64")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.read("reports/findings.json")["actionable"]), 1)
        self.assertTrue((self.root / "reports/grype.json").exists())

    def test_bad_checksum_prevents_scanner_execution(self):
        self.policy["grype"]["linux_amd64_sha256"] = "0" * 64
        self.assertNotEqual(self.scan("linux/amd64").returncode, 0)
        self.assertFalse((self.root / "invocation.json").exists())

    def test_scan_failure_is_not_a_clean_scan(self):
        self.env["SCANNER_EXIT"] = "2"
        self.assertNotEqual(self.scan("linux/amd64").returncode, 0)
        self.assertTrue((self.root / "reports/grype.json").exists())
        self.assertFalse((self.root / "reports/findings.json").exists())

    def test_stale_database_blocks_qualification(self):
        self.fixture["descriptor"]["db"]["status"]["built"] = (
            datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
        self.assertNotEqual(self.scan("linux/amd64").returncode, 0)
        self.assertFalse((self.root / "reports/findings.json").exists())

    def test_invalid_platform_or_moving_registry_tag_is_rejected(self):
        for args in (("linux/386",), ("linux/amd64", "registry:ghcr.io/yelqo/minio-builds:latest")):
            with self.subTest(args=args):
                self.assertNotEqual(self.scan(*args).returncode, 0)
        self.assertFalse((self.root / "invocation.json").exists())


if __name__ == "__main__":
    unittest.main()
