# Migration Mode

Use Migration mode when notes already exist but the knowledge base has no reliable zones, entries, or metadata.

## Phase 1: Inventory Without Moving

List files and classify them by evidence:

- likely formal knowledge
- project-bound notes
- external source material
- candidate/unclear material
- archive/obsolete material
- runtime/config files that should not be treated as knowledge

Do not move or rewrite files in the first inventory pass unless the user explicitly asks for immediate changes.

If the task proceeds beyond inventory, create structured placements under the standard zones. Preserving `raw/` is allowed and often preferred for traceability, but `raw/` is not the migrated knowledge base.

If the task is a test or dry run, prefer copying structured outputs into the new zones while preserving raw notes, then record the raw-to-structured mapping explicitly.

## Phase 2: Create Entries and Mapping

Before moving files, create:

- top-level entry
- zone entries
- candidate index
- source index
- structure audit

Then create a migration mapping:

- `candidate_moves`
- `candidate_promotions`
- `project_clusters`
- `source_candidates`
- `archive_candidates`
- `uncertain_items`

## Phase 3: Conservative Placement

Rules:

- Unclear placement -> `03_Inbox`.
- External original/source-like material -> `04_Sources`.
- Project-bound notes -> `02_Projects`.
- Reusable reviewed knowledge -> `01_Knowledge`.
- Obsolete/frozen notes -> `90_Archive`.

Do not promote a note into `01_Knowledge` only because it is well-written. It must have clear source, scope, reusable value, and risks/boundaries.

Expected result:

- every classified non-runtime note has either a structured destination file or an explicit unresolved entry
- `raw/` files remain as source trace only
- the migration map links each raw file to its structured destination or unresolved decision

## Phase 4: Structure Without Over-Rewriting

Prefer:

- add overviews
- add indexes
- add frontmatter
- mark status and boundaries

Avoid:

- full content rewrite
- changing factual claims
- deleting old notes
- merging many notes into a single file without traceability

## Phase 5: Audit

Record:

- what was moved
- what was copied or restructured while raw was retained
- what remains uncertain
- what needs promotion review
- what needs current creation
- what links or indexes were updated
