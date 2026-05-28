# Codex Capability Registry Migration Plan

## Decision

`codex-capability-registry` is the central registry and migration repository. It records what must be installed, which version is pinned, and how runtime links are created.

Large first-party plugins remain independent repositories and are included as Git submodules:

- `sources/submodules/cutepower`
- `sources/submodules/subpower`

Small first-party skills are embedded directly:

- `skills/karpathy-guidelines`
- `skills/lark-doc-to-obsidian`

Third-party skills are not copied into the registry source tree. They remain external runtime directories and are tracked in `manifests/skills.yaml` with `ownership: third_party_external`.

## Runtime

Plugin marketplace entries keep using:

- `./.codex/plugins/cutepower`
- `./.codex/plugins/subpower`

The install script makes those paths symlinks to the submodule checkouts. Embedded first-party skills are symlinked from `/home/jichao/.agents/skills`. Third-party skills are restored as normal directories from the captured backup if needed.

## Migration To Another Machine

1. Clone this repository with submodules.
2. Install any third-party skills through their normal installer or restore them from a trusted backup.
3. Run `scripts/install-runtime-links.sh`.
4. Run `scripts/verify-runtime.sh`.

## Boundaries

- Do not modify plugin internals from registry-only maintenance unless intentionally changing the submodule repo.
- Do not import third-party skills into `skills/`.
- Update `manifests/plugins.yaml` when a submodule commit is advanced.
