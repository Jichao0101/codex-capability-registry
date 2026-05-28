# Sync Procedure

## Clone On A New Machine

```bash
git clone --recurse-submodules <registry-remote> codex-capability-registry
cd codex-capability-registry
scripts/install-runtime-links.sh
scripts/verify-runtime.sh
```

If the repository was cloned without submodules:

```bash
git submodule update --init --recursive
```

## Advance A Plugin Submodule

Plugin development remains in the plugin repository:

```bash
cd sources/submodules/cutepower
git pull --ff-only origin main
cd ../..
git add sources/submodules/cutepower manifests/plugins.yaml
git commit -m "Advance cutepower submodule"
```

After advancing a submodule, update the matching `commit:` value in `manifests/plugins.yaml`.

## Embedded First-Party Skills

Edit embedded skills directly under:

```bash
skills/karpathy-guidelines
skills/lark-doc-to-obsidian
```

Runtime links are managed by:

```bash
scripts/install-runtime-links.sh
```

## Third-Party Skills

Third-party skills are external runtime directories. They are listed in `manifests/skills.yaml` with `ownership: third_party_external`.

Do not copy third-party source into `skills/`. The install script may restore them from a trusted backup path when the local runtime directory is missing.

## Verification

Run:

```bash
scripts/verify-runtime.sh
```

The verifier checks:

- plugin submodule commit equals `manifests/plugins.yaml`
- plugin runtime links point at `sources/submodules/*`
- first-party embedded skill links point at `skills/*`
- third-party skills exist as normal runtime directories and do not pollute `skills/`
