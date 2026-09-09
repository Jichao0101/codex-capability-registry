---
name: knowledge-base-structure-builder
description: Build or maintain Markdown knowledge-base structure, indexes and current document groups; assess evidence and write risk for changes to established knowledge. Use for migrations, structural maintenance and substantive fact changes, not routine note formatting.
---

# Knowledge Base Structure Builder

Help the agent make evidence-supported changes with the least process needed for the actual semantic impact. The vault's `AGENTS.md` defines authorization and knowledge policy; this skill supplies methods and tools, not additional permission.

## Before changing content

- Identify the authorized targets, intended changes and current fact source. Start at the nearest relevant overview when needed; reuse context already read in this task. Do not traverse every parent entry by default.
- Read the target and original evidence relevant to the change. Expand retrieval along affected claims, entities, references and discovered constraints. Historical files can provide evidence but do not supersede a current entry merely because they were found first.
- Stop expanding retrieval when changed claims have direct support, discovered conflicts are addressed and remaining gaps do not affect this change. No search hit is not evidence that no constraint exists. Do not claim whole-vault coverage from a scoped search.
- Choose retrieval tools freely. A Retriever package or trace index is optional recall assistance; original Markdown remains the evidence. Reuse fresh evidence instead of repeating a workflow for its own sake.

## Match checks to impact

| Actual change | Required work |
|---|---|
| Spelling, formatting, path repair | Read target; check scope and proposed diff; validate affected links. No historical search by default. |
| Explanation or local project fact addition | Read target and direct sources; explain support and check relevant constraints. Escalate if it changes an established conclusion or protected fact. |
| Same-vault relocation or index path sync | Check both source and destination authorization, preserve content and placement semantics, record moves, update affected links. |
| Conclusion replacement, current fact-source change, protected fact rewrite, promotion, evidence/status change, semantic deletion or supersession | Assess changed claims, supporting originals and counterevidence; run full preflight and satisfy the vault's review requirements. |

For CLI checks, read [governance-tools.md](references/governance-tools.md). A command's `allow` means its mechanical checks passed; it does not prove semantic correctness or override repository policy. Review the proposed diff before applying and the actual diff afterward. If impact exceeds the declared class, reclassify and check before writing; if discovered afterward, stop dependent work and repair the unintended change.

Preserve append-only history. Never silently replace conclusions, promote unreviewed external material, or assert verification that was not performed. Protected document labels trigger closer inspection of affected facts, not blanket confirmation for unrelated typography, unless local policy is stricter.

Resolve missing evidence through authorized reading and retrieval first. Escalate to the user only for unavailable authorization/evidence or decisions the existing authorization does not cover. Existing explicit approval can satisfy review only for the same concrete change and evidence snapshot; it cannot override blockers or authorize a different conflict resolution.

## Structure and placement

Respect the vault's established layout. Project-specific work stays in projects; external raw evidence in sources; unreviewed material in candidates; reviewed reusable knowledge with source, scope and boundaries in formal knowledge.

Load only the references needed:

- Empty vault: [bootstrap.md](references/bootstrap.md).
- Unstructured collection: [migration.md](references/migration.md).
- Existing structure/index maintenance: [maintenance.md](references/maintenance.md).
- Current module lifecycle: [current-lifecycle.md](references/current-lifecycle.md).
- Placement or metadata questions: [placement-rules.md](references/placement-rules.md), [metadata-schema.md](references/metadata-schema.md).

Update entries whose navigation, scope, status or current fact source changes. Do not rewrite an entire current group for one changed fact, or create a five-file group for a small module. Preserve a supported recoverability assertion only while its verification remains applicable; never add or raise it without independent verification.

## Finish

Check the actual changes and run relevant validation. Use scoped lint for structural edits; do not scan unrelated directories for a local prose repair. Report changed files, evidence, checks and unresolved limitations concisely. Mention access scope and candidate/source/promotion placement when relevant; omit empty boilerplate fields. Reports and caches are disposable derived artifacts, not fact sources.
