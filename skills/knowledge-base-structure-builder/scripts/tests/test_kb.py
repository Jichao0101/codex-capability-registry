from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "kb.py"


class KnowledgeBaseCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for directory in ("01_Knowledge", "02_Projects/Demo/fixes", "03_Inbox", "04_Sources", "90_Archive"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        entries = {
            "README.md": "# Vault\n",
            "01_Knowledge/知识总览.md": "# Knowledge\n",
            "02_Projects/项目总览.md": "# Projects\n",
            "03_Inbox/候选内容索引.md": "# Inbox\n",
            "04_Sources/来源索引.md": "# Sources\n",
        }
        for rel, body in entries.items():
            (self.root / rel).write_text(body, encoding="utf-8")
        (self.root / "AGENTS.md").write_text("# Policy\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_metadata_applies_guarded_knowledge_default(self) -> None:
        path = self.root / "01_Knowledge/item.md"
        path.write_text("---\nstatus: active\nupdated_at: 2026-06-22\nsources:\n  - internal\n---\n# Item\n", encoding="utf-8")
        output = self.root / "metadata.json"
        result = self.run_cli("metadata", "--root", str(self.root), "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        doc = next(item for item in json.loads(output.read_text())["documents"] if item["path"] == "01_Knowledge/item.md")
        self.assertEqual(doc["effective"]["protection_level"], "guarded")
        self.assertEqual(doc["effective"]["evidence_refs"], ["internal"])
        self.assertEqual(doc["value_origin"]["evidence_refs"], "legacy_alias:sources")

    def test_legacy_status_and_folder_links_do_not_raise_enum_or_link_errors(self) -> None:
        path = self.root / "02_Projects/legacy.md"
        path.write_text("---\nstatus: pending_review\n---\n# Legacy\n[[03_Inbox]]\n", encoding="utf-8")
        output = self.root / "lint.json"
        self.run_cli("lint", "--root", str(self.root), "--output", str(output))
        report = json.loads(output.read_text())
        relevant = [item for item in report["findings"] if item["path"] == "02_Projects/legacy.md"]
        self.assertFalse(any(item["rule_id"] in {"KB-LINT-002", "KB-LINT-004"} for item in relevant))

    def test_lint_reports_broken_link(self) -> None:
        (self.root / "03_Inbox/note.md").write_text("# Note\n[[missing]]\n", encoding="utf-8")
        output = self.root / "lint.json"
        result = self.run_cli("lint", "--root", str(self.root), "--output", str(output))
        self.assertEqual(result.returncode, 1)
        report = json.loads(output.read_text())
        self.assertTrue(any(item["rule_id"] == "KB-LINT-002" for item in report["findings"]))

    def test_preflight_verified_target_requires_review_and_reads_strong_fix(self) -> None:
        target = self.root / "01_Knowledge/item.md"
        target.write_text("---\nstatus: verified\nprotection_level: guarded\nchange_policy: free_update\n---\n# Driver binding\n", encoding="utf-8")
        fix = self.root / "02_Projects/Demo/fixes/driver-binding-fix.md"
        fix.write_text("# Driver binding fix\nKeep driver binding constraint.\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "01_Knowledge/item.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--query", "driver binding",
            "--output", str(report),
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "manual_review")
        self.assertTrue(any(item["path"].endswith("driver-binding-fix.md") for item in data["source_documents_read"]))
        check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_append_only_modify_is_blocked(self) -> None:
        target = self.root / "04_Sources/source.md"
        target.write_text("# Source\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "04_Sources/source.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--output", str(report),
        )
        self.assertEqual(result.returncode, 3)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "blocked")
        self.assertTrue(data["change_policy_checks"]["append_only_violations"])

    def test_explicit_stale_trace_index_fails_closed(self) -> None:
        target = self.root / "03_Inbox/note.md"
        target.write_text("# Note\n", encoding="utf-8")
        index = self.root / "trace.json"
        built = self.run_cli("trace-index", "--root", str(self.root), "--output", str(index))
        self.assertEqual(built.returncode, 0, built.stderr)
        target.write_text("# Note changed\n", encoding="utf-8")
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "03_Inbox/note.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--trace-index", str(index),
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("stale or invalid", result.stderr)

    def test_policy_forbidden_path_is_blocked(self) -> None:
        target = self.root / "03_Inbox/note.md"
        target.write_text("# Note\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "03_Inbox/note.md",
            "--intent", "modify", "--authorized-path", str(self.root),
            "--forbidden-path", str(self.root / "03_Inbox"), "--output", str(report),
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(report.read_text())["gate_decision"], "blocked")

    def test_hash_check_detects_policy_change(self) -> None:
        target = self.root / "03_Inbox/note.md"
        target.write_text("# Note\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "03_Inbox/note.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        (self.root / "AGENTS.md").write_text("# Changed policy\n", encoding="utf-8")
        check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
        self.assertEqual(check.returncode, 4)
        self.assertIn("AGENTS.md", check.stdout)

    def test_replacing_conclusion_without_reciprocal_supersession_is_blocked(self) -> None:
        target = self.root / "01_Knowledge/item.md"
        target.write_text("# Item\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "01_Knowledge/item.md",
            "--intent", "modify", "--replaces-conclusion", "--authorized-path", str(self.root),
            "--supersedes", "old.md", "--supersession-reason", "new evidence",
            "--evidence-ref", "validation.md", "--output", str(report),
        )
        self.assertEqual(result.returncode, 3)
        data = json.loads(report.read_text())
        self.assertTrue(any(item["rule_id"] == "KB-GATE-007" for item in data["triggered_rules"]))

    def test_create_in_authorized_nested_directory_can_be_allowed(self) -> None:
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root),
            "--target", "02_Projects/Demo/Current Maintenance Records/new.md",
            "--intent", "create", "--authorized-path", str(self.root), "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(report.read_text())["gate_decision"], "allow")


if __name__ == "__main__":
    unittest.main()
