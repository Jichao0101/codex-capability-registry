# Metadata Schema

Use concise frontmatter. Do not invent stronger status than evidence supports.

## Formal Knowledge

Minimum:

```yaml
---
type: knowledge
status: verified | legacy_structured | draft
domain: <topic>
summary: <one sentence>
sources:
  - <source or internal basis>
scope: <where this applies>
risks:
  - <risk or non-applicability>
updated_at: YYYY-MM-DD
---
```

## Topic Index

```yaml
---
type: knowledge_topic_index
status: active
domain: <topic>
scope: <index purpose>
updated_at: YYYY-MM-DD
---
```

## Candidate

```yaml
---
type: candidate
status: draft | pending_review | promoted | partially_promoted | rejected
summary: <one sentence>
sources:
  - <source>
target_path: <optional>
scope: <topic>
updated_at: YYYY-MM-DD
---
```

## Source Card

```yaml
---
type: source_card
status: active
source_type: web | paper | pdf | internal | other
source: <url or source path>
summary: <one sentence>
scope: <topic>
risks:
  - <source limitation>
updated_at: YYYY-MM-DD
---
```

## Project Current

```yaml
---
type: project_current
status: verified | created_but_not_fully_verified | draft
project: <project>
module: <module>
current_kind: overview | design | spec | implementation | validation
single_pass_recoverable: false
sources:
  - <source>
updated_at: YYYY-MM-DD
---
```

Only include `single_pass_recoverable: true` after independent recoverability verification.
