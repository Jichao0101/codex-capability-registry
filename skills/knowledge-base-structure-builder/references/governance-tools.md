# Knowledge-base governance tools

Use the skill-owned CLI from the skill root:

```bash
python3 scripts/kb.py metadata --root <vault>
python3 scripts/kb.py lint --root <vault>
python3 scripts/kb.py trace-index --root <vault>
python3 scripts/kb.py preflight --root <vault> --target <relative-path> \
  --intent modify --authorized-path <vault> [--forbidden-path <path>] \
  --policy-file <vault>/AGENTS.md --query "terms" [--trace-index <index.json>]
python3 scripts/kb.py hash-check --root <vault> --report <report.json>
```

## Ownership

- `AGENTS.md` is the repository policy authority.
- `SKILL.md` and references define workflow.
- `rules/` contains version-bound executable decisions.
- `scripts/kb.py` executes those rules without modifying knowledge Markdown.
- `<vault>/reports/kb/` contains run reports.
- `<vault>/.kb_cache/` contains disposable metadata and trace indexes.

## Write workflow

1. Read the vault entry and relevant project/module overview.
2. Run `trace-index` when the cache is missing or stale.
3. Run `preflight` before the first target modification. Pass every authorized path explicitly.
4. If the decision is `blocked`, do not write. Resolve the listed blocker and rerun.
5. If the decision is `manual_review`, create a proposal or patch draft and obtain explicit review before applying it.
6. If the decision is `allow`, apply only the described change intent.
7. Run `hash-check` immediately before writing; rerun preflight if any hash changed.
8. Run `lint` after the write and sync required entries.

`free_update` never bypasses preflight. Index hits are recall candidates; the preflight report must contain verifiable source-document reads for strong and protected matches.

## Preflight intent

- `create`: target does not exist; its parent must be authorized.
- `append`: add content without changing existing bytes.
- `modify`: rewrite existing content.
- `delete`: remove an existing document.
- `supersede`: replace a conclusion and provide `--supersedes`, matching `--reciprocal-supersession`, `--supersession-reason`, and at least one `--evidence-ref`.

For `modify`, add `--replaces-conclusion` when the change replaces a prior conclusion; the same explicit supersession requirements then apply. The workflow must translate authorized and forbidden paths from the repository policy into CLI arguments. The report records the policy file hash but does not attempt to treat prose parsing as policy authority.

Reports and caches are derived artifacts, not fact sources. A project record may cite an immutable report path and hash explicitly when the report is required as validation evidence.
