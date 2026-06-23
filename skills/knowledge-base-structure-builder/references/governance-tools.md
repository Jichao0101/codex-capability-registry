# Knowledge-base governance tools

Use the skill-owned CLI from the skill root:

```bash
python3 scripts/kb.py metadata --root <vault> [--authorized-path <path>]
python3 scripts/kb.py lint --root <vault> [--authorized-path <path>]
python3 scripts/kb.py trace-index --root <vault> --authorized-path <path>
python3 scripts/kb.py fix-registry --root <vault> --scope 02_Projects/<project-or-subproject> --authorized-path <path>
python3 scripts/kb.py retrieval-package-check --root <vault> --package <retrieval_package.json> --authorized-path <path>
python3 scripts/kb.py preflight --root <vault> --target <relative-path> \
  --intent modify --authorized-path <vault> [--forbidden-path <path>] \
  --policy-file <vault>/AGENTS.md [--retrieval-package <retrieval_package.json>] [--query "terms"] [--trace-index <index.json>]
python3 scripts/kb.py hash-check --root <vault> --report <report.json>
```

## Ownership

- `AGENTS.md` is the repository policy authority.
- `SKILL.md` and references define workflow.
- `rules/` contains version-bound executable decisions.
- `scripts/kb.py` executes those rules without modifying knowledge Markdown.
- `<vault>/reports/kb/` contains run reports. Lint reports are end-of-run artifacts; keep the latest report for the current Builder call and remove stale sibling lint reports.
- `<vault>/.kb_cache/` contains disposable metadata and trace indexes.

## Write workflow

1. Read the vault entry and relevant project/module overview.
2. Run `trace-index` when the cache is missing or stale. Pass authorized paths so the index is not built by scanning the whole vault first.
3. Run `preflight` before the first target modification. Pass every authorized path explicitly.
4. If the decision is `blocked`, do not write. Resolve the listed blocker and rerun.
5. If the decision is `manual_review`, create a proposal or patch draft and obtain explicit review before applying it.
6. If the decision is `allow`, apply only the described change intent.
7. Run `hash-check` immediately before writing; rerun preflight if any hash changed.
8. Run `lint` after the write, prune stale lint reports, and sync required entries.

`free_update` never bypasses preflight. Index hits are recall candidates; the preflight report must contain verifiable source-document reads for strong and protected matches.

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

## Fix Registry

Use `fix-registry` as a project/subproject-scoped recall index:

```bash
python3 scripts/kb.py fix-registry --root <vault> --scope 02_Projects/DMS/04_Tracking
```

The command writes a derived JSON index under `<vault>/.kb_cache/fix-registry/` unless `--output` is provided. It only derives entries from source fix Markdown under the requested scope. Manual edits may add anchors or correct summaries in the source fix document, then the registry should be regenerated; do not create fact entries directly in the registry. Registry entries use lightweight fingerprints by default; strong hashes are left to preflight/hash-check evidence paths.
