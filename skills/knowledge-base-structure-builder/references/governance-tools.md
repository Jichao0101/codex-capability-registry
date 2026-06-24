# Knowledge-base governance tools

Use the skill-owned CLI from the skill root:

```bash
python3 scripts/kb.py metadata --root <vault> [--authorized-path <path>]
python3 scripts/kb.py lint --root <vault> [--authorized-path <path>]
python3 scripts/kb.py trace-index --root <vault> --authorized-path <path>
python3 scripts/kb.py retrieval-summary-proposals --root <vault> --authorized-path <path>
python3 scripts/kb.py retrieval-package-check --root <vault> --package <retrieval_package.json> --authorized-path <path>
python3 scripts/kb.py minimal-apply-check --root <vault> --target <relative-path> \
  --intent append --change-class retrieval_summary_append --authorized-path <path> \
  [--user-confirmed] [--batch-confirmation-id <id>]
python3 scripts/kb.py preflight --root <vault> --target <relative-path> \
  --intent modify --authorized-path <vault> [--forbidden-path <path>] \
  --policy-file <vault>/AGENTS.md --change-class <class> \
  [--retrieval-package <retrieval_package.json>] [--query "terms"] [--trace-index <index.json>]
python3 scripts/kb.py hash-check --root <vault> --report <report.json>
```

## Ownership

- `AGENTS.md` is the repository policy authority.
- `SKILL.md` and references define workflow.
- `rules/` contains version-bound executable decisions.
- `scripts/kb.py` executes those rules without modifying knowledge Markdown.
- `<vault>/reports/kb/` contains run reports. Default timestamped reports keep the latest three files per report kind and prune older sibling reports.
- `<vault>/.kb_cache/` contains disposable metadata and trace indexes.

## Gate granularity

Gate selection is determined by change class and write intent, not by whether Retriever ran.

Proposal-only commands do not edit Markdown and do not require trace-index, preflight, or hash-check. This includes report generation for retrieval summary proposals.

Low-risk non-fact append/create operations use `minimal-apply-check` immediately before editing Markdown. This check only validates policy readability, explicit authorized scope, target readability/creatability, forbidden paths, target hash snapshot, whether the change class must be escalated to full preflight, and whether current/guarded targets need user confirmation. It does not build trace-index, read strong records, or scan source documents. A low-risk write is not blocked merely because no historical retrieval was run.

Lightweight append/create operations to current or guarded targets may use batch-level user confirmation. If `minimal-apply-check` returns `requires_user_confirmation`, obtain confirmation for the exact target set and declared low-risk change class, then rerun with `--user-confirmed` and optionally `--batch-confirmation-id`.

Full preflight is whitelist-only for high-risk change classes. Use `trace-index` + `preflight` + `hash-check` for:

- current document group updates
- delete or move
- formal knowledge promotion
- external source promotion
- supersession
- conclusion replacement
- protected rewrites
- metadata/status changes
- evidence-level changes
- explicitly critical-target operations

If `minimal-apply-check` returns `requires_full_preflight`, switch to the full workflow.

## Minimal apply workflow

1. Read the target and enough local context to ensure the proposed append is supported by that document.
2. Run `minimal-apply-check` before editing.
3. If the decision is `requires_user_confirmation`, obtain batch-level user confirmation for the target set and rerun with `--user-confirmed`.
4. If the decision is `allow`, apply only the checked append.
5. Run `lint` after the write; default report generation prunes older sibling reports beyond the latest three.

## Full preflight workflow

1. Read the vault entry and relevant project/module overview.
2. Run `trace-index` when the cache is missing or stale. Pass authorized paths so the index is not built by scanning the whole vault first.
3. Run `preflight` before the first target modification. Pass every authorized path explicitly.
4. If the decision is `blocked`, do not write. Resolve the listed blocker and rerun.
5. If the decision is `manual_review`, create a proposal or patch draft and obtain explicit review before applying it.
6. If the decision is `allow`, apply only the described change intent.
7. Run `hash-check` immediately before writing; rerun preflight if any hash changed.
8. Run `lint` after the write; default report generation prunes older sibling reports beyond the latest three, then sync required entries.

`free_update` never bypasses the applicable gate. Index hits are recall candidates; no retrieval hit is not safety proof. When full preflight is required, the preflight report must contain verifiable source-document reads for strong and protected matches. If a high-risk change has insufficient retrieval/source evidence, treat the result as `manual_review` or proposal-only; do not silently apply the write.

## Preflight intent

- `create`: target does not exist; its parent must be authorized.
- `append`: add content without changing existing bytes.
- `modify`: rewrite existing content.
- `delete`: remove an existing document.
- `supersede`: replace a conclusion and provide `--supersedes`, matching `--reciprocal-supersession`, `--supersession-reason`, and at least one `--evidence-ref`.

For `modify`, add `--replaces-conclusion` when the change replaces a prior conclusion; the same explicit supersession requirements then apply. The workflow must translate authorized and forbidden paths from the repository policy into CLI arguments. The report records the policy file hash but does not attempt to treat prose parsing as policy authority.

Reports and caches are derived artifacts, not fact sources. A project record may cite an immutable report path and hash explicitly when the report is required as validation evidence.

## Retriever Package

Builder may consume a Retriever `retrieval_package` as write-side evidence, but Retriever does not choose the write path. Builder checks only package authorization coverage, source sections read, candidate fields, and recall limitations. Cited source sections are re-read through Builder preflight under the target vault policy.

## Retrieval Summary Proposals

Use `retrieval-summary-proposals` to generate report-only patch proposals for fix, decision, validation, and incident records that lack a short `Retrieval Summary` or `Retrieval Anchors` section:

```bash
python3 scripts/kb.py retrieval-summary-proposals --root <vault> --authorized-path <vault>/02_Projects/DMS/04_Tracking
```

The command writes a derived report under `<vault>/reports/kb/retrieval-summary-proposals/` unless `--output` is provided. It never edits Markdown directly and does not require trace-index, preflight, or hash-check. Apply the approved patch only after `minimal-apply-check` returns `allow`; if it returns `requires_user_confirmation`, obtain batch-level confirmation and rerun; if the change class requires full preflight, follow the full workflow instead.
