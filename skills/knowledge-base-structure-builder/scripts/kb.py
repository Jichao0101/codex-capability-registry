#!/usr/bin/env python3
"""Read-only governance CLI for structured Markdown knowledge bases."""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable

TOOL_VERSION = "0.1.0"
SKILL_ROOT = Path(__file__).resolve().parent.parent
RULES_ROOT = SKILL_ROOT / "rules"
DECLARED_FIELDS = {
    "status",
    "evidence_level",
    "evidence_refs",
    "review_after",
    "supersedes",
    "superseded_by",
    "protection_level",
    "change_policy",
}
EXCLUDED_DIRS = {".git", ".kb_cache", "reports", "node_modules", "__pycache__"}
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TERM_RE = re.compile(r"[A-Za-z0-9_./+-]+|[\u3400-\u9fff]{2,}")
RETRIEVAL_SUMMARY_TITLES = {"retrieval summary", "retrieval anchors"}
RETRIEVAL_SUMMARY_RECORD_TYPES = {"fix", "decision", "validation", "incident"}
FULL_PREFLIGHT_CHANGE_CLASSES = {
    "current_group_update",
    "delete",
    "move",
    "formal_knowledge_promotion",
    "external_source_promotion",
    "supersession",
    "conclusion_replacement",
    "protected_rewrite",
    "metadata_status_change",
    "evidence_level_change",
    "guarded_or_critical_target",
}


class GovernanceError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_rule(name: str) -> dict[str, Any]:
    path = RULES_ROOT / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot load rule file {path}: {exc}") from exc


def ruleset_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(RULES_ROOT.glob("*.yaml")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def skill_content_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(SKILL_ROOT.rglob("*")):
        if not path.is_file() or any(part in {"__pycache__", ".git"} for part in path.parts):
            continue
        digest.update(str(path.relative_to(SKILL_ROOT)).encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def repository_revision(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def normalize_authorized_paths(root: Path, values: list[str] | None) -> list[Path]:
    if not values:
        return [root]
    return [Path(value).resolve() for value in values]


def under_any(path: Path, roots: list[Path]) -> bool:
    resolved = path.resolve(strict=False)
    return any(resolved == root or root in resolved.parents for root in roots)


def resolve_under_root(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)


def vault_fingerprint(root: Path, authorized: list[Path] | None = None) -> str:
    digest = hashlib.sha256()
    for path in sorted(markdown_files(root, authorized)):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def parse_frontmatter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}
    raw = "\n".join(lines[1:end])
    try:
        import yaml  # type: ignore

        value = yaml.safe_load(raw)
        return json_safe(value) if isinstance(value, dict) else {}
    except Exception:
        return parse_simple_frontmatter(raw)


def json_safe(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def parse_simple_frontmatter(raw: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    active_list: str | None = None
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s+-\s+", line) and active_list:
            result.setdefault(active_list, []).append(parse_scalar(re.sub(r"^\s+-\s+", "", line)))
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            active_list = None
            continue
        key, raw_value = match.groups()
        if raw_value == "":
            result[key] = []
            active_list = key
        else:
            result[key] = parse_scalar(raw_value)
            active_list = None
    return result


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"null", "~"}:
        return None
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [] if not inner else [parse_scalar(v) for v in inner.split(",")]
    return value.strip("\"'")


def ensure_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def markdown_files(root: Path, authorized: list[Path] | None = None) -> Iterable[Path]:
    authorized_roots = [root] if authorized is None else authorized
    for path in root.rglob("*.md"):
        rel_parts = path.relative_to(root).parts
        if any(part in EXCLUDED_DIRS for part in rel_parts):
            continue
        if not under_any(path, authorized_roots):
            continue
        yield path


def path_defaults(rel: str) -> tuple[dict[str, Any], str | None]:
    rules = load_rule("path-defaults.yaml")
    effective = dict(rules["defaults"])
    matched_id = None
    for entry in rules["ordered_paths"]:
        if any(fnmatch.fnmatch(rel, pattern) for pattern in entry["patterns"]):
            for key in ("protection_level", "change_policy", "signal_strength"):
                if key in entry:
                    effective[key] = entry[key]
            matched_id = entry["id"]
            break
    return effective, matched_id


def derive_record_type(rel: str) -> str:
    lowered = rel.lower()
    if rel.endswith("_current.md") or rel.endswith("overview_current.md"):
        return "current"
    for needle, kind in (
        ("/fixes/", "fix"),
        ("修复", "fix"),
        ("/decisions/", "decision"),
        ("决策", "decision"),
        ("/validation_records/", "validation"),
        ("验证", "validation"),
        ("/incidents/", "incident"),
        ("事故", "incident"),
        ("current maintenance records", "maintenance"),
        ("维护记录", "maintenance"),
    ):
        if needle in lowered or needle in rel:
            return kind
    if rel.startswith("04_Sources/"):
        return "source"
    if rel.startswith("01_Knowledge/"):
        return "knowledge"
    if rel.startswith("03_Inbox/"):
        return "candidate"
    return "page"


def headings_and_sections(lines: list[str]) -> list[dict[str, Any]]:
    headings: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        match = HEADING_RE.match(line)
        if match:
            headings.append({"level": len(match.group(1)), "title": match.group(2), "line": index})
    for i, heading in enumerate(headings):
        heading["end_line"] = (headings[i + 1]["line"] - 1) if i + 1 < len(headings) else len(lines)
    return headings


def section_text(lines: list[str], heading: dict[str, Any]) -> str:
    return "\n".join(lines[heading["line"] - 1 : heading["end_line"]])


def find_retrieval_summary_sections(lines: list[str]) -> list[dict[str, Any]]:
    sections = []
    for heading in headings_and_sections(lines):
        title = heading["title"].strip().lower()
        normalized = re.sub(r"^\d+(?:\.\d+)*\s+", "", title)
        if title in RETRIEVAL_SUMMARY_TITLES or normalized in RETRIEVAL_SUMMARY_TITLES:
            sections.append(heading)
    return sections


def strip_sections(lines: list[str], sections: list[dict[str, Any]]) -> str:
    excluded: set[int] = set()
    for section in sections:
        excluded.update(range(section["line"], section["end_line"] + 1))
    return "\n".join(line for index, line in enumerate(lines, start=1) if index not in excluded)


def retrieval_summary_anchors(text: str) -> list[str]:
    anchors = set()
    anchors.update(re.findall(r"`([^`\n]{2,120})`", text))
    anchors.update(item.rstrip(".,;:，。；：)") for item in re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text))
    return sorted(item for item in anchors if item and not item.isdigit())


def retrieval_summary_quality(lines: list[str], section: dict[str, Any]) -> list[str]:
    text = section_text(lines, section)
    body_without_summary = strip_sections(lines, [section])
    issues = []
    non_empty = [line for line in text.splitlines()[1:] if line.strip()]
    if len(non_empty) > 18 or len(text) > 1400:
        issues.append("summary_too_long")
    anchors = retrieval_summary_anchors(text)
    if len(anchors) > 35:
        issues.append("too_many_anchors")
    unsupported = [anchor for anchor in anchors if anchor not in body_without_summary]
    if unsupported:
        issues.append("unsupported_anchors:" + ", ".join(unsupported[:8]))
    return issues


def derive_project_module(rel: str) -> tuple[str | None, str | None]:
    parts = Path(rel).parts
    if len(parts) >= 2 and parts[0] == "02_Projects":
        return parts[1], parts[2] if len(parts) >= 4 else None
    return None, None


def extract_document(root: Path, path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    rel = path.relative_to(root).as_posix()
    frontmatter = parse_frontmatter(text)
    schema = load_rule("schema-enums.yaml")
    defaults, path_rule = path_defaults(rel)

    declared = {key: frontmatter[key] for key in DECLARED_FIELDS if key in frontmatter}
    effective = dict(defaults)
    origins = {key: "default" for key in defaults}
    if path_rule:
        for key in ("protection_level", "change_policy", "signal_strength"):
            if key in effective:
                origins[key] = f"path_policy:{path_rule}"

    for key in DECLARED_FIELDS:
        if key in declared:
            effective[key] = declared[key]
            origins[key] = "declared"

    if "evidence_refs" not in declared:
        for alias in schema["legacy_aliases"]["evidence_refs"]:
            if alias in frontmatter:
                effective["evidence_refs"] = ensure_list(frontmatter[alias])
                origins["evidence_refs"] = f"legacy_alias:{alias}"
                break
    effective["evidence_refs"] = ensure_list(effective.get("evidence_refs"))
    effective["supersedes"] = ensure_list(effective.get("supersedes"))
    effective["superseded_by"] = ensure_list(effective.get("superseded_by"))

    doc_headings = headings_and_sections(lines)
    title = next((h["title"] for h in doc_headings if h["level"] == 1), path.stem)
    link_text = re.sub(r"```.*?```", "", text, flags=re.S)
    link_text = re.sub(r"`[^`]*`", "", link_text)
    links = [m.group(1).split("|")[0].split("#")[0].strip() for m in WIKILINK_RE.finditer(link_text)]
    record_type = derive_record_type(rel)
    signal = effective.get("signal_strength", "medium")
    if record_type in {"current", "fix", "decision", "validation", "incident"}:
        signal = "strong"
    if record_type == "maintenance" or effective.get("status") in {"superseded", "archived"}:
        signal = "weak"
    project, module = derive_project_module(rel)
    constraint_state = "present" if re.search(r"active constraints?|当前约束|硬约束", text, re.I) else "unknown"
    origins["constraint_state"] = "content_scan" if constraint_state == "present" else "default"

    return {
        "path": rel,
        "title": title,
        "declared": declared,
        "effective": effective,
        "value_origin": origins,
        "frontmatter": frontmatter,
        "record_type": record_type,
        "signal_strength": signal,
        "authority_status": "superseded" if effective.get("status") == "superseded" else ("authoritative" if signal == "strong" else "supporting"),
        "project": project,
        "module": module,
        "constraint_state": constraint_state,
        "headings": doc_headings,
        "links": [link for link in links if link],
        "document_hash": sha256_bytes(raw),
        "recorded_at": str(frontmatter.get("updated_at") or dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()),
        "search_text": text.lower(),
    }


def build_metadata(root: Path, authorized: list[Path] | None = None) -> dict[str, Any]:
    docs = [extract_document(root, path) for path in sorted(markdown_files(root, authorized))]
    authorized_roots = [root] if authorized is None else authorized
    return {
        "generated_at": utc_now(),
        "tool_version": TOOL_VERSION,
        "ruleset_hash": ruleset_hash(),
        "repository_revision": repository_revision(root),
        "root": str(root),
        "authorized_paths": [str(path) for path in authorized_roots],
        "documents": docs,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prune_old_reports(output: Path, kind: str, keep: int = 3) -> list[str]:
    reports = sorted(
        output.parent.glob(f"{kind}-*.json"),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    removed = []
    for path in reports[keep:]:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        removed.append(str(path))
    return removed


def default_cache(root: Path, kind: str) -> Path:
    return root / ".kb_cache" / kind / "index.json"


def cmd_metadata(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    authorized = normalize_authorized_paths(root, args.authorized_path)
    data = build_metadata(root, authorized)
    output = Path(args.output).resolve() if args.output else default_cache(root, "metadata")
    write_json(output, data)
    print(json.dumps({"output": str(output), "documents": len(data["documents"])}, ensure_ascii=False))
    return 0


def resolve_link(root: Path, source_rel: str, link: str, by_stem: dict[str, list[str]]) -> str | None:
    if not link or "://" in link or link.startswith("#"):
        return None
    candidate = link[:-3] if link.endswith(".md") else link
    direct = root / f"{candidate}.md"
    if direct.is_file():
        return direct.relative_to(root).as_posix()
    direct_dir = root / candidate
    if direct_dir.is_dir():
        return direct_dir.relative_to(root).as_posix()
    relative = root / Path(source_rel).parent / f"{candidate}.md"
    if relative.is_file():
        return relative.relative_to(root).as_posix()
    matches = by_stem.get(Path(candidate).name, [])
    return matches[0] if len(matches) == 1 else None


def supersession_target(root: Path, value: str, paths: set[str], by_stem: dict[str, list[str]]) -> str | None:
    normalized = value.strip().strip("[]")
    if normalized in paths:
        return normalized
    if normalized + ".md" in paths:
        return normalized + ".md"
    matches = by_stem.get(Path(normalized).stem, [])
    return matches[0] if len(matches) == 1 else None


def find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            start = visiting.index(node)
            cycles.append(visiting[start:] + [node])
            return
        if node in visited:
            return
        visiting.append(node)
        for nxt in graph.get(node, []):
            visit(nxt)
        visiting.pop()
        visited.add(node)

    for node in graph:
        visit(node)
    return cycles


def lint_report(root: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    severity = load_rule("lint-severity.yaml")["rules"]
    schema = load_rule("schema-enums.yaml")
    docs = metadata["documents"]
    paths = {doc["path"] for doc in docs}
    by_stem: dict[str, list[str]] = {}
    for path in paths:
        by_stem.setdefault(Path(path).stem, []).append(path)
    findings: list[dict[str, Any]] = []

    def add(rule_id: str, path: str | None, message: str, **extra: Any) -> None:
        findings.append({"rule_id": rule_id, "severity": severity[rule_id]["severity"], "path": path, "message": message, **extra})

    required_entries = ["README.md", "01_Knowledge/知识总览.md", "02_Projects/项目总览.md", "03_Inbox/候选内容索引.md", "04_Sources/来源索引.md"]
    for entry in required_entries:
        if entry not in paths:
            add("KB-LINT-001", entry, "required entry is missing")

    inbound = {path: 0 for path in paths}
    for doc in docs:
        for link in doc["links"]:
            resolved = resolve_link(root, doc["path"], link, by_stem)
            if resolved:
                if resolved in inbound:
                    inbound[resolved] += 1
            elif not ("://" in link):
                add("KB-LINT-002", doc["path"], f"missing wikilink target: {link}")
        uses_schema_v2 = any(key in doc["frontmatter"] for key in ("evidence_level", "evidence_refs", "review_after", "protection_level", "change_policy"))
        if uses_schema_v2:
            for key, values in schema["enums"].items():
                if key in doc["declared"] and doc["declared"][key] not in values:
                    add("KB-LINT-004", doc["path"], f"invalid {key}: {doc['declared'][key]}")
        if doc["path"].startswith("01_Knowledge/") and doc["path"] != "01_Knowledge/知识总览.md":
            required = ("status", "summary", "scope", "risks")
            missing = [key for key in required if key not in doc["frontmatter"]]
            has_source = any(key in doc["frontmatter"] for key in ("evidence_refs", "sources", "source"))
            if not has_source:
                missing.append("evidence_refs/source(s)")
            if missing:
                add("KB-LINT-005", doc["path"], "missing formal metadata", missing=missing)
        if doc["frontmatter"].get("single_pass_recoverable") is True:
            add("KB-LINT-008", doc["path"], "single_pass_recoverable=true requires independent verification")
        if doc["record_type"] in RETRIEVAL_SUMMARY_RECORD_TYPES:
            path = root / doc["path"]
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                lines = []
            summaries = find_retrieval_summary_sections(lines)
            if not summaries:
                add("KB-LINT-009", doc["path"], "missing Retrieval Summary or Retrieval Anchors section")
            else:
                for summary_section in summaries:
                    issues = retrieval_summary_quality(lines, summary_section)
                    if issues:
                        add(
                            "KB-LINT-010",
                            doc["path"],
                            "Retrieval Summary needs manual review",
                            section=summary_section["title"],
                            issues=issues,
                        )

    entry_set = set(required_entries)
    for path, count in inbound.items():
        if count == 0 and path not in entry_set and not path.startswith("90_Archive/"):
            add("KB-LINT-003", path, "page has no inbound wikilink")

    graph: dict[str, list[str]] = {}
    for doc in docs:
        targets = []
        for value in ensure_list(doc["effective"].get("supersedes")):
            resolved = supersession_target(root, value, paths, by_stem)
            if resolved:
                targets.append(resolved)
            else:
                add("KB-LINT-006", doc["path"], f"missing supersession target: {value}")
        graph[doc["path"]] = targets
    for cycle in find_cycles(graph):
        add("KB-LINT-007", cycle[0], "supersession cycle", cycle=cycle)

    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    return {
        "generated_at": utc_now(),
        "tool_version": TOOL_VERSION,
        "skill_content_hash": skill_content_hash(),
        "ruleset_hash": ruleset_hash(),
        "repository_revision": repository_revision(root),
        "summary": counts,
        "findings": findings,
    }


def timestamped_report(root: Path, kind: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%S%f")
    return root / "reports" / "kb" / kind / f"{kind}-{stamp}.json"


def cmd_lint(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    authorized = normalize_authorized_paths(root, args.authorized_path)
    metadata = build_metadata(root, authorized)
    report = lint_report(root, metadata)
    default_output = args.output is None
    output = Path(args.output).resolve() if args.output else timestamped_report(root, "lint")
    write_json(output, report)
    pruned = prune_old_reports(output, "lint") if default_output else []
    print(json.dumps({"output": str(output), "summary": report["summary"], "pruned_reports": pruned}, ensure_ascii=False))
    return 1 if report["summary"].get("error", 0) else 0


def build_trace_index(root: Path, authorized: list[Path] | None = None) -> dict[str, Any]:
    metadata = build_metadata(root, authorized)
    records = []
    for doc in metadata["documents"]:
        records.append({
            "path": doc["path"],
            "title": doc["title"],
            "record_type": doc["record_type"],
            "signal_strength": doc["signal_strength"],
            "authority_status": doc["authority_status"],
            "project": doc["project"],
            "module": doc["module"],
            "effective": doc["effective"],
            "value_origin": doc["value_origin"],
            "headings": doc["headings"],
            "links": doc["links"],
            "document_hash": doc["document_hash"],
            "search_text": doc["search_text"],
        })
    paths = {record["path"] for record in records}
    by_stem: dict[str, list[str]] = {}
    for path in paths:
        by_stem.setdefault(Path(path).stem, []).append(path)
    graph: dict[str, list[str]] = {}
    for record in records:
        graph[record["path"]] = [
            resolved
            for value in ensure_list(record["effective"].get("supersedes"))
            if (resolved := supersession_target(root, value, paths, by_stem))
        ]
    return {
        "generated_at": utc_now(),
        "tool_version": TOOL_VERSION,
        "skill_content_hash": skill_content_hash(),
        "ruleset_hash": ruleset_hash(),
        "repository_revision": repository_revision(root),
        "vault_fingerprint": vault_fingerprint(root, authorized),
        "authorized_paths": metadata["authorized_paths"],
        "records": records,
        "supersession_cycles": find_cycles(graph),
    }


def cmd_trace_index(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    authorized = [Path(value).resolve() for value in args.authorized_path]
    index = build_trace_index(root, authorized)
    output = Path(args.output).resolve() if args.output else default_cache(root, "trace-index")
    write_json(output, index)
    print(json.dumps({"output": str(output), "records": len(index["records"])}, ensure_ascii=False))
    return 0


def first_body_paragraph(text: str) -> str:
    body = re.sub(r"(?s)^---\n.*?\n---\n", "", text).strip()
    lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            if lines:
                break
            continue
        lines.append(stripped)
        if len(" ".join(lines)) >= 240:
            break
    return " ".join(lines)[:300]


def extract_retrieval_terms(text: str) -> dict[str, list[str]]:
    code_spans = re.findall(r"`([^`\n]{2,120})`", text)
    paths = [item.rstrip(".,;:，。；：)") for item in re.findall(r"(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+", text)]
    symbols = re.findall(r"\b[A-Za-z_][A-Za-z0-9_:.]{2,}\b", text)
    symptoms = []
    constraints = []
    validation = []
    for line in text.splitlines():
        if re.search(r"症状|问题|失败|异常|coredump|crash|error|bug|回归", line, re.I):
            symptoms.append(line.strip()[:200])
        if re.search(r"约束|必须|不得|保持|禁止|兼容|constraint", line, re.I):
            constraints.append(line.strip()[:200])
        if re.search(r"验证|测试|复核|通过|失败|validation|test|pytest|unittest|lint", line, re.I):
            validation.append(line.strip()[:200])
    return {
        "anchors": sorted({item for item in code_spans if len(item) <= 120})[:40],
        "paths": sorted({item for item in paths if "/" in item})[:40],
        "symbols": sorted({item for item in symbols if not item.isdigit()})[:80],
        "symptoms": symptoms[:20],
        "constraints": constraints[:20],
        "validation": validation[:20],
    }


def compact_list(items: list[str], limit: int = 5) -> str:
    clean = []
    for item in items:
        stripped = re.sub(r"\s+", " ", item).strip()
        if stripped and stripped not in clean:
            clean.append(stripped)
        if len(clean) >= limit:
            break
    return "; ".join(clean)


def proposed_retrieval_summary(doc: dict[str, Any], raw: str) -> str:
    terms = extract_retrieval_terms(raw)
    title = doc["title"]
    summary = str(doc["frontmatter"].get("summary") or first_body_paragraph(raw))
    topic = title
    component = " / ".join(item for item in (doc.get("project"), doc.get("module")) if item)
    symptoms = compact_list(terms["symptoms"], 3)
    affected_paths = compact_list(terms["paths"], 5)
    symbols = compact_list(terms["anchors"] + terms["symbols"], 8)
    constraints = compact_list(terms["constraints"], 3)
    validation = compact_list(terms["validation"], 3)
    aliases = compact_list([title, summary], 2)
    fields = [
        ("topic", topic),
        ("component", component),
        ("symptoms", symptoms),
        ("affected_paths", affected_paths),
        ("symbols", symbols),
        ("constraints", constraints),
        ("validation", validation),
        ("aliases", aliases),
    ]
    lines = ["## Retrieval Summary", ""]
    for key, value in fields:
        lines.append(f"- {key}: {value or 'manual_review_required'}")
    return "\n".join(lines)


def build_retrieval_summary_proposals(root: Path, authorized: list[Path], limit: int) -> dict[str, Any]:
    metadata = build_metadata(root, authorized)
    proposals = []
    for doc in metadata["documents"]:
        if doc["record_type"] not in RETRIEVAL_SUMMARY_RECORD_TYPES:
            continue
        path = root / doc["path"]
        raw = path.read_text(encoding="utf-8", errors="replace")
        lines = raw.splitlines()
        if find_retrieval_summary_sections(lines):
            continue
        proposal = proposed_retrieval_summary(doc, raw)
        proposals.append({
            "target_path": doc["path"],
            "record_type": doc["record_type"],
            "status": doc["effective"].get("status"),
            "protection_level": doc["effective"].get("protection_level"),
            "change_policy": doc["effective"].get("change_policy"),
            "proposal_only": True,
            "gate_reason": "proposal_only; no trace-index/preflight/hash-check required until Markdown apply",
            "apply_check": {
                "recommended_command": "minimal-apply-check",
                "change_class": "retrieval_summary_append",
                "intent": "append",
            },
            "proposed_section": proposal,
            "supporting_source": {
                "title": doc["title"],
                "summary": doc["frontmatter"].get("summary"),
                "evidence_refs": doc["effective"].get("evidence_refs", []),
                "first_body_paragraph": first_body_paragraph(raw),
            },
        })
        if len(proposals) >= limit:
            break
    return {
        "generated_at": utc_now(),
        "tool_version": TOOL_VERSION,
        "skill_content_hash": skill_content_hash(),
        "ruleset_hash": ruleset_hash(),
        "repository_revision": repository_revision(root),
        "authorized_paths": [str(path) for path in authorized],
        "proposal_count": len(proposals),
        "proposals": proposals,
    }


def cmd_retrieval_summary_proposals(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    authorized = normalize_authorized_paths(root, args.authorized_path)
    report = build_retrieval_summary_proposals(root, authorized, args.limit)
    default_output = args.output is None
    output = Path(args.output).resolve() if args.output else timestamped_report(root, "retrieval-summary-proposals")
    write_json(output, report)
    pruned = prune_old_reports(output, "retrieval-summary-proposals") if default_output else []
    print(json.dumps({"output": str(output), "proposals": report["proposal_count"], "pruned_reports": pruned}, ensure_ascii=False))
    return 0


def load_json_file(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceError(f"JSON file must contain an object: {path}")
    return value


def check_retrieval_package(root: Path, package: dict[str, Any], authorized: list[Path]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []

    def add(severity: str, code: str, message: str, **extra: Any) -> None:
        issues.append({"severity": severity, "code": code, "message": message, **extra})

    package_paths = package.get("authorized_paths")
    if not isinstance(package_paths, list) or not package_paths:
        add("error", "KBR-PKG-001", "retrieval_package.authorized_paths must be a non-empty list")
        package_paths = []
    for value in package_paths:
        path = resolve_under_root(root, str(value))
        if not under_any(path, authorized):
            add("error", "KBR-PKG-002", "package authorized path is outside Builder authorized paths", path=str(value))

    sections = package.get("source_sections_read")
    if not isinstance(sections, list):
        add("error", "KBR-PKG-003", "retrieval_package.source_sections_read must be a list")
        sections = []
    source_paths = []
    for section in sections:
        if not isinstance(section, dict):
            add("error", "KBR-PKG-004", "source section entry must be an object")
            continue
        source_path = section.get("path") or section.get("source_path")
        if not source_path:
            add("error", "KBR-PKG-005", "source section must include path or source_path")
            continue
        candidate = (root / str(source_path)).resolve(strict=False)
        if not under_any(candidate, authorized):
            add("error", "KBR-PKG-006", "source section path is outside authorized paths", path=str(source_path))
            continue
        if not candidate.is_file():
            add("error", "KBR-PKG-007", "source section path is not readable Markdown", path=str(source_path))
            continue
        source_paths.append(str(source_path))

    limitations = package.get("recall_limitations")
    if limitations is None:
        add("warning", "KBR-PKG-008", "recall_limitations is missing")
    elif not isinstance(limitations, list):
        add("error", "KBR-PKG-009", "recall_limitations must be a list")

    candidate_fields = ("candidate_decisions", "candidate_constraints", "candidate_fixes", "candidate_supersessions")
    for field in candidate_fields:
        value = package.get(field, [])
        if not isinstance(value, list):
            add("error", "KBR-PKG-010", f"{field} must be a list")

    return {
        "valid": not any(issue["severity"] == "error" for issue in issues),
        "checked_at": utc_now(),
        "authorized_paths": [str(path) for path in authorized],
        "package_authorized_paths": package_paths,
        "source_sections_read": source_paths,
        "recall_limitations": limitations if isinstance(limitations, list) else [],
        "issues": issues,
    }


def cmd_retrieval_package_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    authorized = normalize_authorized_paths(root, args.authorized_path)
    package = load_json_file(args.package)
    result = check_retrieval_package(root, package, authorized)
    if args.output:
        write_json(Path(args.output).resolve(), result)
        print(json.dumps({"output": str(Path(args.output).resolve()), "valid": result["valid"], "issues": len(result["issues"])}, ensure_ascii=False))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["valid"] else 2


def query_terms(*values: str) -> list[str]:
    terms: list[str] = []
    ignored = {".md", "md", "02_projects", "01_knowledge", "03_inbox", "04_sources"}
    for value in values:
        for term in TERM_RE.findall(value.lower()):
            if len(term) >= 2 and term not in ignored and term not in terms:
                terms.append(term)
    return terms


def match_trace_records(
    index: dict[str, Any],
    target: str,
    query: str,
    limit: int,
    required_paths: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    terms = query_terms(query)
    target_parts = set(Path(target).parts)
    required = set(required_paths or [])
    matches = []
    for record in index["records"]:
        if record["path"] == target:
            continue
        matched = [term for term in terms if term in record["search_text"] or term in record["path"].lower()]
        shared = len(target_parts.intersection(Path(record["path"]).parts))
        is_required = record["path"] in required
        if not is_required and not matched and shared < 2:
            continue
        weight = {"strong": 20, "medium": 10, "weak": 1}.get(record["signal_strength"], 5)
        score = (1000 if is_required else 0) + weight + len(matched) * 3 + shared
        matches.append({**record, "matched_terms": matched, "score": score, "source": "retrieval_package" if is_required else "trace_index"})
    matches.sort(key=lambda item: (-item["score"], item["path"]))
    return matches[:limit], terms


def section_read_evidence(root: Path, record: dict[str, Any], terms: list[str]) -> dict[str, Any]:
    path = root / record["path"]
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()
    headings = headings_and_sections(lines)
    selected = []
    for heading in headings:
        start = heading["line"]
        end = heading["end_line"]
        section = "\n".join(lines[start - 1:end])
        matched = [term for term in terms if term in section.lower()]
        if matched:
            selected.append({
                "heading": heading["title"],
                "line_start": start,
                "line_end": end,
                "section_hash": sha256_bytes(section.encode()),
                "matched_terms": matched,
            })
        if len(selected) >= 5:
            break
    if not selected:
        end = min(len(lines), 80)
        section = "\n".join(lines[:end])
        selected.append({"heading": headings[0]["title"] if headings else "document-start", "line_start": 1, "line_end": end, "section_hash": sha256_bytes(section.encode()), "matched_terms": []})
    return {
        "path": record["path"],
        "reason": "trace match requires original Markdown read",
        "matched_terms": record.get("matched_terms", []),
        "sections_read": selected,
        "document_hash": sha256_bytes(raw),
        "status": record["effective"].get("status"),
        "protection_level": record["effective"].get("protection_level"),
        "read_at": utc_now(),
    }


def is_authorized(target: Path, authorized: list[Path]) -> bool:
    resolved = target.resolve(strict=False)
    return any(resolved == path or path in resolved.parents for path in authorized)


def nearest_existing_parent(path: Path) -> Path:
    candidate = path.parent
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def evaluate_gate(context: dict[str, Any]) -> tuple[str, list[dict[str, Any]], bool]:
    table = load_rule("gate-decision-table.yaml")
    condition_values = {
        "target_forbidden": context["target_forbidden"],
        "target_unreadable": context["target_unreadable"],
        "status_verified": context["effective"].get("status") == "verified",
        "protection_critical": context["effective"].get("protection_level") == "critical",
        "protection_guarded": context["effective"].get("protection_level") == "guarded",
        "append_only_violation": context["effective"].get("change_policy") == "append_only" and context["intent"] in {"modify", "delete", "supersede"},
        "supersession_missing": context["effective"].get("change_policy") == "explicit_supersession_required" and (context["intent"] == "supersede" or context["replaces_conclusion"]) and not (
            context["supersedes"]
            and context["supersession_reason"]
            and context["evidence_refs"]
            and set(context["supersedes"]).issubset(set(context["reciprocal_supersession"]))
        ),
        "strong_record_unread": any(r["signal_strength"] == "strong" and r["path"] not in context["read_paths"] for r in context["matches"]),
        "protected_source_unread": any(r["effective"].get("protection_level") in {"guarded", "critical"} and r["path"] not in context["read_paths"] for r in context["matches"]),
        "supersession_conflict": bool(context["supersession_conflicts"]),
        "only_weak_records": bool(context["matches"]) and all(r["signal_strength"] == "weak" for r in context["matches"]),
        "default_allow": True,
    }
    triggered = []
    decisions = []
    validation_required = False
    for rule in table["rules"]:
        if not condition_values[rule["condition"]]:
            continue
        triggered.append({"rule_id": rule["id"], "condition": rule["condition"], "decision": rule.get("decision")})
        if rule.get("decision"):
            decisions.append(rule["decision"])
        validation_required = validation_required or rule.get("validation_plan_required", False)
    decision = "blocked" if "blocked" in decisions else ("manual_review" if "manual_review" in decisions else "allow")
    return decision, triggered, validation_required


def load_or_build_trace(root: Path, override: str | None = None, authorized: list[Path] | None = None) -> dict[str, Any]:
    path = Path(override).resolve() if override else default_cache(root, "trace-index")
    authorized_roots = [root] if authorized is None else authorized
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            current_fingerprint = vault_fingerprint(root, authorized_roots)
            if (
                data.get("ruleset_hash") == ruleset_hash()
                and data.get("vault_fingerprint") == current_fingerprint
                and data.get("authorized_paths") == [str(path) for path in authorized_roots]
            ):
                return data
        except (OSError, json.JSONDecodeError):
            pass
        if override:
            raise GovernanceError(f"explicit trace index is stale or invalid: {path}")
    data = build_trace_index(root, authorized_roots)
    write_json(path, data)
    return data


def target_metadata(root: Path, target: Path) -> dict[str, Any]:
    if target.is_file():
        return extract_document(root, target)
    rel = target.relative_to(root).as_posix()
    defaults, path_rule = path_defaults(rel)
    return {
        "path": rel,
        "declared": {},
        "effective": defaults,
        "value_origin": {key: (f"path_policy:{path_rule}" if key in {"protection_level", "change_policy", "signal_strength"} and path_rule else "default") for key in defaults},
        "document_hash": None,
    }


def cmd_preflight(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = (root / args.target).resolve(strict=False)
    try:
        target_rel = target.relative_to(root).as_posix()
    except ValueError:
        target_rel = args.target
    authorized = [Path(value).resolve() for value in args.authorized_path]
    forbidden = [Path(value).resolve() for value in args.forbidden_path]
    policy_file = Path(args.policy_file).resolve() if args.policy_file else root / "AGENTS.md"
    policy_unreadable = not policy_file.is_file() or not os.access(policy_file, os.R_OK)
    target_forbidden = (
        policy_unreadable
        or not authorized
        or not is_authorized(target, authorized)
        or any(is_authorized(target, [path]) for path in forbidden)
        or (root not in target.parents and target != root)
    )
    create_parent = nearest_existing_parent(target)
    target_unreadable = (args.intent != "create" and (not target.is_file() or not os.access(target, os.R_OK))) or (
        args.intent == "create" and (not create_parent.is_dir() or not os.access(create_parent, os.R_OK))
    )
    metadata = target_metadata(root, target) if not target_forbidden else {"declared": {}, "effective": {}, "value_origin": {}, "document_hash": None}
    package_check = None
    package_source_paths: list[str] = []
    if args.retrieval_package:
        package = load_json_file(args.retrieval_package)
        package_check = check_retrieval_package(root, package, authorized)
        package_source_paths = package_check["source_sections_read"]
    index = load_or_build_trace(root, args.trace_index, authorized)
    matches, terms = match_trace_records(index, target_rel, args.query, args.limit, package_source_paths)
    source_reads = []
    read_errors = []
    for record in matches:
        should_read = (
            record["path"] in package_source_paths
            or record["signal_strength"] == "strong"
            or record["effective"].get("protection_level") in {"guarded", "critical"}
        )
        if not should_read:
            continue
        try:
            source_reads.append(section_read_evidence(root, record, terms))
        except OSError as exc:
            read_errors.append({"path": record["path"], "error": str(exc)})
    read_paths = {item["path"] for item in source_reads}
    conflicts = index.get("supersession_cycles", [])
    context = {
        "target_forbidden": target_forbidden,
        "target_unreadable": target_unreadable,
        "effective": metadata.get("effective", {}),
        "intent": args.intent,
        "supersedes": args.supersedes,
        "supersession_reason": args.supersession_reason,
        "evidence_refs": args.evidence_ref,
        "replaces_conclusion": args.replaces_conclusion,
        "reciprocal_supersession": args.reciprocal_supersession,
        "matches": matches,
        "read_paths": read_paths,
        "supersession_conflicts": conflicts,
    }
    decision, triggered, validation_required = evaluate_gate(context)
    if package_check and not package_check["valid"]:
        decision = "blocked"
        triggered.append({"rule_id": "KB-GATE-012", "condition": "invalid_retrieval_package", "decision": "blocked"})
    if read_errors:
        decision = "blocked"
        triggered.append({"rule_id": "KB-GATE-008", "condition": "source_read_error", "decision": "blocked"})
    target_hashes = []
    if target.is_file():
        target_hashes.append({"path": target_rel, "hash": sha256_file(target)})
    report = {
        "preflight_snapshot": {
            "generated_at": utc_now(),
            "skill_version": "unversioned",
            "skill_content_hash": skill_content_hash(),
            "tool_version": TOOL_VERSION,
            "ruleset_hash": ruleset_hash(),
            "repository_revision": repository_revision(root),
            "vault_fingerprint": index.get("vault_fingerprint"),
            "authorized_paths": [str(path) for path in authorized],
            "policy_file": str(policy_file),
            "policy_hash": sha256_file(policy_file) if not policy_unreadable else None,
            "target_files": [target_rel],
            "target_hashes_before_write": target_hashes,
            "source_hashes_valid": not read_errors,
        },
        "input": {
            "target_path": target_rel,
            "target_declared_metadata": metadata.get("declared", {}),
            "target_effective_metadata": metadata.get("effective", {}),
            "change_intent": args.intent,
            "change_summary": args.change_summary,
        },
        "matched_trace_records": [{k: v for k, v in item.items() if k != "search_text"} for item in matches],
        "source_documents_read": source_reads,
        "retrieval_package_check": package_check,
        "source_read_errors": read_errors,
        "derived_constraints": [
            {"path": read["path"], "sections": [section["heading"] for section in read["sections_read"]]}
            for read in source_reads
            if any(re.search(r"constraints?|约束|必须|不得", section["heading"], re.I) for section in read["sections_read"])
        ],
        "potentially_overwritten_fixes": [item["path"] for item in matches if item["record_type"] == "fix"],
        "required_validations": [],
        "authorization_gaps": ([target_rel] if target_forbidden else []) + ([str(policy_file)] if policy_unreadable else []),
        "change_policy_checks": {
            "append_only_violations": [target_rel] if context["effective"].get("change_policy") == "append_only" and args.intent in {"modify", "delete", "supersede"} else [],
            "supersession_requirements": [] if not any(t["rule_id"] == "KB-GATE-007" for t in triggered) else ["supersedes", "reciprocal superseded_by update", "reason", "evidence_refs"],
        },
        "weak_record_hits": [item["path"] for item in matches if item["signal_strength"] == "weak"],
        "triggered_rules": triggered,
        "validation_plan_required": validation_required,
        "gate_decision": decision,
    }
    output = Path(args.output).resolve() if args.output else timestamped_report(root, "preflight")
    write_json(output, report)
    pruned = prune_old_reports(output, "preflight") if args.output is None else []
    print(json.dumps({"output": str(output), "gate_decision": decision, "matched_records": len(matches), "pruned_reports": pruned}, ensure_ascii=False))
    return 0 if decision == "allow" else (2 if decision == "manual_review" else 3)


def cmd_hash_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    mismatches = []
    snapshot = report.get("preflight_snapshot", {})
    if snapshot.get("ruleset_hash") != ruleset_hash():
        mismatches.append({"path": "<ruleset>", "expected": snapshot.get("ruleset_hash"), "actual": ruleset_hash()})
    if snapshot.get("skill_content_hash") != skill_content_hash():
        mismatches.append({"path": "<skill>", "expected": snapshot.get("skill_content_hash"), "actual": skill_content_hash()})
    authorized = [Path(value).resolve() for value in snapshot.get("authorized_paths", [str(root)])]
    current_vault_fingerprint = vault_fingerprint(root, authorized)
    if snapshot.get("vault_fingerprint") != current_vault_fingerprint:
        mismatches.append({"path": "<vault>", "expected": snapshot.get("vault_fingerprint"), "actual": current_vault_fingerprint})
    policy_path = Path(snapshot["policy_file"]) if snapshot.get("policy_file") else None
    policy_hash = sha256_file(policy_path) if policy_path and policy_path.is_file() else None
    if snapshot.get("policy_hash") != policy_hash:
        mismatches.append({"path": str(policy_path or "<policy>"), "expected": snapshot.get("policy_hash"), "actual": policy_hash})
    for item in snapshot.get("target_hashes_before_write", []):
        path = root / item["path"]
        current = sha256_file(path) if path.is_file() else None
        if current != item["hash"]:
            mismatches.append({"path": item["path"], "expected": item["hash"], "actual": current})
    for item in report.get("source_documents_read", []):
        path = root / item["path"]
        current = sha256_file(path) if path.is_file() else None
        if current != item["document_hash"]:
            mismatches.append({"path": item["path"], "expected": item["document_hash"], "actual": current})
    result = {"valid": not mismatches, "checked_at": utc_now(), "mismatches": mismatches}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not mismatches else 4


def cmd_minimal_apply_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    target = (root / args.target).resolve(strict=False)
    try:
        target_rel = target.relative_to(root).as_posix()
    except ValueError:
        target_rel = args.target
    authorized = [Path(value).resolve() for value in args.authorized_path]
    forbidden = [Path(value).resolve() for value in args.forbidden_path]
    policy_file = Path(args.policy_file).resolve() if args.policy_file else root / "AGENTS.md"
    policy_unreadable = not policy_file.is_file() or not os.access(policy_file, os.R_OK)
    target_outside_root = root not in target.parents and target != root
    target_forbidden = (
        policy_unreadable
        or not authorized
        or target_outside_root
        or not is_authorized(target, authorized)
        or any(is_authorized(target, [path]) for path in forbidden)
    )
    create_parent = nearest_existing_parent(target)
    target_unreadable = (args.intent != "create" and (not target.is_file() or not os.access(target, os.R_OK))) or (
        args.intent == "create" and (not create_parent.is_dir() or not os.access(create_parent, os.R_OK))
    )
    metadata = target_metadata(root, target) if not target_outside_root and not target_forbidden else {"declared": {}, "effective": {}, "document_hash": None, "record_type": None}
    record_type = metadata.get("record_type") or derive_record_type(target_rel)
    effective = metadata.get("effective", {})
    full_preflight_reasons = []
    if args.change_class in FULL_PREFLIGHT_CHANGE_CLASSES:
        full_preflight_reasons.append(f"change_class:{args.change_class}")
    if args.intent not in {"append", "create"}:
        full_preflight_reasons.append(f"intent:{args.intent}")
    if record_type == "current":
        full_preflight_reasons.append("target_record_type:current")
    if target_rel.startswith("01_Knowledge/"):
        full_preflight_reasons.append("formal_knowledge_target")
    if effective.get("protection_level") in {"guarded", "critical"}:
        full_preflight_reasons.append(f"protection_level:{effective.get('protection_level')}")
    if args.replaces_conclusion:
        full_preflight_reasons.append("replaces_conclusion")
    if args.supersedes:
        full_preflight_reasons.append("supersedes")

    target_hashes = []
    if target.is_file():
        target_hashes.append({"path": target_rel, "hash": sha256_file(target)})
    elif args.intent != "create":
        target_unreadable = True

    decision = "allow"
    if target_forbidden or target_unreadable:
        decision = "blocked"
    elif full_preflight_reasons:
        decision = "requires_full_preflight"

    report = {
        "minimal_apply_snapshot": {
            "generated_at": utc_now(),
            "skill_content_hash": skill_content_hash(),
            "tool_version": TOOL_VERSION,
            "ruleset_hash": ruleset_hash(),
            "repository_revision": repository_revision(root),
            "authorized_paths": [str(path) for path in authorized],
            "policy_file": str(policy_file),
            "policy_hash": sha256_file(policy_file) if not policy_unreadable else None,
            "target_files": [target_rel],
            "target_hashes_before_apply": target_hashes,
        },
        "input": {
            "target_path": target_rel,
            "intent": args.intent,
            "change_class": args.change_class,
            "change_summary": args.change_summary,
            "target_effective_metadata": effective,
            "target_record_type": record_type,
        },
        "checks": {
            "policy_readable": not policy_unreadable,
            "authorized_path_provided": bool(authorized),
            "target_in_authorized_scope": bool(authorized) and is_authorized(target, authorized),
            "target_in_forbidden_scope": any(is_authorized(target, [path]) for path in forbidden),
            "target_readable_or_creatable": not target_unreadable,
            "trace_index_used": False,
            "source_documents_read": False,
            "full_preflight_required": bool(full_preflight_reasons),
            "full_preflight_reasons": full_preflight_reasons,
        },
        "gate_decision": decision,
    }
    output = Path(args.output).resolve() if args.output else timestamped_report(root, "minimal-apply-check")
    write_json(output, report)
    pruned = prune_old_reports(output, "minimal-apply-check") if args.output is None else []
    print(json.dumps({"output": str(output), "gate_decision": decision, "pruned_reports": pruned}, ensure_ascii=False))
    if decision == "allow":
        return 0
    if decision == "requires_full_preflight":
        return 2
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("metadata", cmd_metadata), ("lint", cmd_lint), ("trace-index", cmd_trace_index)):
        command = sub.add_parser(name)
        command.add_argument("--root", required=True)
        command.add_argument("--authorized-path", action="append", default=[], help="repeat for every explicitly authorized root")
        command.add_argument("--output")
        command.set_defaults(handler=handler)
    summary_proposals = sub.add_parser("retrieval-summary-proposals")
    summary_proposals.add_argument("--root", required=True)
    summary_proposals.add_argument("--authorized-path", action="append", default=[], help="repeat for every explicitly authorized root")
    summary_proposals.add_argument("--limit", type=int, default=50)
    summary_proposals.add_argument("--output")
    summary_proposals.set_defaults(handler=cmd_retrieval_summary_proposals)
    package_check = sub.add_parser("retrieval-package-check")
    package_check.add_argument("--root", required=True)
    package_check.add_argument("--package", required=True)
    package_check.add_argument("--authorized-path", action="append", default=[], help="repeat for every explicitly authorized root")
    package_check.add_argument("--output")
    package_check.set_defaults(handler=cmd_retrieval_package_check)
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--root", required=True)
    preflight.add_argument("--target", required=True)
    preflight.add_argument("--intent", choices=("create", "append", "modify", "delete", "supersede"), required=True)
    preflight.add_argument("--authorized-path", action="append", default=[], help="repeat for every explicitly authorized root")
    preflight.add_argument("--forbidden-path", action="append", default=[], help="repeat for policy-forbidden roots resolved by the workflow")
    preflight.add_argument("--policy-file", help="policy authority; defaults to <root>/AGENTS.md")
    preflight.add_argument("--query", default="")
    preflight.add_argument("--retrieval-package", help="path to Retriever retrieval_package JSON to validate and use as source-section hints")
    preflight.add_argument("--change-summary", default="")
    preflight.add_argument("--supersedes", action="append", default=[])
    preflight.add_argument("--supersession-reason", default="")
    preflight.add_argument("--evidence-ref", action="append", default=[])
    preflight.add_argument("--replaces-conclusion", action="store_true")
    preflight.add_argument("--reciprocal-supersession", action="append", default=[], help="old documents whose superseded_by will point to the target")
    preflight.add_argument("--limit", type=int, default=20)
    preflight.add_argument("--trace-index", help="explicit trace index; stale input blocks instead of rebuilding")
    preflight.add_argument("--output")
    preflight.set_defaults(handler=cmd_preflight)
    minimal = sub.add_parser("minimal-apply-check")
    minimal.add_argument("--root", required=True)
    minimal.add_argument("--target", required=True)
    minimal.add_argument("--intent", choices=("create", "append", "modify", "delete", "supersede"), required=True)
    minimal.add_argument("--change-class", required=True)
    minimal.add_argument("--authorized-path", action="append", default=[], help="repeat for every explicitly authorized root")
    minimal.add_argument("--forbidden-path", action="append", default=[], help="repeat for policy-forbidden roots resolved by the workflow")
    minimal.add_argument("--policy-file", help="policy authority; defaults to <root>/AGENTS.md")
    minimal.add_argument("--change-summary", default="")
    minimal.add_argument("--supersedes", action="append", default=[])
    minimal.add_argument("--replaces-conclusion", action="store_true")
    minimal.add_argument("--output")
    minimal.set_defaults(handler=cmd_minimal_apply_check)
    check = sub.add_parser("hash-check")
    check.add_argument("--root", required=True)
    check.add_argument("--report", required=True)
    check.set_defaults(handler=cmd_hash_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except GovernanceError as exc:
        print(json.dumps({"error": str(exc), "gate_decision": "blocked"}, ensure_ascii=False), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
