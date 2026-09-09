# Governance tools

`AGENTS.md` owns policy; `rules/` and `scripts/kb.py` implement mechanical checks. The CLI never edits knowledge Markdown. Its report is not proof that a model understood evidence or that the repository permits an operation.

## Local and structural changes

Read the target and review a proposed diff. For a local modification, save complete proposed content outside the fact source and run:

```bash
python3 scripts/kb.py minimal-apply-check --root <vault> --target <relative-path> \
  --intent modify --change-class editorial_edit --proposed-file <draft-file> \
  --authorized-path <authorized-path>
```

`local_fact_update` covers additions supported by direct evidence that preserve established conclusions and protected facts. `retrieval_summary_append` remains supported. Non-fact appends may use `--intent append`; provide `--proposed-file` whenever checking an exact draft. Local `modify` requires it. The report binds the proposed content hash and target snapshot. Apply only that content after confirming the target has not changed.

The check detects frontmatter changes, some constraint/recoverability markers and append violations. This is conservative escalation, not a semantic classifier: changing an unmarked fact still requires the agent to reclassify the diff. `allow` does not waive that responsibility. Append-only documents cannot use local modify; append corrections instead.

Use `structure_relocate`, `archive_move` or `index_path_sync` for content-preserving structural operations. Directory targets are supported. Check destination authorization separately, review the move manifest and path links, and escalate if placement changes protection/status or the current fact source. Do not use a structure class to delete facts or rewrite append-only text.

A `requires_full_preflight` result switches to the next section; `blocked` prohibits applying. Hash checking is useful for concurrent edits, long-running work or protected rewrites; re-read/recheck stale inputs rather than asking for permission to use them.

## Semantic changes

Prepare a compact evidence assessment for consequential changes. This is the agent's reasoning with checkable citations, not a new fact document:

```json
{
  "claims": [
    {"change": "Describe the changed claim", "path": "02_Projects/Demo/validation.md", "quote": "Exact supporting text", "reason": "Why this text supports this change"}
  ],
  "constraints": [
    {"path": "02_Projects/Demo/decision.md", "quote": "Exact relevant constraint", "disposition": "preserved", "reason": "How the proposed change preserves it"}
  ],
  "limitations": []
}
```

`constraints` may be empty after an appropriate scoped search; document the search scope and stopping rationale in the task record or response. Dispositions are `preserved`, `irrelevant` or `conflict`. `limitations` lists unresolved gaps affecting this change; disclose irrelevant coverage limits separately. Every changed claim needs support, and every relevant counterexample/constraint needs a disposition. Do not pad citations merely to satisfy the schema.

```bash
python3 scripts/kb.py preflight --root <vault> --target <relative-path> \
  --intent modify --change-class protected_rewrite \
  --authorized-path <authorized-path> --policy-file <vault>/AGENTS.md \
  --evidence-assessment <assessment.json> --change-summary <summary>
```

Original evidence must be within authorized scope and outside forbidden paths. The CLI checks quotes, paths and hashes; the agent judges entailment, coverage and conflict resolution. Invalid citations block. Missing assessment or relevant gaps require review for high-risk changes; reading any one file no longer counts as sufficient evidence.

Direct evidence assessment does not require a trace index. Use `--query`, `--trace-index` or `--retrieval-package` when recall assistance is useful. Supersession and conclusion replacement still use trace scanning to detect cycles. Trace hits are review candidates, not actual conflicts. When candidates are present, record their dispositions in the assessment; unresolved candidates require review. Matching a keyword alone must not be reported as a proven semantic conflict.

Change classes requiring full preflight: `semantic_fact_update` (consequential unprotected facts), `current_group_update` (structural/fact-source changes), `formal_knowledge_promotion`, `external_source_promotion`, `supersession`, `conclusion_replacement`, `protected_rewrite`, `metadata_status_change`, `evidence_level_change`, `semantic_delete`, `protected_delete`. Labels alone do not select these classes.

For replacement use `--replaces-conclusion`; for supersession use `--intent supersede`. Supply `--supersedes`, matching `--reciprocal-supersession`, `--supersession-reason` and `--evidence-ref`. Review actual reciprocal records before applying; CLI arguments record intended updates rather than proving they have occurred.

- `blocked`: repair the listed issue and rerun; no approval bypass.
- `manual_review`: prepare a concrete patch, evidence and the decision needed. Reuse explicit review already covering those inputs; otherwise obtain it. Approval for implementation does not by itself resolve a newly discovered contradiction.
- `allow`: mechanical checks passed. Apply only within policy, semantic assessment and declared intent.

## Supporting commands

```bash
python3 scripts/kb.py trace-index --root <vault> --authorized-path <path>
python3 scripts/kb.py lint --root <vault> --authorized-path <path>
python3 scripts/kb.py metadata --root <vault> --authorized-path <path>
python3 scripts/kb.py hash-check --root <vault> --report <preflight.json>
python3 scripts/kb.py retrieval-package-check --root <vault> --package <package.json> --authorized-path <path>
python3 scripts/kb.py retrieval-summary-proposals --root <vault> --authorized-path <path>
```

Proposal generation requires no apply gate. A retrieval package supplies recall hints and source sections; it does not decide placement or establish semantic sufficiency. Explicit stale trace indexes fail closed; refresh them or use current direct evidence when no trace is needed.

Reports under `reports/kb/` and caches under `.kb_cache/` are derived. Default reports retain the latest three per kind; use an explicit immutable output path and cite its hash when a project needs durable validation evidence. Do not delete reports cited as evidence. Scope lint to changed structure and dependencies, then sync affected entries. `hash-check` checks full preflight snapshots; local draft hashes are recorded by minimal checks and must be compared before apply.
