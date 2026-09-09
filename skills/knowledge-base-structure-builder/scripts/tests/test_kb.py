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

    def test_metadata_respects_authorized_paths(self) -> None:
        (self.root / "01_Knowledge/item.md").write_text("# Knowledge Item\n", encoding="utf-8")
        (self.root / "02_Projects/Demo/project.md").write_text("# Project Item\n", encoding="utf-8")
        output = self.root / "metadata.json"
        result = self.run_cli(
            "metadata", "--root", str(self.root), "--authorized-path", str(self.root / "02_Projects"), "--output", str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        paths = {item["path"] for item in json.loads(output.read_text())["documents"]}
        self.assertIn("02_Projects/Demo/project.md", paths)
        self.assertNotIn("01_Knowledge/item.md", paths)

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

    def test_lint_keeps_latest_three_default_reports(self) -> None:
        report_dir = self.root / "reports/kb/lint"
        report_dir.mkdir(parents=True)
        stale_reports = []
        for index in range(4):
            stale = report_dir / f"lint-20000101T00000000000{index}.json"
            stale.write_text("{}\n", encoding="utf-8")
            stale_reports.append(stale)
        result = self.run_cli("lint", "--root", str(self.root))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        remaining = sorted(report_dir.glob("lint-*.json"))
        self.assertEqual(len(remaining), 3)
        self.assertFalse(stale_reports[0].exists())
        self.assertTrue(Path(payload["output"]).is_file())
        self.assertIn(str(stale_reports[0]), payload["pruned_reports"])

    def test_preflight_unassessed_fix_candidate_requires_review_and_reads_source(self) -> None:
        target = self.root / "01_Knowledge/item.md"
        target.write_text("---\nstatus: verified\nprotection_level: guarded\nchange_policy: free_update\n---\n# Driver binding\n", encoding="utf-8")
        fix = self.root / "02_Projects/Demo/fixes/driver-binding-fix.md"
        fix.write_text("# Driver binding fix\nKeep driver binding constraint.\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "01_Knowledge/item.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--query", "driver binding",
            "--output", str(report), "--strict-exit-code",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "manual_review")
        self.assertTrue(any(item["condition"] == "semantic_review_needed" for item in data["triggered_rules"]))
        self.assertTrue(any(item["path"].endswith("driver-binding-fix.md") for item in data["source_documents_read"]))
        check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_preflight_manual_review_defaults_to_zero_exit_for_agent_loops(self) -> None:
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
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(report.read_text())["gate_decision"], "manual_review")

    def test_preflight_guarded_verified_target_without_conflict_can_be_allowed(self) -> None:
        target = self.root / "01_Knowledge/item.md"
        target.write_text("---\nstatus: verified\nprotection_level: guarded\nchange_policy: free_update\n---\n# Item\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "01_Knowledge/item.md",
            "--intent", "modify", "--authorized-path", str(self.root),
            "--query", "term-that-does-not-match", "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "allow")
        self.assertFalse(any(item["condition"] in {"semantic_review_needed", "high_risk_retrieval_insufficient"} for item in data["triggered_rules"]))

    def test_preflight_requires_explicit_authorized_path(self) -> None:
        target = self.root / "03_Inbox/note.md"
        target.write_text("# Note\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli("preflight", "--root", str(self.root), "--target", "03_Inbox/note.md", "--intent", "modify", "--output", str(report), "--strict-exit-code")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(report.read_text())["gate_decision"], "blocked")

    def test_append_only_modify_is_blocked(self) -> None:
        target = self.root / "04_Sources/source.md"
        target.write_text("# Source\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "04_Sources/source.md",
            "--intent", "modify", "--authorized-path", str(self.root), "--output", str(report), "--strict-exit-code",
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
            "--forbidden-path", str(self.root / "03_Inbox"), "--output", str(report), "--strict-exit-code",
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

    def test_hash_check_ignores_unauthorized_scope_changes(self) -> None:
        target = self.root / "02_Projects/Demo/note.md"
        target.write_text("# Note\n", encoding="utf-8")
        outside = self.root / "01_Knowledge/outside.md"
        outside.write_text("# Outside\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "02_Projects/Demo/note.md",
            "--intent", "modify", "--authorized-path", str(self.root / "02_Projects"), "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        outside.write_text("# Outside changed\n", encoding="utf-8")
        check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_replacing_conclusion_without_reciprocal_supersession_is_blocked(self) -> None:
        target = self.root / "01_Knowledge/item.md"
        target.write_text("# Item\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "01_Knowledge/item.md",
            "--intent", "modify", "--replaces-conclusion", "--authorized-path", str(self.root),
            "--supersedes", "old.md", "--supersession-reason", "new evidence",
            "--evidence-ref", "validation.md", "--output", str(report), "--strict-exit-code",
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

    def test_minimal_apply_check_allows_retrieval_summary_append_without_trace_index(self) -> None:
        fix = self.root / "02_Projects/Demo/Current Maintenance Records/binding-fix.md"
        fix.parent.mkdir(parents=True, exist_ok=True)
        fix.write_text("---\nstatus: verified\n---\n# Binding fix\n\nBody text.\n", encoding="utf-8")
        report = self.root / "minimal.json"
        result = self.run_cli(
            "minimal-apply-check", "--root", str(self.root),
            "--target", "02_Projects/Demo/Current Maintenance Records/binding-fix.md",
            "--intent", "append", "--change-class", "retrieval_summary_append",
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "allow")
        self.assertFalse(data["checks"]["trace_index_used"])
        self.assertFalse((self.root / ".kb_cache/trace-index/index.json").exists())
        self.assertEqual(data["input"]["target_record_type"], "maintenance")
        self.assertTrue(data["minimal_apply_snapshot"]["target_hashes_before_apply"])

    def test_minimal_apply_check_allows_current_lightweight_append_without_target_type_confirmation(self) -> None:
        current = self.root / "02_Projects/Demo/overview_current.md"
        current.write_text("# Current\n", encoding="utf-8")
        report = self.root / "minimal.json"
        result = self.run_cli(
            "minimal-apply-check", "--root", str(self.root),
            "--target", "02_Projects/Demo/overview_current.md",
            "--intent", "append", "--change-class", "retrieval_summary_append",
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "allow")
        self.assertFalse(data["checks"]["full_preflight_required"])
        self.assertFalse(data["checks"]["user_confirmation_required"])
        self.assertEqual(data["checks"]["confirmation_reasons"], [])

    def test_minimal_apply_check_keeps_confirmation_fields_when_user_supplies_batch_id(self) -> None:
        current = self.root / "02_Projects/Demo/overview_current.md"
        current.write_text("# Current\n", encoding="utf-8")
        report = self.root / "minimal.json"
        result = self.run_cli(
            "minimal-apply-check", "--root", str(self.root),
            "--target", "02_Projects/Demo/overview_current.md",
            "--intent", "append", "--change-class", "retrieval_summary_append",
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--user-confirmed", "--batch-confirmation-id", "batch-20260624",
            "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "allow")
        self.assertFalse(data["checks"]["user_confirmation_required"])
        self.assertEqual(data["checks"]["batch_confirmation_id"], "batch-20260624")

    def test_structure_relocate_directory_scope_check_does_not_require_full_preflight(self) -> None:
        source_dir = self.root / "03_Inbox/J6"
        source_dir.mkdir(parents=True)
        (source_dir / "a.md").write_text("# A\n", encoding="utf-8")
        (source_dir / "b.md").write_text("# B\n", encoding="utf-8")
        report = self.root / "minimal.json"
        result = self.run_cli(
            "minimal-apply-check", "--root", str(self.root),
            "--target", "03_Inbox/J6",
            "--intent", "modify", "--change-class", "structure_relocate",
            "--authorized-path", str(self.root / "03_Inbox"),
            "--output", str(report),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "allow")
        self.assertFalse(data["checks"]["full_preflight_required"])
        self.assertFalse((self.root / ".kb_cache/trace-index/index.json").exists())
        self.assertEqual(set(data["minimal_apply_snapshot"]["target_files"]), {"03_Inbox/J6/a.md", "03_Inbox/J6/b.md"})

    def test_preflight_high_risk_without_retrieval_evidence_requires_manual_review(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n", encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "02_Projects/Demo/design.md",
            "--intent", "modify", "--change-class", "conclusion_replacement",
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--query", "term-that-does-not-match", "--output", str(report), "--strict-exit-code",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "manual_review")
        self.assertFalse(data["retrieval_coverage"]["matches_found"])
        self.assertFalse(data["retrieval_coverage"]["safety_proven_by_no_hits"])
        self.assertTrue(any(item["condition"] == "high_risk_retrieval_insufficient" for item in data["triggered_rules"]))

    def test_minimal_apply_check_requires_full_preflight_for_conclusion_replacement(self) -> None:
        note = self.root / "02_Projects/Demo/note.md"
        note.write_text("# Note\n", encoding="utf-8")
        report = self.root / "minimal.json"
        result = self.run_cli(
            "minimal-apply-check", "--root", str(self.root),
            "--target", "02_Projects/Demo/note.md",
            "--intent", "modify", "--change-class", "conclusion_replacement",
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--replaces-conclusion", "--output", str(report), "--strict-exit-code",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "requires_full_preflight")
        self.assertIn("change_class:conclusion_replacement", data["checks"]["full_preflight_reasons"])

    def test_lint_reports_missing_retrieval_summary_for_fix_docs(self) -> None:
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        fix.write_text(
            "# Binding fix\n\n症状：driver binding failed in `TrackManager::update`.\n",
            encoding="utf-8",
        )
        output = self.root / "lint.json"
        result = self.run_cli("lint", "--root", str(self.root), "--output", str(output))
        self.assertEqual(result.returncode, 0)
        report = json.loads(output.read_text())
        self.assertTrue(
            any(item["rule_id"] == "KB-LINT-009" and item["path"] == "02_Projects/Demo/fixes/binding-fix.md" for item in report["findings"])
        )

    def test_lint_reports_unsupported_retrieval_summary_anchor(self) -> None:
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        fix.write_text(
            "# Binding fix\n\n"
            "## Retrieval Summary\n\n"
            "- topic: driver binding\n"
            "- symbols: `MissingSymbol`\n\n"
            "正文只提到 `TrackManager::update`。\n",
            encoding="utf-8",
        )
        output = self.root / "lint.json"
        self.run_cli("lint", "--root", str(self.root), "--output", str(output))
        report = json.loads(output.read_text())
        self.assertTrue(
            any(item["rule_id"] == "KB-LINT-010" and "unsupported_anchors" in " ".join(item.get("issues", [])) for item in report["findings"])
        )

    def test_retrieval_summary_proposals_are_report_only(self) -> None:
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        original = "# Binding fix\n\n症状：driver binding failed in `TrackManager::update` at source/utils/track.cpp.\n"
        fix.write_text(original, encoding="utf-8")
        output = self.root / "summary-proposals.json"
        result = self.run_cli(
            "retrieval-summary-proposals", "--root", str(self.root),
            "--authorized-path", str(self.root / "02_Projects/Demo"),
            "--output", str(output),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(output.read_text())
        self.assertEqual(report["proposal_count"], 1)
        proposal = report["proposals"][0]
        self.assertEqual(proposal["target_path"], "02_Projects/Demo/fixes/binding-fix.md")
        self.assertTrue(proposal["proposal_only"])
        self.assertEqual(proposal["apply_check"]["recommended_command"], "minimal-apply-check")
        self.assertIn("no trace-index/preflight/hash-check", proposal["gate_reason"])
        self.assertIn("## Retrieval Summary", proposal["proposed_section"])
        self.assertEqual(fix.read_text(encoding="utf-8"), original)

    def test_retrieval_package_can_drive_preflight_source_read_and_conflict_review(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n", encoding="utf-8")
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        fix.write_text("# Binding fix\nKeep binding constraint.\n", encoding="utf-8")
        package = self.root / "retrieval_package.json"
        package.write_text(json.dumps({
            "authorized_paths": [str(self.root / "02_Projects")],
            "source_sections_read": [{"path": "02_Projects/Demo/fixes/binding-fix.md", "heading": "Binding fix"}],
            "candidate_fixes": [{"source_path": "02_Projects/Demo/fixes/binding-fix.md"}],
            "recall_limitations": [],
        }), encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "02_Projects/Demo/design.md",
            "--intent", "modify", "--authorized-path", str(self.root / "02_Projects"),
            "--retrieval-package", str(package), "--output", str(report), "--strict-exit-code",
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "manual_review")
        self.assertTrue(data["retrieval_package_check"]["valid"])
        self.assertTrue(any(item["path"] == "02_Projects/Demo/fixes/binding-fix.md" for item in data["source_documents_read"]))
        self.assertTrue(any(item["condition"] == "semantic_review_needed" for item in data["triggered_rules"]))

    def test_invalid_retrieval_package_blocks_preflight(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n", encoding="utf-8")
        package = self.root / "retrieval_package.json"
        package.write_text(json.dumps({
            "authorized_paths": [str(self.root / "01_Knowledge")],
            "source_sections_read": [],
            "recall_limitations": [],
        }), encoding="utf-8")
        report = self.root / "preflight.json"
        result = self.run_cli(
            "preflight", "--root", str(self.root), "--target", "02_Projects/Demo/design.md",
            "--intent", "modify", "--authorized-path", str(self.root / "02_Projects"),
            "--retrieval-package", str(package), "--output", str(report), "--strict-exit-code",
        )
        self.assertEqual(result.returncode, 3)
        data = json.loads(report.read_text())
        self.assertEqual(data["gate_decision"], "blocked")
        self.assertFalse(data["retrieval_package_check"]["valid"])

    def test_local_edit_checks_proposed_content_and_preserves_history(self) -> None:
        target = self.root / "02_Projects/Demo/note.md"
        draft = self.root / "draft.txt"
        report = self.root / "minimal.json"
        cases = [
            ("# N\nSpeling.\n", "# N\nSpelling.\n", "modify", "allow"),
            ("# N\nText.\n", "---\nstatus: verified\n---\n# N\nText.\n", "modify", "requires_full_preflight"),
            ("# N\n必须验证。\n", "# N\n可以跳过验证。\n", "modify", "requires_full_preflight"),
            ("---\nchange_policy: append_only\n---\n# N\nOld.\n", "# N\nNew.\n", "modify", "blocked"),
            ("# N\nOld.\n", "# N\nNew.\n", "append", "blocked"),
        ]
        for before, after, intent, expected in cases:
            with self.subTest(expected=expected, before=before):
                target.write_text(before)
                draft.write_text(after)
                result = self.run_cli("minimal-apply-check", "--root", str(self.root),
                    "--target", "02_Projects/Demo/note.md", "--intent", intent,
                    "--change-class", "editorial_edit", "--proposed-file", str(draft),
                    "--authorized-path", str(target.parent), "--output", str(report))
                self.assertEqual(result.returncode, 0, result.stderr)
                data = json.loads(report.read_text())
                self.assertEqual(data["gate_decision"], expected)
                self.assertTrue(data["checks"]["proposed_content_hash"])
                self.assertEqual(target.read_text(), before)
                self.assertFalse((self.root / ".kb_cache").exists())

    def test_local_modify_without_draft_escalates(self) -> None:
        target = self.root / "03_Inbox/note.md"
        target.write_text("# Note\n")
        report = self.root / "minimal.json"
        result = self.run_cli("minimal-apply-check", "--root", str(self.root),
            "--target", "03_Inbox/note.md", "--intent", "modify", "--change-class", "editorial_edit",
            "--authorized-path", str(target.parent), "--output", str(report), "--strict-exit-code")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(report.read_text())["gate_decision"], "requires_full_preflight")

    def test_direct_evidence_validates_originals_without_index(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n")
        source = self.root / "02_Projects/Demo/validation.md"
        source.write_text("# Validation\nObserved result: 12.\n")
        assessment = self.root / "assessment.json"
        report = self.root / "preflight.json"
        base = {"claims": [{"change": "Add measured result", "path": "02_Projects/Demo/validation.md",
                "quote": "Observed result: 12.", "reason": "The experiment measured this value"}],
                "constraints": [], "limitations": []}
        for variant, expected in [("valid", "allow"), ("quote", "blocked"), ("path", "blocked"), ("forbidden", "blocked"),
                                  ("gap", "manual_review"), ("conflict", "manual_review")]:
            with self.subTest(variant=variant):
                data = json.loads(json.dumps(base))
                if variant == "quote":
                    data["claims"][0]["quote"] = "Invented evidence"
                elif variant == "path":
                    data["claims"][0]["path"] = "01_Knowledge/private.md"
                elif variant == "gap":
                    data["limitations"] = ["Missing production validation"]
                elif variant == "conflict":
                    data["constraints"] = [{"path": "02_Projects/Demo/validation.md", "quote": "Observed result: 12.",
                        "disposition": "conflict", "reason": "The new claim contradicts this result"}]
                assessment.write_text(json.dumps(data))
                result = self.run_cli("preflight", "--root", str(self.root),
                    "--target", "02_Projects/Demo/design.md", "--intent", "modify", "--change-class", "semantic_fact_update",
                    "--authorized-path", str(target.parent), "--evidence-assessment", str(assessment), "--output", str(report),
                    *(["--forbidden-path", str(source)] if variant == "forbidden" else []))
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(report.read_text())
                self.assertEqual(output["gate_decision"], expected)
                self.assertFalse((self.root / ".kb_cache").exists())
                self.assertEqual(output["semantic_coverage"], "agent_assessed_not_machine_proven")
                if variant == "valid":
                    check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
                    self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
                    source.write_text("# Validation\nObserved result: 13.\n")
                    check = self.run_cli("hash-check", "--root", str(self.root), "--report", str(report))
                    self.assertEqual(check.returncode, 4, check.stdout + check.stderr)
                    source.write_text("# Validation\nObserved result: 12.\n")

    def test_trace_hit_is_candidate_not_proven_conflict(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n")
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        fix.write_text("# Binding fix\nKeep driver binding.\n")
        assessment = self.root / "assessment.json"
        assessment.write_text(json.dumps({
            "claims": [{"change": "Explain driver binding", "path": "02_Projects/Demo/fixes/binding-fix.md",
                "quote": "Keep driver binding.", "reason": "Explains the existing constraint"}],
            "constraints": [{"path": "02_Projects/Demo/fixes/binding-fix.md", "quote": "Keep driver binding.",
                "disposition": "preserved", "reason": "No change to binding behavior"}], "limitations": []}))
        report = self.root / "preflight.json"
        result = self.run_cli("preflight", "--root", str(self.root), "--target", "02_Projects/Demo/design.md",
            "--intent", "modify", "--query", "driver binding", "--authorized-path", str(target.parent),
            "--evidence-assessment", str(assessment), "--output", str(report))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(report.read_text())
        self.assertTrue(output["matched_trace_records"])
        self.assertEqual(output["semantic_conflicts"], [])
        self.assertEqual(output["unresolved_review_candidates"], [])
        self.assertEqual(output["gate_decision"], "allow")

    def test_read_paths_alone_do_not_establish_high_risk_coverage(self) -> None:
        target = self.root / "02_Projects/Demo/design.md"
        target.write_text("# Design\n")
        fix = self.root / "02_Projects/Demo/fixes/binding-fix.md"
        fix.write_text("# Binding fix\nKeep binding.\n")
        report = self.root / "preflight.json"
        result = self.run_cli("preflight", "--root", str(self.root), "--target", "02_Projects/Demo/design.md",
            "--intent", "modify", "--change-class", "protected_rewrite", "--query", "binding",
            "--authorized-path", str(target.parent), "--output", str(report))
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(report.read_text())
        self.assertTrue(output["source_documents_read"])
        self.assertTrue(any(r["condition"] == "high_risk_retrieval_insufficient" for r in output["triggered_rules"]))


if __name__ == "__main__":
    unittest.main()
