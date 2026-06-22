## Knowledge Base Rules

### Zones

- `01_Knowledge/`: reviewed reusable knowledge.
- `02_Projects/`: project-bound work, current docs, experiments, records.
- `03_Inbox/`: unreviewed candidates.
- `04_Sources/`: external or original source evidence.
- `90_Archive/`: frozen or obsolete material.

### Read Order

Read entry files first when present:

1. `README.md`
2. knowledge overview
3. project overview
4. module index or `overview_current`
5. detailed records and source notes

### Write Sync

If a write changes entry, status, scope, placement, current fact source, or recoverability, update the relevant overview/index/audit file.

External information must not go directly into formal knowledge.

### Write Gate Hard Policy

- Markdown is the fact source. Indexes, caches, lint reports, and preflight reports are rebuildable derived artifacts.
- Run preflight before the first fact-file create, modify, move, delete, or supersession operation. Post-write lint does not replace preflight.
- Do not write when the decision is `blocked`. Require explicit user or authorized-reviewer confirmation for `manual_review`. Treat `allow` as scoped only to the current target, intent, and input snapshot.
- Automation must not directly rewrite verified, guarded, critical, or active-constraint content. It may generate proposals, patch drafts, candidate summaries, or validation plans.
- Preserve append-only history. A replacement conclusion requires explicit bidirectional supersession, reason, and evidence.
- A trace index only recalls candidates. Read matched strong or protected Markdown sources before continuing.
- Fail closed when authorization, source reads, rules, indexes, hashes, or supersession state cannot be verified.
- Automation must not promote formal knowledge, resolve conflicts, delete history, raise evidence level, or assert single-pass recoverability.
