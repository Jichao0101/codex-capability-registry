# Maintenance Mode

Use Maintenance mode when the knowledge base already has zones and entry files.

## Read Order

Start at the nearest relevant entry that establishes the current fact source. Reuse fresh context already read in this task; do not require a top-down traversal for every edit. Expand to source records and history according to changed claims, dependencies and discovered constraints.

## Write-After-Sync Rules

Update the relevant entry/index/audit when a write:

- creates a new knowledge item
- creates a new project or module
- creates or changes a current group
- changes status, scope, or recoverability
- adds a candidate
- adds a source card
- moves, renames, deletes, or archives a file

You may skip overview sync for a small body-only edit that does not change entry, status, scope, placement, or truth source. State that reason in the final answer.

## Structure Audit

Maintain a current audit file such as:

- `02_Projects/Knowledge-Base/知识库结构审计_current.md`
- or `02_Projects/Knowledge-Base/structure-audit-current.md`

The audit should track:

- zone structure state
- formal knowledge metadata coverage
- project current coverage
- unresolved migration or recoverability items
- total overview contentization policy

## Formal Knowledge Maintenance

For `01_Knowledge`, prefer:

- topic overview
- concise frontmatter
- source/scope/risk metadata
- links to candidate/source records

Do not use project current five-file groups for general formal knowledge.

## Project Maintenance

For `02_Projects`, use:

- project overview
- module index for lightweight modules
- current document groups for long-lived modules
- `Current Maintenance Records/` for creation, patch, review, verification, and writeback records
