---
name: lark-doc-to-obsidian
description: Import one Feishu/Lark rich-text document into a local Obsidian vault as a Markdown note. Use when Codex needs to fetch a single document, convert supported content to Markdown, export supported image objects as local attachments, leave unsupported rich objects as explicit placeholders, write the result into a specified note path or directory, print an import summary, and verify only the links in that new Markdown file that point into that import's attachment directory. Do not use for batch import, bidirectional sync, OCR, comment sync, whole-vault scans, modifying existing notes, cross-document link mapping, or automatic knowledge/project classification.
---

# lark-doc-to-obsidian

Import one Feishu document into one local Obsidian Markdown note.

## Goal

Convert a single Feishu/Lark rich-text document into a local Obsidian Markdown note, export supported images into a local attachment directory, leave unsupported rich objects as placeholders, and print a concise import summary.

## Inputs

Collect these inputs before acting:

- Feishu wiki URL or wiki token
- Obsidian vault path
- Target note path, or target directory
- Optional attachment directory override

Apply these defaults:

- Prefer an explicit target note path
- If only a target directory is provided, name the file `<document-title>.md`
- Default attachment directory to `<note_stem>.assets/`
- Print the import summary to stdout unless the caller explicitly asks for a file output

Do not infer knowledge-area placement such as `knowledge`, `project`, or `other`.

## Primary access channel

Prefer a logged-in `lark-cli` as the primary document access channel.

For wiki inputs, resolve the wiki node first, then dispatch by the returned object type.

In the first version, fully support only `docx` objects after wiki resolution.

Do not assume the script directly holds HTTP API credentials.  
Do not implement interactive login or token lifecycle management inside this skill.

## Core job

Execute this flow:

1. Accept a Feishu wiki URL or wiki token as input.
2. Extract the wiki token.
3. Run:

   ```bash
   lark-cli wiki spaces get_node --params '{"token":"<wiki_token>"}'
   ```

4. Parse the returned JSON and read:
   - `data.node.obj_type`
   - `data.node.obj_token`

5. If `obj_type != "docx"`, stop and report an unsupported object type error.
6. If `obj_type == "docx"`, run:

   ```bash
   lark-cli docs +fetch --doc <obj_token>
   ```

7. Parse the returned JSON and extract:
   - `data.markdown`
   - `data.title` if available

8. Convert the current document body into the target Markdown note content.
9. Do not recursively expand `mention-doc`; preserve those references as-is.
10. For object handling in v1.5:
    - convert standard text structure directly into Markdown
    - export `<image .../>` objects as local attachments when `lark-cli docs +media-download` succeeds
    - write a clear placeholder for unsupported or unstable rich objects when reliable export is not available

11. Write the Markdown file into the requested vault location.
12. Write any generated image attachments into the import attachment directory.
13. Verify only the local links in the new Markdown file that point into that attachment directory.
14. Print a concise import summary.

## Conversion rules

Convert basic document structure into straightforward Markdown.

Prefer stable mappings such as:

- headings
- paragraphs
- bullet and numbered lists
- block quotes
- code blocks
- tables when they can be represented simply
- inline emphasis
- links
- images when export is supported

Keep output simple and readable. Do not attempt full visual fidelity.

Track object capability with these categories:

- `markdown_native`
- `image_like`
- `snapshot_candidate`
- `unsupported`

If a block or object cannot be represented cleanly in Markdown, choose one of these:

- for supported image objects, save it as an attachment and insert a local reference
- insert a placeholder that states the object could not be reliably converted

Do not invent missing content.

Do not recursively fetch or expand `mention-doc`.

## Attachment downgrade rules

Treat these as downgrade candidates when Markdown conversion is not stable:

- whiteboards
- complex diagrams
- embedded objects
- rich visual cards
- other document objects without a dependable Markdown form

Default behavior in v1.5:

- image objects: classify as `image_like`; export to a local attachment if `docs +media-download --type media` succeeds; otherwise insert a placeholder
- whiteboards: classify as `snapshot_candidate`; export a whiteboard snapshot image if `docs +media-download --type whiteboard` succeeds; otherwise insert a placeholder
- sheets, grids, rich cards, and other unsupported rich objects: classify as `unsupported`; insert a placeholder or preserve the explicit source tag, and report them as `placeholder_only`

Do not force screenshots.  
Do not perform OCR.  
Do not claim fidelity that the import does not preserve.

## Path rules

Resolve the output path as follows:

- if the caller provides a note path, use it
- if the caller provides only a directory, create `<document-title>.md` in that directory

Resolve attachments as follows:

- use the caller-provided attachment directory if present
- otherwise use `<note_stem>.assets/`

Keep attachment links local and relative when possible.

If the document title is used in a filename, preserve readable Unicode when possible and only replace characters invalid for the local filesystem.

## Link verification rules

Verify only this narrow scope:

- inspect the newly generated Markdown file
- check only local links that point into the current attachment directory
- report missing or broken attachment references from this import

Do not:

- scan the whole vault
- modify existing notes
- repair links in other files
- map cross-document Feishu links into Obsidian links

## Safety rules

- Do not overwrite an existing note unless the caller explicitly permits overwrite.
- Do not delete pre-existing attachments in the target directory.
- If the target filename already exists and overwrite is not allowed, stop and report the conflict.
- If attachment export partially fails, still write the Markdown note with clear placeholders and report the failure.

## CLI command contract

### `wiki spaces get_node`

Command:

```bash
lark-cli wiki spaces get_node --params '{"token":"<wiki_token>"}'
```

Success contract:

- exit code must be `0`
- stdout must be valid JSON
- JSON must contain `data.node.obj_type`
- JSON must contain `data.node.obj_token`

Failure contract:

- `lark-cli` not found
- non-zero exit code
- stdout is not valid JSON
- missing `obj_type`
- missing `obj_token`

### `docs +fetch`

Command:

```bash
lark-cli docs +fetch --doc <obj_token>
```

Success contract:

- exit code must be `0`
- stdout must be valid JSON
- JSON must contain `ok == true`
- JSON must contain `data.markdown`
- `data.title` is optional

Failure contract:

- `lark-cli` not found
- CLI not logged in or permission denied
- non-zero exit code
- stdout is not valid JSON
- `ok != true`
- missing `data.markdown`

## Supported routing

### Supported

- `obj_type == "docx"`
  - fetch with `lark-cli docs +fetch --doc <obj_token>`

### Not supported in v1

Explicitly reject and report unsupported object types such as:

- `doc`
- `sheet`
- `bitable`
- `slides`
- `file`
- `mindnote`
- missing or unknown object types

Do not silently downgrade these into generic imports.

## Summary output

Print a concise import summary to stdout.

Include at least:

- document title
- Markdown output path
- attachment directory path
- `exported_as_image` and `placeholder_only` results
- attachment-link verification result for this import
- unconverted content or known risks

Only write a sidecar summary file if the caller explicitly requests it.

## Non-goals

Do not expand this skill into:

- batch import
- bidirectional sync
- OCR
- comment or annotation sync
- whole-vault scans
- edits to pre-existing notes
- cross-document link mapping
- automatic note classification
- recursive expansion of mentioned child documents
- direct HTTP API authentication management

## Execution guidance

Use a script-backed flow.

Keep script responsibilities narrow:

- parse wiki input
- resolve one wiki node through `lark-cli`
- validate `obj_type == "docx"`
- fetch one doc body through `lark-cli`
- convert supported content
- export supported image attachments when possible
- emit placeholders when export is not reliable
- write one Markdown note and its attachments
- verify only attachment links in that note
- print the import summary

Keep orchestration light in the skill body. Avoid turning this skill into a general vault-management tool.
