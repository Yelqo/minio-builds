#!/usr/bin/env python3
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from monitor import actionable, advisory_changes, gate, scan_report, scanner_findings


def report(matches):
    return {"descriptor": {"db": {"status": {"built": datetime.now(timezone.utc).isoformat(), "valid": True}}}, "matches": matches}


def match(severity="High", state="fixed"):
    return {"artifact": {"name": "example", "version": "1"}, "vulnerability": {
        "id": "CVE-EXAMPLE", "severity": severity, "fix": {"state": state, "versions": ["2"]}, "dataSource": "https://example.org/advisory"}}


class MonitoringPolicy(unittest.TestCase):
    def test_new_and_revised_advisories_require_review(self):
        current = [{"ghsa_id": "known", "updated_at": "new", "html_url": "https://example.org/known"},
                   {"ghsa_id": "new", "updated_at": "today", "html_url": "https://example.org/new"}]
        self.assertEqual([item["id"] for item in advisory_changes(current, {"known": "old"})], ["known", "new"])
        self.assertEqual(advisory_changes(current, {"known": "new", "new": "today"}), [])

    def test_unfixed_findings_remain_visible_without_claiming_a_fix(self):
        findings = scanner_findings(report([match(state="not-fixed"), match(severity="Medium")]))
        self.assertEqual(len(findings), 2)  # preserve differing severity/fix assessments
        self.assertEqual(actionable(scanner_findings(report([match(state="not-fixed")]))), [])
        self.assertEqual(len(actionable(scanner_findings(report([match()])))), 1)

    def test_duplicate_binary_matches_do_not_duplicate_operator_work(self):
        self.assertEqual(len(scanner_findings(report([match(), match()]))), 1)

    def test_missing_or_invalid_scanner_database_is_not_a_clean_scan(self):
        for value in ({"matches": []}, {"descriptor": {"db": {"status": {"valid": False, "built": "2026-01-01T00:00:00Z"}}}, "matches": []}):
            with self.assertRaises(ValueError):
                scanner_findings(value)

    def test_stale_database_is_rejected(self):
        value = report([])
        value["descriptor"]["db"]["status"]["built"] = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
        with self.assertRaises(ValueError):
            scanner_findings(value)

    def test_actionable_scan_writes_evidence_before_failing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "scan.json").write_text(json.dumps(report([match()])))
            self.assertTrue(scan_report(root / "scan.json", root))
            self.assertIn("Fixable High/Critical findings: **1**", (root / "scan-summary.md").read_text())
            self.assertEqual(len(json.loads((root / "findings.json").read_text())["findings"]), 1)

    def test_incomplete_primary_sources_and_new_advisories_fail_the_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "evidence.json"
            for value, expected in [
                ({"errors": [{"required": True}], "changes": []}, True),
                ({"errors": [{"required": False}], "changes": []}, False),
                ({"errors": [], "changes": [{"kind": "advisory-needs-review"}]}, True),
                ({"errors": [], "changes": [{"kind": "base-image-update"}]}, True),
                ({"errors": [], "changes": [{"kind": "official-image-candidate"}]}, True),
                ({"errors": [], "changes": []}, False),
            ]:
                path.write_text(json.dumps(value))
                self.assertEqual(gate(path), expected)


if __name__ == "__main__":
    unittest.main()
