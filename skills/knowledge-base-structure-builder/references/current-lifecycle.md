# Current Lifecycle

Use this reference for project modules, not general formal knowledge.

## When to Create a Current Group

Create a current group when a project module is long-lived, repeatedly read by agents, and has enough source material to recover:

- current scope
- design choices
- behavioral/spec contracts
- implementation entry points
- validation facts and gaps

Do not create current groups for temporary notes or one-off records; use a module index instead.

## Lifecycle Modes

| Mode | Use When | Action |
|---|---|---|
| creation | no current group exists | create minimal current set from source inventory |
| patch | current group is sound, one fact changes | update only affected current files and overview |
| hardening_refactor | current exists but mixed with baseline/delta/history | restructure into cleaner current group |
| rewrite | current is structurally unrecoverable | rewrite only with explicit evidence |

## Standard Current Set

Use local naming conventions, but the roles are:

- `overview_current`: default entry, scope, read order, truth source, recoverability
- `design_current`: goals, non-goals, boundaries, decisions, risks
- `spec_current`: states, behavior contracts, interface/config constraints, verification contract
- `implementation_current`: code/config paths, mapping from spec to implementation, known gaps
- `validation_current`: verified facts, commands/evidence, unverified items, next checks

## Hard Stops

- Do not default to full rewrite.
- Do not mark `single_pass_recoverable: true` without independent recoverability verification.
- Do not treat historical records, run artifacts, or baseline files as current truth when an overview current exists.
- Put maintenance records under `Current Maintenance Records/`.

## Creation Record

When creating a current group, write a maintenance record with:

- source inventory
- files created
- files updated
- recoverability decision
- unresolved items
