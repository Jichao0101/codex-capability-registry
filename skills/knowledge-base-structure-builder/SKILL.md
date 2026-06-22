---
name: knowledge-base-structure-builder
description: Build, migrate, maintain, lint, and preflight structured Markdown knowledge bases. Use when initializing or restructuring a knowledge base, maintaining overview/index files and project current groups, deciding candidate/source/project/knowledge placement, auditing metadata and links, building a traceability index, or preventing guarded facts, fixes, constraints, and supersession history from being silently overwritten.
---

# Knowledge Base Structure Builder

Use this skill for knowledge-base structure work, not for ordinary note writing. It supports three modes:

- **Bootstrap**: create a structured knowledge base from an empty or nearly empty directory.
- **Migration**: classify and structure an existing unformatted note collection.
- **Maintenance**: update an already structured knowledge base, including overview sync and current document groups.

## First Step: Diagnose Mode

Before editing, inspect only authorized paths and answer:

1. Is there a top-level entry such as `README.md`?
2. Are standard zones present: `01_Knowledge`, `02_Projects`, `03_Inbox`, `04_Sources`, `90_Archive`?
3. Are there overview/index files for knowledge, projects, inbox, sources, and structure audit?
4. Are project modules using `overview_current` or module indexes?
5. Are there many orphan Markdown files, external-source notes, or project-bound records?

Select one mode:

| Condition | Mode | Reference |
|---|---|---|
| No standard zones or no entry files | Bootstrap | `references/bootstrap.md` |
| Existing notes but no reliable structure | Migration | `references/migration.md` |
| Standard zones and entries exist | Maintenance | `references/maintenance.md` |
| Project current group is requested or implied | Current lifecycle | `references/current-lifecycle.md` |

## Core Rules

- Read entry files first when they exist: `README.md`, knowledge overview, project overview, module index, `overview_current`, inbox index, source index, structure audit.
- Do not directly start from historical records, run artifacts, baseline files, or random notes unless the user asks for historical trace.
- When using template assets, replace all placeholders such as `YYYY-MM-DD`, `TBD`, and English default names that do not match the local naming convention before considering the write complete.
- External information must first go to candidate/source zones, not formal knowledge.
- Formal knowledge needs at least: summary, source, scope, risks/boundaries, status.
- Project-bound material stays in project space until abstracted and reviewed.
- For current groups, never set `single_pass_recoverable: true` without independent recoverability verification.
- Any write that changes entries, scope, status, current fact source, placement, or recoverability must sync the relevant overview/index/audit file.
- In Migration mode, structured placement under the standard zones is the primary output. Keeping `raw/` is only a traceability measure and does not replace arranging documents in the new structure.

## Governance Workflow

Treat the target vault's `AGENTS.md` as policy authority. Keep this skill's workflow, `rules/`, and `scripts/` version-bound; do not create a second repo-level implementation unless an independent CI, CLI, agent, or skill consumer exists.

Before any knowledge-base write:

1. Read authorized entries and the relevant project/module overview.
2. Build or refresh the trace index with `python3 scripts/kb.py trace-index --root <vault>`.
3. Run `python3 scripts/kb.py preflight` for each target; pass the policy file plus explicit `--authorized-path` and policy-derived `--forbidden-path` values.
4. For `blocked`, do not write. For `manual_review`, prepare a proposal or patch draft and obtain explicit review. For `allow`, apply only the declared intent.
5. Run `hash-check` immediately before writing; rerun preflight when hashes changed.
6. After writing, run read-only `lint` and perform required overview/index sync.

Read `references/governance-tools.md` before using lint, trace, or gate commands. Machine decisions live in `rules/`; do not infer a more permissive result than the CLI. Reports under `<vault>/reports/kb/` and caches under `<vault>/.kb_cache/` are derived artifacts, not fact sources.

## Placement Quick Guide

- `01_Knowledge/`: reviewed reusable knowledge with clear scope and risks.
- `02_Projects/`: project-specific requirements, designs, experiments, implementation notes, decisions, current groups.
- `03_Inbox/`: unreviewed candidates, temporary excerpts, unclear placement.
- `04_Sources/`: original source notes, evidence cards, external reading notes.
- `90_Archive/`: frozen, obsolete, or historical material.

For detailed placement and metadata, read `references/placement-rules.md` and `references/metadata-schema.md`.

## Output Checklist

End knowledge-base write tasks with:

- `allowed_paths`
- `files_read`
- `files_written`
- `candidate_created`
- `source_notes_created`
- `promoted_to_knowledge`
- `missing_authorization`
- `promotion_blockers`
- `unresolved_items`

## Self-Check

Before finishing, run a lightweight structure check:

- standard zones and entry files exist for the selected mode
- no unresolved template placeholders remain except intentional `TBD` entries listed in unresolved items
- indexes/overviews mention files created, moved, archived, or status-changed
- migration work places documents under the new structure and preserves raw traceability until the user explicitly approves cleanup
- current groups keep `single_pass_recoverable: false` unless recoverability verification was independently performed
