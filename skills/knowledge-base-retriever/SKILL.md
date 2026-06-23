---
name: knowledge-base-retriever
description: Lightweight read-only retrieval for Markdown knowledge bases. Use when Codex needs to perform agent-led Query Planning, execute deterministic authorized-path-only rg batches, extract matching Markdown sections, and format a candidate retrieval_package for analysis or for knowledge-base-structure-builder preflight; especially useful before design, debugging, or high-risk knowledge-base writes that may depend on historical fixes, decisions, constraints, supersession records, or validation notes.
---

# Knowledge Base Retriever

Use this skill for read-only historical context retrieval. The hard part is semantic query planning; the agent does that. The bundled script only executes a structured query plan deterministically.

This skill is not a workflow engine, state machine, research loop, vector search system, NLP system, or knowledge source.

## Division Of Responsibility

Agent responsibilities:

- Read the user's question, optional context, and available project/module entry points.
- Produce a structured `query_plan` with facets, terms, and `rg_batches`.
- Decide Chinese terms, aliases, old names, symptom groupings, and history-type searches.
- Decide which batch may indicate `candidate_fixes`, `candidate_decisions`, `candidate_constraints`, or `candidate_supersessions`.
- Interpret the returned package by reading source sections; do not treat candidate fields as facts.

Script responsibilities:

- Validate `authorized_paths`.
- Validate query plan size and reject unsafe terms.
- Execute exactly the `rg_batches` supplied by the agent.
- Merge hits by Markdown file and line.
- Extract containing Markdown sections using Markdown headings outside fenced code blocks.
- Read sections with simple document diversity so one heavily matching file does not consume all section quota.
- Format a versioned `retrieval_package`.
- Avoid query understanding, synonym expansion, Chinese segmentation, symptom classification, and default hash calculation.

## Required Rules

- `authorized_paths` are required. Do not search when they are missing.
- Search, directory traversal, link expansion, and section reads must stay within `authorized_paths`.
- Do not scan the whole vault and filter afterward.
- Report no matches as `no_match_within_authorized_scope`, not as proof that history does not exist.
- Read Markdown source sections for candidate current, fix, decision, validation, supersession, and Fix Registry hits.
- Treat `protected`, `guarded`, and `critical` as ordinary search terms or candidate signals only. They are Builder/Schema/AGENTS governance concepts, not retriever prerequisites.
- Do not compute hashes by default. Carry existing hashes only when an input index or caller provides them. Builder owns hash checks needed for write gates.
- Do not write, move, delete, promote, resolve supersession conflicts, or raise evidence levels.

## Agent Query Planning

Before running the script, write a structured plan. Include only terms you can justify from user text, optional context, paths/headings you read, or explicit agent inference. Mark the origin.

Use these facets as a checklist:

- `target_object`: project, module, component, document, path, API, config, symbol
- `operation_intent`: create, modify, replace, delete, migrate, fix, rollback
- `symptom`: error text, failure mode, unexpected behavior
- `constraint`: must keep, must avoid, compatibility, validation boundary
- `name_variants`: Chinese/English, abbreviation, old/new name, code symbol
- `history_type`: current, fix, decision, validation, incident, superseded
- `structure_relation`: overview, current, same project/module, links
- `time_state`: current, historical, superseded, unverified

Recommended `rg_batches`:

- `exact_anchors`: paths, symbols, quoted text, config keys
- `name_variants`: aliases, old/new names, Chinese/English variants
- `structure_anchors`: overview, current, index, 总览, 索引
- `history_anchors`: fix, 修复, decision, 决策, validation, 验证, incident, superseded, supersession
- `fallback_terms`: important remaining terms from the agent plan

Multi-round retrieval is allowed only as repeated agent-authored `rg_batches` followed by merge/read. Do not create an automatic loop.

## Query Plan Schema

```json
{
  "change_or_analysis_intent": "driver face 后排误绑定修复历史和约束",
  "optional_context": ["DMS Tracking", "source/utils/track.cpp"],
  "facets": [
    {"name": "target_object", "values": ["DMS", "Tracking", "driver face"], "origin": "user/context"}
  ],
  "terms": [
    {"term": "后排误绑定", "facet": "symptom", "origin": "user"},
    {"term": "driver face", "facet": "target_object", "origin": "context"}
  ],
  "rg_batches": [
    {
      "name": "exact_anchors",
      "terms": ["driver face", "source/utils/track.cpp"],
      "candidate_field": "candidate_constraints"
    },
    {
      "name": "fix_history",
      "terms": ["后排误绑定", "修复", "闭环"],
      "candidate_field": "candidate_fixes"
    }
  ],
  "unresolved_ambiguities": ["driver face may appear as 主驾 face or selected driver face"]
}
```

`candidate_field` is optional and must be one of:

- `candidate_decisions`
- `candidate_constraints`
- `candidate_fixes`
- `candidate_supersessions`

If omitted, the script records source sections and candidate documents but does not classify the hit into a candidate bucket.

Plan limits enforced by the script defaults:

- max batches: 12
- max terms per batch: 12
- max total terms: 80
- max term length: 120 characters
- no newline or control characters inside terms
- duplicate terms inside a batch are deduplicated before execution

## Helper Script

Use `scripts/kb_retrieve.py` to execute a completed plan:

```bash
python3 /mnt/d/codex-capability-registry/skills/knowledge-base-retriever/scripts/kb_retrieve.py \
  --root /path/to/vault \
  --authorized-path /path/to/vault/02_Projects/DMS/04_Tracking \
  --query-plan-file /tmp/query_plan.json
```

The script prints JSON. It requires `--authorized-path`; accepts multiple authorized paths; uses `rg` when available; and falls back to bounded Python text scanning only inside authorized paths.

Useful execution controls:

- `--max-hits`: cap total raw hits.
- `--max-sections`: cap source sections read.
- `--max-sections-per-document`: cap sections per candidate document; default is 2.
- `--max-batches`, `--max-terms-per-batch`, `--max-total-terms`, `--max-term-length`: cap oversized plans.

The script preserves hits inside code blocks, but code-block lines that look like headings do not define section boundaries.

## Package Schema

```yaml
retrieval_package_version: 1
generated_at:
authorized_paths: []
authorized_paths_required: true
change_or_analysis_intent:
optional_context:
query_plan:
  facets: []
  terms: []
  rg_batches: []
queries_executed: []
candidate_documents: []
source_sections_read: []
candidate_decisions: []
candidate_constraints: []
candidate_fixes: []
candidate_supersessions: []
unresolved_ambiguities: []
recall_limitations: []
```

For each candidate item, cite source path and section or line range. Include priority labels only as retrieval priority, not as truth judgments.

## Working With Builder

When `knowledge-base-structure-builder` asks for a package, ensure the package states:

- which authorized paths were searched
- which source sections were read
- which candidate constraints/fixes/decisions/supersessions were found
- what recall limitations remain

Builder decides write risk, hash checks, gate decisions, protected/guarded semantics, and whether manual review is required.
