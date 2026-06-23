#!/usr/bin/env python3
"""Execute an agent-authored query plan against authorized Markdown paths."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ALLOWED_CANDIDATE_FIELDS = {
    "candidate_decisions",
    "candidate_constraints",
    "candidate_fixes",
    "candidate_supersessions",
}

MAX_BATCHES_LIMIT = 30
MAX_TERMS_PER_BATCH_LIMIT = 50
MAX_TERM_LENGTH_LIMIT = 500
MAX_TOTAL_TERMS_LIMIT = 500


@dataclass(frozen=True)
class Hit:
    path: Path
    line: int
    text: str
    batch: str
    query: str
    candidate_field: str | None


@dataclass(frozen=True)
class DocumentRank:
    score: int
    reasons: tuple[str, ...]


def norm_path(path: Path) -> Path:
    return path.expanduser().resolve()


def ensure_authorized(root: Path, raw_paths: list[str]) -> list[Path]:
    if not raw_paths:
        raise SystemExit("error: --authorized-path is required")
    root = norm_path(root)
    authorized: list[Path] = []
    for raw in raw_paths:
        path = norm_path(Path(raw))
        if not path.exists():
            raise SystemExit(f"error: authorized path does not exist: {raw}")
        try:
            path.relative_to(root)
        except ValueError:
            raise SystemExit(f"error: authorized path is outside root: {raw}")
        authorized.append(path)
    return sorted(set(authorized))


def load_query_plan(args: argparse.Namespace) -> dict:
    if bool(args.query_plan_file) == bool(args.query_plan_json):
        raise SystemExit("error: provide exactly one of --query-plan-file or --query-plan-json")
    if args.query_plan_file:
        data = Path(args.query_plan_file).read_text(encoding="utf-8")
    else:
        data = args.query_plan_json
    try:
        plan = json.loads(data)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: invalid query plan JSON: {exc}") from exc
    validate_query_plan(
        plan,
        max_batches=args.max_batches,
        max_terms_per_batch=args.max_terms_per_batch,
        max_term_length=args.max_term_length,
        max_total_terms=args.max_total_terms,
    )
    return plan


def validate_limits(args: argparse.Namespace) -> None:
    if not (1 <= args.max_batches <= MAX_BATCHES_LIMIT):
        raise SystemExit(f"error: --max-batches must be 1..{MAX_BATCHES_LIMIT}")
    if not (1 <= args.max_terms_per_batch <= MAX_TERMS_PER_BATCH_LIMIT):
        raise SystemExit(f"error: --max-terms-per-batch must be 1..{MAX_TERMS_PER_BATCH_LIMIT}")
    if not (1 <= args.max_term_length <= MAX_TERM_LENGTH_LIMIT):
        raise SystemExit(f"error: --max-term-length must be 1..{MAX_TERM_LENGTH_LIMIT}")
    if not (1 <= args.max_total_terms <= MAX_TOTAL_TERMS_LIMIT):
        raise SystemExit(f"error: --max-total-terms must be 1..{MAX_TOTAL_TERMS_LIMIT}")
    if args.max_sections_per_document < 1:
        raise SystemExit("error: --max-sections-per-document must be >= 1")


def normalize_term(raw: str, batch_index: int) -> str:
    if not isinstance(raw, str):
        raise SystemExit(f"error: rg_batches[{batch_index}].terms contains a non-string term")
    term = raw.strip()
    if not term:
        raise SystemExit(f"error: rg_batches[{batch_index}].terms contains an empty term")
    if any(ch in term for ch in ("\n", "\r", "\t")) or any(ord(ch) < 32 for ch in term):
        raise SystemExit(f"error: rg_batches[{batch_index}].terms contains newline/control characters")
    return term


def validate_query_plan(
    plan: dict,
    *,
    max_batches: int,
    max_terms_per_batch: int,
    max_term_length: int,
    max_total_terms: int,
) -> None:
    if not isinstance(plan, dict):
        raise SystemExit("error: query plan must be a JSON object")
    batches = plan.get("rg_batches")
    if not isinstance(batches, list) or not batches:
        raise SystemExit("error: query plan must include non-empty rg_batches")
    if len(batches) > max_batches:
        raise SystemExit(f"error: query plan has {len(batches)} batches; max is {max_batches}")
    total_terms = 0
    for idx, batch in enumerate(batches):
        if not isinstance(batch, dict):
            raise SystemExit(f"error: rg_batches[{idx}] must be an object")
        name = batch.get("name")
        terms = batch.get("terms")
        if not isinstance(name, str) or not name.strip():
            raise SystemExit(f"error: rg_batches[{idx}].name must be a non-empty string")
        if not isinstance(terms, list) or not terms:
            raise SystemExit(f"error: rg_batches[{idx}].terms must be a non-empty list")
        if len(terms) > max_terms_per_batch:
            raise SystemExit(f"error: rg_batches[{idx}] has {len(terms)} terms; max is {max_terms_per_batch}")
        normalized_terms: list[str] = []
        seen_terms: set[str] = set()
        for term in terms:
            normalized = normalize_term(term, idx)
            if len(normalized) > max_term_length:
                raise SystemExit(f"error: rg_batches[{idx}] term exceeds max length {max_term_length}")
            if normalized not in seen_terms:
                normalized_terms.append(normalized)
                seen_terms.add(normalized)
        batch["terms"] = normalized_terms
        total_terms += len(normalized_terms)
        candidate_field = batch.get("candidate_field")
        if candidate_field is not None and candidate_field not in ALLOWED_CANDIDATE_FIELDS:
            allowed = ", ".join(sorted(ALLOWED_CANDIDATE_FIELDS))
            raise SystemExit(f"error: invalid candidate_field {candidate_field!r}; allowed: {allowed}")
    if total_terms > max_total_terms:
        raise SystemExit(f"error: query plan has {total_terms} total terms; max is {max_total_terms}")


def iter_markdown_files(paths: Iterable[Path]) -> Iterable[Path]:
    for base in paths:
        if base.is_file() and base.suffix.lower() == ".md":
            yield base
        elif base.is_dir():
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in {".git", ".kb_cache", "reports"}]
                for name in filenames:
                    if name.endswith(".md"):
                        yield Path(dirpath) / name


def run_rg(term: str, auth_path: Path) -> list[tuple[Path, int, str]]:
    cmd = ["rg", "--line-number", "--fixed-strings", "--glob", "*.md", term, str(auth_path)]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if proc.returncode not in (0, 1):
        return []
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) != 3:
            continue
        path_s, line_s, text = parts
        try:
            rows.append((Path(path_s).resolve(), int(line_s), text))
        except ValueError:
            continue
    return rows


def scan_python(term: str, auth_path: Path) -> list[tuple[Path, int, str]]:
    rows = []
    for path in iter_markdown_files([auth_path]):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for idx, line in enumerate(lines, 1):
            if term in line:
                rows.append((path.resolve(), idx, line))
    return rows


def search_batches(batches: list[dict], authorized: list[Path], max_hits: int) -> tuple[list[Hit], list[dict]]:
    use_rg = shutil.which("rg") is not None
    hits: list[Hit] = []
    queries: list[dict] = []
    seen = set()
    for batch in batches:
        batch_name = batch["name"].strip()
        candidate_field = batch.get("candidate_field")
        for raw_term in batch["terms"]:
            term = raw_term.strip()
            query_hits = 0
            for auth in authorized:
                rows = run_rg(term, auth) if use_rg else scan_python(term, auth)
                for path, line, text in rows:
                    key = (str(path), line, batch_name, term)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.append(Hit(path, line, text.strip(), batch_name, term, candidate_field))
                    query_hits += 1
                    if len(hits) >= max_hits:
                        break
                if len(hits) >= max_hits:
                    break
            queries.append({"batch": batch_name, "term": term, "engine": "rg" if use_rg else "python", "hits": query_hits})
            if len(hits) >= max_hits:
                return hits, queries
    return hits, queries


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def infer_record_kind(rel: str) -> str:
    lowered = rel.lower()
    name = Path(rel).name.lower()
    if rel.endswith("_current.md") or rel.endswith("overview_current.md"):
        return "current"
    if "项目总览" in rel or "总览" in name or "overview" in name:
        return "overview"
    if "修复" in rel or "/fixes/" in lowered:
        return "fix"
    if "决策" in rel or "/decisions/" in lowered:
        return "decision"
    if "验证" in rel or "/validation" in lowered:
        return "validation"
    if "coredump" in lowered or "incident" in lowered or "调查" in rel:
        return "incident"
    if "Current Maintenance Records" in rel or "维护记录" in rel:
        return "maintenance"
    return "page"


def line_context(path: Path, line_no: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "body"
    if not (1 <= line_no <= len(lines)):
        return "body"
    in_frontmatter = bool(lines and lines[0].strip() == "---")
    if in_frontmatter:
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                if line_no <= idx + 1:
                    return "frontmatter"
                break
    headings = heading_lines_outside_code(lines)
    current_heading = ""
    for heading_line, title in headings:
        if heading_line <= line_no:
            current_heading = title.lower()
        else:
            break
    line_text = lines[line_no - 1]
    if "retrieval summary" in current_heading or "retrieval anchors" in current_heading:
        return "retrieval_summary"
    if re.match(r"^#\s+", line_text):
        return "title"
    if re.search(r"source inventory|source list|sources|evidence_refs", current_heading, re.I):
        return "source_list"
    if in_frontmatter and line_no <= 120:
        return "frontmatter"
    return "body"


def score_document(rel: str, hits: list[Hit], root: Path) -> DocumentRank:
    kind = infer_record_kind(rel)
    score = 0
    reasons: list[str] = []
    kind_weight = {
        "fix": 45,
        "decision": 40,
        "validation": 38,
        "incident": 42,
        "maintenance": 18,
        "current": 12,
        "overview": 5,
        "page": 10,
    }.get(kind, 10)
    score += kind_weight
    reasons.append(f"record_kind:{kind}:{kind_weight}")
    batches = {hit.batch for hit in hits}
    terms = {hit.query for hit in hits}
    score += min(len(hits), 20)
    score += len(batches) * 3
    score += len(terms) * 2
    if "exact" in " ".join(batches).lower() or "title" in " ".join(batches).lower():
        score += 18
        reasons.append("exact_or_title_batch:+18")
    if any("symptom" in batch.lower() for batch in batches):
        score += 14
        reasons.append("symptom_batch:+14")
    if any("structure" in batch.lower() for batch in batches):
        score -= 8
        reasons.append("structure_batch:-8")

    contexts: dict[str, int] = {}
    for hit in hits:
        context = line_context(hit.path, hit.line)
        contexts[context] = contexts.get(context, 0) + 1
    if contexts.get("retrieval_summary"):
        score += 30
        reasons.append("retrieval_summary_hit:+30")
    if contexts.get("title"):
        score += 20
        reasons.append("title_hit:+20")
    if contexts.get("frontmatter") and not contexts.get("body"):
        score -= 14
        reasons.append("frontmatter_only:-14")
    elif contexts.get("frontmatter"):
        score -= 6
        reasons.append("frontmatter_hit:-6")
    if contexts.get("source_list"):
        score -= 10
        reasons.append("source_list_hit:-10")
    if kind in {"current", "overview"} and not contexts.get("body") and not contexts.get("retrieval_summary"):
        score -= 20
        reasons.append("aggregate_without_body_hit:-20")
    return DocumentRank(score=score, reasons=tuple(reasons))


def heading_lines_outside_code(lines: list[str]) -> list[tuple[int, str]]:
    headings = []
    in_fence = False
    fence_re = re.compile(r"^\s*(```|~~~)")
    heading_re = re.compile(r"^#{1,6}\s+")
    for idx, line in enumerate(lines, 1):
        if fence_re.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and heading_re.match(line):
            headings.append((idx, line.strip()))
    return headings


def section_for_hit(path: Path, hit_line: int, context_lines: int) -> dict:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, hit_line - context_lines)
    end = min(len(lines), hit_line + context_lines)
    headings = heading_lines_outside_code(lines)
    heading = None
    for line_no, title in reversed(headings):
        if line_no <= hit_line:
            start = line_no
            heading = title
            break
    for line_no, _ in headings:
        if line_no > hit_line:
            end = line_no - 1
            break
    return {
        "path": str(path),
        "heading": heading,
        "start_line": start,
        "end_line": end,
        "excerpt": "\n".join(lines[start - 1 : end]),
    }


def candidate_item(hit: Hit, section: dict, root: Path) -> dict:
    return {
        "path": relative_to_root(root, hit.path),
        "section": section.get("heading"),
        "start_line": section.get("start_line"),
        "end_line": section.get("end_line"),
        "matched_line": hit.line,
        "retrieval_signal": hit.batch,
        "matched_term": hit.query,
    }


def document_summaries(hits: list[Hit], root: Path) -> dict[str, dict]:
    docs = {}
    hits_by_doc: dict[str, list[Hit]] = {}
    for hit in hits:
        rel = relative_to_root(root, hit.path)
        docs.setdefault(rel, {"path": rel, "hit_count": 0, "matched_batches": [], "matched_terms": []})
        hits_by_doc.setdefault(rel, []).append(hit)
        docs[rel]["hit_count"] += 1
        if hit.batch not in docs[rel]["matched_batches"]:
            docs[rel]["matched_batches"].append(hit.batch)
        if hit.query not in docs[rel]["matched_terms"]:
            docs[rel]["matched_terms"].append(hit.query)
    for rel, doc_hits in hits_by_doc.items():
        rank = score_document(rel, doc_hits, root)
        docs[rel]["rank_score"] = rank.score
        docs[rel]["rank_reasons"] = list(rank.reasons)
    return docs


def diverse_section_hits(hits: list[Hit], max_sections: int, max_per_doc: int) -> list[Hit]:
    if max_sections <= 0:
        return []
    by_doc: dict[Path, list[Hit]] = {}
    for hit in hits:
        by_doc.setdefault(hit.path, []).append(hit)
    selected: list[Hit] = []
    selected_keys: set[tuple[str, int, str, str]] = set()
    per_doc_counts: dict[Path, int] = {path: 0 for path in by_doc}

    def add(hit: Hit) -> bool:
        if len(selected) >= max_sections:
            return False
        if per_doc_counts[hit.path] >= max_per_doc:
            return False
        key = (str(hit.path), hit.line, hit.batch, hit.query)
        if key in selected_keys:
            return False
        selected.append(hit)
        selected_keys.add(key)
        per_doc_counts[hit.path] += 1
        return True

    for doc_hits in by_doc.values():
        add(doc_hits[0])
        if len(selected) >= max_sections:
            return selected
    for hit in hits:
        add(hit)
        if len(selected) >= max_sections:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Knowledge base root")
    parser.add_argument("--authorized-path", action="append", required=True, help="Authorized path; repeatable")
    parser.add_argument("--query-plan-file", help="Path to agent-authored query plan JSON")
    parser.add_argument("--query-plan-json", help="Agent-authored query plan JSON string")
    parser.add_argument("--max-hits", type=int, default=80)
    parser.add_argument("--max-sections", type=int, default=20)
    parser.add_argument("--max-sections-per-document", type=int, default=2)
    parser.add_argument("--context-lines", type=int, default=8)
    parser.add_argument("--max-batches", type=int, default=12)
    parser.add_argument("--max-terms-per-batch", type=int, default=12)
    parser.add_argument("--max-term-length", type=int, default=120)
    parser.add_argument("--max-total-terms", type=int, default=80)
    args = parser.parse_args()

    validate_limits(args)
    root = norm_path(Path(args.root))
    authorized = ensure_authorized(root, args.authorized_path)
    query_plan = load_query_plan(args)
    hits, queries = search_batches(query_plan["rg_batches"], authorized, args.max_hits)

    docs = document_summaries(hits, root)
    sections = []
    candidate_buckets = {
        "candidate_decisions": [],
        "candidate_constraints": [],
        "candidate_fixes": [],
        "candidate_supersessions": [],
    }
    for hit in diverse_section_hits(hits, args.max_sections, args.max_sections_per_document):
        rel = relative_to_root(root, hit.path)
        section = section_for_hit(hit.path, hit.line, args.context_lines)
        section["path"] = rel
        section["matched_line"] = hit.line
        section["matched_text"] = hit.text
        section["matched_batch"] = hit.batch
        section["matched_term"] = hit.query
        sections.append(section)
        if hit.candidate_field:
            candidate_buckets[hit.candidate_field].append(candidate_item(hit, section, root))

    limitations = []
    if not hits:
        limitations.append("no_match_within_authorized_scope")
    if len(hits) >= args.max_hits:
        limitations.append(f"hit_limit_reached:{args.max_hits}")
    if len(sections) < len(hits):
        limitations.append(f"section_read_limit:{args.max_sections}")
    if len(sections) < len({hit.path for hit in hits}):
        limitations.append("not_all_candidate_documents_read_due_to_section_limit")
    limitations.append("query_understanding_done_by_agent_not_script")
    limitations.append("hashes_not_computed_by_retriever")

    package = {
        "retrieval_package_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authorized_paths": [relative_to_root(root, p) for p in authorized],
        "authorized_paths_required": True,
        "change_or_analysis_intent": query_plan.get("change_or_analysis_intent"),
        "optional_context": query_plan.get("optional_context", []),
        "query_plan": {
            "facets": query_plan.get("facets", []),
            "terms": query_plan.get("terms", []),
            "rg_batches": query_plan["rg_batches"],
        },
        "queries_executed": queries,
        "candidate_documents": sorted(docs.values(), key=lambda d: (-d.get("rank_score", 0), -d["hit_count"], d["path"])),
        "source_sections_read": sections,
        **candidate_buckets,
        "unresolved_ambiguities": query_plan.get("unresolved_ambiguities", []),
        "recall_limitations": limitations,
    }
    print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
