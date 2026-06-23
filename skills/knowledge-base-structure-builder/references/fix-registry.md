# Fix Registry

Fix Registry is a project or subproject scoped recall index for historical fixes. It is horizontal: it gathers modules, paths, symbols, symptoms, summaries, constraints, validation references, and supersession links so future write-side checks and retrieval can find candidate fix documents quickly.

## Scope

Prefer the smallest stable scope:

- `02_Projects/investment-advisor` for a compact project.
- `02_Projects/DMS/04_Tracking` for a large project submodule.

Avoid a global registry unless the vault is small. Global indexes become noisy and make authorization review harder.

## Authority

- The registry is derived and rebuildable. It is not a fact source.
- Every factual registry entry must have `source_fix_doc`.
- Source fix Markdown remains the authority and must keep its own retrieval anchor.
- Human maintenance may add anchors or correct summaries in the source fix document, then regenerate or check the registry.
- Human maintenance must not bypass `source_fix_doc` by creating factual entries directly in the registry.

## Recommended Command

```bash
python3 scripts/kb.py fix-registry --root <vault> --scope 02_Projects/<project-or-subproject>
```

The default output is a JSON cache under `.kb_cache/fix-registry/`. Cite a registry in project records only as a derived validation artifact, never as original evidence.

## Fields

Each entry should include `source_fix_doc`, `source_section`, `source_fingerprint`, `registry_entry_fingerprint`, `module`, `affected_paths`, `symbols`, `symptoms`, `summary`, `constraints`, `validation`, `status`, and supersession fields when present.

`source_fingerprint` is lightweight by default: path, section, mtime, and size are enough to detect likely drift. Do not compute per-field hashes in the registry. Use preflight and hash-check when strong evidence is required.
