# Codex Capability Registry Migration Plan

## Decision

`codex-capability-registry` is the central registry and migration repository. It records available capabilities, their ownership, portable source facts, install strategy, verification expectations, and pinned versions where applicable.

Large first-party plugins remain independent repositories and are included as Git submodules:

- `sources/submodules/cutepower`
- `sources/submodules/subpower`

Small first-party skills are embedded directly:

- `skills/karpathy-guidelines`
- `skills/lark-doc-to-obsidian`

Third-party skills are not copied into the registry source tree. They remain external runtime directories and are tracked in `manifests/skills.yaml` with `ownership: third_party_external`.

Each third-party entry is an installation record, not source ownership. The record should keep enough portable information to rebuild the runtime directory later: capability summary, provider/source hint, install strategy, and trusted backup path when available. Machine-local runtime paths are derived by scripts and should not be stored as registry facts.

## Runtime

Plugin marketplace entries keep using:

- `./.codex/plugins/cutepower`
- `./.codex/plugins/subpower`

The install script makes those paths symlinks to the submodule checkouts. Embedded first-party skills are symlinked from the configured agents skills directory. Third-party skills are restored as normal directories from the captured backup if needed.

## Migration To Another Machine

1. Clone this repository with submodules.
2. Install any third-party skills through their normal installer or restore them from a trusted backup.
3. Run `scripts/install-runtime-links.sh`.
4. Run `scripts/verify-runtime.sh`.

On the original machine, `scripts/install-runtime-links.sh --restore-third-party` may be used to restore third-party runtime directories from the backup paths recorded in `manifests/skills.yaml`. On a new machine, prefer the original provider or a freshly captured trusted backup.

## Boundaries

- Do not modify plugin internals from registry-only maintenance unless intentionally changing the submodule repo.
- Do not import third-party skills into `skills/`.
- Update `manifests/plugins.yaml` when a submodule commit is advanced.
