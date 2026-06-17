# Codex Capability Registry

Central registry and migration repository for self-developed Codex plugins and skills.

## Layout

- `sources/submodules/`: first-party plugin repositories pinned as Git submodules.
- `skills/`: small first-party skills embedded directly in this repository.
- `manifests/`: capability summaries, ownership, portable source, install strategy, and verification metadata.
- `marketplaces/`: marketplace manifests or templates used to expose local plugins.
- `scripts/`: runtime link installation and verification.
- `docs/`: operating notes, migration records, and sync procedures.

## Ownership Policy

- `first_party_submodule`: first-party plugin with an independent repository and lifecycle.
- `first_party_embedded`: small first-party skill whose source is maintained directly here.
- `third_party_external`: third-party skill or plugin that is not copied into this source tree.

Third-party capabilities are recorded in manifests only. They must not be imported into `skills/` or linked from runtime paths into this repository.

For first-party skills, `manifests/skills.yaml` records the bundled repository path and points to the local `SKILL.md` as the description source. Runtime paths are derived by the install scripts and are not registry facts.

For third-party skills, `manifests/skills.yaml` is an installation record: it names the capability, provider/source hint, install strategy, and trusted backup path when one exists. The registry does not own or vendor that source, and machine-local runtime paths are intentionally omitted.

## Runtime Strategy

- Keep `/home/jichao/.agents/plugins/marketplace.json` stable when possible.
- Link `/home/jichao/.codex/plugins/<plugin>` to `sources/submodules/<plugin>`.
- Link only first-party embedded skills from `/home/jichao/.agents/skills/<skill>` to `skills/<skill>`.
- Keep third-party skills as external runtime directories and verify them from `manifests/skills.yaml`.
