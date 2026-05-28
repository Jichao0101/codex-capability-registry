#!/usr/bin/env python3
"""Minimal skeleton for importing one Lark/Feishu doc into Obsidian.

This script intentionally keeps a narrow scope:
- import one document
- convert supported content to Markdown
- downgrade unsupported objects to attachments or placeholders
- write one Markdown file plus attachments
- verify only links in that Markdown pointing into the current attachment dir
- print a concise import summary
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import unquote, urlparse
from dataclasses import asdict, dataclass, field
from pathlib import Path


ATTACHMENT_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|\[[^\]]+\]\(([^)]+)\)")
UNSAFE_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WHITESPACE_RE = re.compile(r"\s+")
WIKI_URL_TOKEN_RE = re.compile(r"/wiki/([A-Za-z0-9]+)")
DOCX_URL_TOKEN_RE = re.compile(r"/docx/([A-Za-z0-9]+)")
IMAGE_TAG_RE = re.compile(r'<image\b[^>]*token="([^"]+)"[^>]*/?>')
WHITEBOARD_TAG_RE = re.compile(r'<whiteboard\b[^>]*token="([^"]+)"[^>]*/?>')
PLACEHOLDER_TAG_RE = re.compile(r'<(sheet|grid|card|iframe-card|embed-card|rich-card)\b([^>]*)/?>')
LARK_TABLE_RE = re.compile(r"<lark-table\b[^>]*>(.*?)</lark-table>", re.DOTALL)
LARK_TR_RE = re.compile(r"<lark-tr\b[^>]*>(.*?)</lark-tr>", re.DOTALL)
LARK_TD_RE = re.compile(r"<lark-td\b[^>]*>(.*?)</lark-td>", re.DOTALL)
EQUATION_RE = re.compile(r"<equation\b[^>]*>(.*?)</equation>", re.DOTALL)
QUOTE_CONTAINER_RE = re.compile(r"<quote-container\b[^>]*>(.*?)</quote-container>", re.DOTALL)
MENTION_DOC_RE = re.compile(r"<mention-doc\b")
MENTION_DOC_FULL_RE = re.compile(r'<mention-doc\b([^>]*)token="([^"]+)"([^>]*)type="([^"]+)"([^>]*)>(.*?)</mention-doc>')
MARKDOWN_LINK_RE = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')
TRAILING_ATTR_RE = re.compile(r'\s*\{[A-Za-z0-9_.:-]+="[^"]*"(?:\s+[A-Za-z0-9_.:-]+="[^"]*")*\}\s*$')
INLINE_TAG_RE = re.compile(r"</?(?:lark-[a-z-]+|quote-container|equation)\b[^>]*>")


@dataclass
class HandledObject:
    object_type: str
    object_classification: str
    result: str
    detail: str
    output_path: str | None = None


@dataclass
class ImportSummary:
    source: str
    document_title: str
    note_path: str
    attachment_dir: str
    handled_objects: list[HandledObject] = field(default_factory=list)
    broken_attachment_links: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    title: str
    markdown: str
    handled_objects: list[HandledObject] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


@dataclass
class SourceDocument:
    title: str
    markdown: str
    source_base_url: str | None = None


@dataclass
class WikiNode:
    obj_type: str
    obj_token: str
    title: str | None = None


@dataclass
class SourceRef:
    ref_kind: str
    token: str


class LarkCliError(RuntimeError):
    """Raised when a lark-cli command cannot be executed successfully."""


class NoteAlreadyExistsError(FileExistsError):
    """Raised when the target note already exists and must not be modified."""


class LarkDocImporter:
    """Import one Feishu wiki doc through the logged-in lark-cli only."""

    def fetch_source_document(self, source: str) -> SourceDocument:
        source_ref = parse_source_ref(source)
        if source_ref.ref_kind == "wiki":
            node = resolve_wiki_node(source_ref.token)
            if node.obj_type != "docx":
                raise LarkCliError(f"unsupported obj_type: {node.obj_type}")
            title, markdown = fetch_docx(node.obj_token)
            resolved_title = title or node.title or source_ref.token
        elif source_ref.ref_kind == "docx":
            title, markdown = fetch_docx(source_ref.token)
            resolved_title = title or source_ref.token
        else:
            raise LarkCliError(f"unsupported source type: {source_ref.ref_kind}")
        return SourceDocument(
            title=resolved_title,
            markdown=markdown,
            source_base_url=extract_base_url(source),
        )

    def import_document(
        self,
        source_document: SourceDocument,
        attachment_dir: Path,
    ) -> ImportResult:
        processed_markdown, handled_objects, risks = self.process_markdown(
            markdown=source_document.markdown,
            attachment_dir=attachment_dir,
            note_stem=normalize_filename(source_document.title),
            source_base_url=source_document.source_base_url,
        )

        handled_objects.insert(
            0,
            HandledObject(
                object_type="docx_body",
                object_classification="markdown_native",
                result="markdown_native",
                detail="Imported Markdown body from lark-cli docs +fetch",
            ),
        )

        if MENTION_DOC_RE.search(processed_markdown):
            risks.append("mention-doc references were preserved and not expanded")

        return ImportResult(
            title=source_document.title,
            markdown=processed_markdown,
            handled_objects=handled_objects,
            risks=risks,
        )

    def process_markdown(
        self,
        markdown: str,
        attachment_dir: Path,
        note_stem: str,
        source_base_url: str | None,
    ) -> tuple[str, list[HandledObject], list[str]]:
        risks: list[str] = []
        handled_objects: list[HandledObject] = []
        image_index = 0
        whiteboard_index = 0

        def replace_image(match: re.Match[str]) -> str:
            nonlocal image_index
            image_index += 1
            token = match.group(1)
            try:
                exported_path = export_image_attachment(
                    token=token,
                    attachment_dir=attachment_dir,
                    base_name=f"{note_stem}_image_{image_index:03d}",
                )
                relative_path = f"{attachment_dir.name}/{exported_path.name}"
                handled_objects.append(
                    HandledObject(
                        object_type="image",
                        object_classification="image_like",
                        result="exported_as_image",
                        detail=f"Exported image token {token}",
                        output_path=relative_path,
                    )
                )
                return render_exported_image_markdown(relative_path)
            except LarkCliError as exc:
                risks.append(f"image export failed for token {token}: {exc}")
                handled_objects.append(
                    HandledObject(
                        object_type="image",
                        object_classification="image_like",
                        result="placeholder_only",
                        detail=f"Image token {token} could not be exported",
                    )
                )
                return f"[placeholder: image token {token} could not be exported]"

        processed = IMAGE_TAG_RE.sub(replace_image, markdown)

        def replace_whiteboard(match: re.Match[str]) -> str:
            nonlocal whiteboard_index
            whiteboard_index += 1
            token = match.group(1)
            try:
                exported_path = export_whiteboard_snapshot(
                    token=token,
                    attachment_dir=attachment_dir,
                    base_name=f"{note_stem}_whiteboard_{whiteboard_index:03d}",
                )
                relative_path = f"{attachment_dir.name}/{exported_path.name}"
                handled_objects.append(
                    HandledObject(
                        object_type="whiteboard",
                        object_classification="snapshot_candidate",
                        result="exported_as_image",
                        detail=f"Exported whiteboard snapshot token {token}",
                        output_path=relative_path,
                    )
                )
                return render_exported_image_markdown(relative_path)
            except LarkCliError as exc:
                risks.append(f"whiteboard export failed for token {token}: {exc}")
                handled_objects.append(
                    HandledObject(
                        object_type="whiteboard",
                        object_classification="snapshot_candidate",
                        result="placeholder_only",
                        detail=f"Whiteboard token {token} could not be exported",
                    )
                )
                return f"[placeholder: whiteboard token {token} could not be exported]"

        processed = WHITEBOARD_TAG_RE.sub(replace_whiteboard, processed)
        processed = convert_lark_tables(processed, handled_objects)
        processed = convert_equations(processed, handled_objects)
        processed = convert_quote_containers(processed, handled_objects)

        for tag_match in PLACEHOLDER_TAG_RE.finditer(processed):
            tag_name = tag_match.group(1)
            token_match = re.search(r'token="([^"]+)"', tag_match.group(0))
            detail = f"Preserved {tag_name} placeholder"
            if token_match:
                detail += f" for token {token_match.group(1)}"
            handled_objects.append(
                HandledObject(
                    object_type=tag_name,
                    object_classification="unsupported",
                    result="placeholder_only",
                    detail=detail,
                )
            )

        processed = cleanup_trailing_attributes(processed)
        processed = normalize_links(processed, source_base_url=source_base_url)
        return processed, handled_objects, risks


def parse_source_ref(source: str) -> SourceRef:
    source = source.strip()
    wiki_match = WIKI_URL_TOKEN_RE.search(source)
    if wiki_match:
        return SourceRef(ref_kind="wiki", token=wiki_match.group(1))
    docx_match = DOCX_URL_TOKEN_RE.search(source)
    if docx_match:
        return SourceRef(ref_kind="docx", token=docx_match.group(1))
    if "/" in source or "://" in source:
        raise ValueError("unsupported source format; expected a wiki URL or wiki token")
    return SourceRef(ref_kind="wiki", token=source)


def extract_base_url(source: str) -> str | None:
    source = source.strip()
    if "://" not in source:
        return None
    parsed = urlparse(source)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def run_lark_cli(command: list[str], cwd: Path | None = None) -> str:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, cwd=cwd)
    except FileNotFoundError as exc:
        raise LarkCliError("lark-cli not found in PATH") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise LarkCliError(
            f"command failed ({completed.returncode}): {' '.join(command)} | {detail}"
        )
    return completed.stdout


def run_lark_cli_no_stdout(command: list[str], cwd: Path | None = None) -> None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False, cwd=cwd)
    except FileNotFoundError as exc:
        raise LarkCliError("lark-cli not found in PATH") from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "no output"
        raise LarkCliError(
            f"command failed ({completed.returncode}): {' '.join(command)} | {detail}"
        )


def parse_json_output(raw: str, context: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LarkCliError(f"invalid JSON from lark-cli during {context}") from exc
    if not isinstance(parsed, dict):
        raise LarkCliError(f"invalid JSON shape during {context}: expected object")
    return parsed


def require_field(mapping: dict, key: str, context: str):
    if key not in mapping:
        raise LarkCliError(f"missing field: {context}.{key}")
    return mapping[key]


def resolve_wiki_node(wiki_token: str) -> WikiNode:
    raw = run_lark_cli(
        [
            "lark-cli",
            "wiki",
            "spaces",
            "get_node",
            "--params",
            json.dumps({"token": wiki_token}, ensure_ascii=False),
        ]
    )
    payload = parse_json_output(raw, "wiki get_node")
    data = require_field(payload, "data", "root")
    if not isinstance(data, dict):
        raise LarkCliError("invalid JSON shape during wiki get_node: data is not object")
    node = require_field(data, "node", "data")
    if not isinstance(node, dict):
        raise LarkCliError("invalid JSON shape during wiki get_node: node is not object")
    obj_type = require_field(node, "obj_type", "data.node")
    obj_token = require_field(node, "obj_token", "data.node")
    title = node.get("title")
    if not isinstance(obj_type, str) or not obj_type:
        raise LarkCliError("missing or unknown obj_type")
    if not isinstance(obj_token, str) or not obj_token:
        raise LarkCliError("missing field: data.node.obj_token")
    if title is not None and not isinstance(title, str):
        raise LarkCliError("invalid JSON shape during wiki get_node: title is not string")
    return WikiNode(obj_type=obj_type, obj_token=obj_token, title=title)


def fetch_docx(obj_token: str) -> tuple[str | None, str]:
    raw = run_lark_cli(["lark-cli", "docs", "+fetch", "--doc", obj_token])
    payload = parse_json_output(raw, "docs +fetch")
    ok = require_field(payload, "ok", "root")
    if ok is not True:
        raise LarkCliError("docs fetch returned ok=false")
    data = require_field(payload, "data", "root")
    if not isinstance(data, dict):
        raise LarkCliError("invalid JSON shape during docs +fetch: data is not object")
    markdown = require_field(data, "markdown", "data")
    title = data.get("title")
    if not isinstance(markdown, str):
        raise LarkCliError("invalid JSON shape during docs +fetch: markdown is not string")
    if title is not None and not isinstance(title, str):
        raise LarkCliError("invalid JSON shape during docs +fetch: title is not string")
    return title, markdown


def export_image_attachment(token: str, attachment_dir: Path, base_name: str) -> Path:
    return export_media_file(
        token=token,
        attachment_dir=attachment_dir,
        base_name=base_name,
        media_type="media",
    )


def export_whiteboard_snapshot(token: str, attachment_dir: Path, base_name: str) -> Path:
    return export_media_file(
        token=token,
        attachment_dir=attachment_dir,
        base_name=base_name,
        media_type="whiteboard",
    )


def export_media_file(
    token: str,
    attachment_dir: Path,
    base_name: str,
    media_type: str,
) -> Path:
    before_paths = {path.resolve() for path in attachment_dir.iterdir()} if attachment_dir.exists() else set()
    requested_output = attachment_dir / base_name
    run_lark_cli_no_stdout(
        [
            "lark-cli",
            "docs",
            "+media-download",
            "--token",
            token,
            "--type",
            media_type,
            "--output",
            f"./{base_name}",
        ],
        cwd=attachment_dir,
    )

    if requested_output.exists():
        return normalize_exported_path(requested_output)

    after_paths = {path.resolve() for path in attachment_dir.iterdir()} if attachment_dir.exists() else set()
    new_paths = [Path(path) for path in sorted(after_paths - before_paths)]
    if len(new_paths) == 1:
        return normalize_exported_path(new_paths[0])

    matching_paths = sorted(attachment_dir.glob(f"{base_name}*"))
    if len(matching_paths) == 1:
        return normalize_exported_path(matching_paths[0])

    raise LarkCliError(
        f"media-download completed but exported file could not be resolved for token {token}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Lark doc URL or token")
    parser.add_argument("--vault", required=True, help="Path to the Obsidian vault")
    parser.add_argument(
        "--note-path",
        help="Explicit output note path, absolute or relative to --vault",
    )
    parser.add_argument(
        "--note-dir",
        help="Output note directory, absolute or relative to --vault",
    )
    parser.add_argument(
        "--attachment-dir",
        help="Explicit attachment directory, absolute or relative to note parent",
    )
    parser.add_argument(
        "--summary-format",
        choices=("text", "json"),
        default="text",
        help="Summary output format",
    )
    return parser.parse_args()


def normalize_filename(name: str) -> str:
    cleaned = UNSAFE_FILENAME_CHARS_RE.sub("_", name)
    cleaned = WHITESPACE_RE.sub("_", cleaned).strip("_ ").rstrip(".")
    return cleaned or "untitled"


def normalize_exported_path(path: Path) -> Path:
    normalized_name = normalize_filename(path.name)
    normalized_path = path.with_name(normalized_name)
    if normalized_path == path:
        return path
    if normalized_path.exists():
        normalized_path = uniquify_path(normalized_path)
    path.rename(normalized_path)
    return normalized_path


def uniquify_path(path: Path) -> Path:
    stem = path.stem
    suffix = path.suffix
    index = 1
    while True:
        candidate = path.with_name(f"{stem}_{index:03d}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def render_exported_image_markdown(relative_path: str) -> str:
    return f"![](./{relative_path})"


def convert_lark_tables(markdown: str, handled_objects: list[HandledObject]) -> str:
    def replace(match: re.Match[str]) -> str:
        table_markdown = render_lark_table(match.group(1))
        handled_objects.append(
            HandledObject(
                object_type="lark-table",
                object_classification="markdown_native",
                result="markdown_native",
                detail="Converted lark-table to Markdown table",
            )
        )
        return table_markdown

    return LARK_TABLE_RE.sub(replace, markdown)


def render_lark_table(table_body: str) -> str:
    rows: list[list[str]] = []
    for row_match in LARK_TR_RE.finditer(table_body):
        cells = [normalize_table_cell(cell_match.group(1)) for cell_match in LARK_TD_RE.finditer(row_match.group(1))]
        if cells:
            rows.append(cells)

    if not rows:
        return "[placeholder: empty lark-table could not be converted]"

    column_count = max(len(row) for row in rows)
    normalized_rows = [row + [""] * (column_count - len(row)) for row in rows]
    header = normalized_rows[0]
    separator = ["---"] * column_count
    body_rows = normalized_rows[1:]

    lines = [
        format_markdown_table_row(header),
        format_markdown_table_row(separator),
    ]
    lines.extend(format_markdown_table_row(row) for row in body_rows)
    return "\n" + "\n".join(lines) + "\n"


def normalize_table_cell(cell_content: str) -> str:
    text = strip_inline_tags(cell_content)
    text = INLINE_TAG_RE.sub("", text)
    text = " ".join(text.split())
    text = text.replace("|", r"\|")
    return text


def format_markdown_table_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def convert_equations(markdown: str, handled_objects: list[HandledObject]) -> str:
    def replace(match: re.Match[str]) -> str:
        equation = normalize_block_text(match.group(1))
        handled_objects.append(
            HandledObject(
                object_type="equation",
                object_classification="markdown_native",
                result="markdown_native",
                detail="Converted equation block to Markdown math fence",
            )
        )
        return f"\n$$\n{equation}\n$$\n"

    return EQUATION_RE.sub(replace, markdown)


def convert_quote_containers(markdown: str, handled_objects: list[HandledObject]) -> str:
    def replace(match: re.Match[str]) -> str:
        text = normalize_block_text(match.group(1))
        handled_objects.append(
            HandledObject(
                object_type="quote-container",
                object_classification="markdown_native",
                result="markdown_native",
                detail="Converted quote-container to Markdown blockquote",
            )
        )
        quoted_lines = [f"> {line}" if line else ">" for line in text.splitlines()]
        return "\n" + "\n".join(quoted_lines) + "\n"

    return QUOTE_CONTAINER_RE.sub(replace, markdown)


def normalize_block_text(text: str) -> str:
    text = strip_inline_tags(text)
    text = INLINE_TAG_RE.sub("", text)
    lines = [line.strip() for line in text.strip().splitlines()]
    return "\n".join(line for line in lines if line)


def cleanup_trailing_attributes(markdown: str) -> str:
    cleaned_lines: list[str] = []
    in_fenced_code = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fenced_code = not in_fenced_code
            cleaned_lines.append(line)
            continue
        if not in_fenced_code:
            line = TRAILING_ATTR_RE.sub("", line)
        cleaned_lines.append(line.rstrip())
    return "\n".join(cleaned_lines)


def normalize_links(markdown: str, source_base_url: str | None) -> str:
    markdown = normalize_mention_doc_links(markdown, source_base_url=source_base_url)
    markdown = normalize_external_markdown_links(markdown)
    return markdown


def normalize_mention_doc_links(markdown: str, source_base_url: str | None) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(2)
        ref_type = match.group(4).strip().lower()
        title = strip_inline_tags(match.group(6).strip()) or token
        reconstructed_url = reconstruct_feishu_doc_url(
            token=token,
            ref_type=ref_type,
            source_base_url=source_base_url,
        )
        if reconstructed_url is None:
            return match.group(0)
        return f"[{title}]({reconstructed_url})"

    return MENTION_DOC_FULL_RE.sub(replace, markdown)


def normalize_external_markdown_links(markdown: str) -> str:
    def replace(match: re.Match[str]) -> str:
        title = match.group(1)
        destination = match.group(2).strip()
        decoded_destination = decode_external_url(destination)
        if decoded_destination is None:
            return match.group(0)
        return f"[{title}]({decoded_destination})"

    return MARKDOWN_LINK_RE.sub(replace, markdown)


def decode_external_url(destination: str) -> str | None:
    if destination.startswith("./") or destination.startswith("../") or destination.startswith("#"):
        return None
    decoded = unquote(destination)
    if decoded.startswith("http://") or decoded.startswith("https://"):
        return decoded
    return None


def reconstruct_feishu_doc_url(
    token: str,
    ref_type: str,
    source_base_url: str | None,
) -> str | None:
    if source_base_url is None:
        return None
    if ref_type == "docx":
        return f"{source_base_url}/docx/{token}"
    return f"{source_base_url}/wiki/{token}"


def strip_inline_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def resolve_under_vault(vault: Path, candidate: str) -> Path:
    path = Path(candidate)
    return path if path.is_absolute() else (vault / path)


def resolve_note_path(vault: Path, note_path: str | None, note_dir: str | None, title: str) -> Path:
    if note_path:
        return resolve_under_vault(vault, note_path)
    if note_dir:
        directory = resolve_under_vault(vault, note_dir)
        return directory / f"{normalize_filename(title)}.md"
    raise ValueError("Either --note-path or --note-dir must be provided")


def resolve_attachment_dir(note_path: Path, attachment_dir: str | None) -> Path:
    if attachment_dir:
        candidate = Path(attachment_dir)
        return candidate if candidate.is_absolute() else (note_path.parent / candidate)
    return note_path.parent / f"{note_path.stem}.assets"


def extract_attachment_links(markdown: str, attachment_dir: Path) -> list[str]:
    links: list[str] = []
    attachment_dir_name = attachment_dir.name
    for match in ATTACHMENT_LINK_RE.finditer(markdown):
        raw = match.group(1) or match.group(2)
        if not raw or "://" in raw or raw.startswith("#"):
            continue
        if raw.startswith(f"{attachment_dir_name}/") or f"/{attachment_dir_name}/" in raw:
            links.append(raw)
    return links


def verify_attachment_links(markdown: str, note_path: Path, attachment_dir: Path) -> list[str]:
    broken: list[str] = []
    for link in extract_attachment_links(markdown, attachment_dir):
        target = (note_path.parent / link).resolve()
        if not target.exists():
            broken.append(link)
    return broken


def ensure_parent_dirs(note_path: Path, attachment_dir: Path) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    attachment_dir.mkdir(parents=True, exist_ok=True)


def write_markdown(note_path: Path, markdown: str) -> None:
    note_path.write_text(markdown, encoding="utf-8")


def format_text_summary(summary: ImportSummary) -> str:
    grouped = group_handled_objects(summary.handled_objects)
    lines = [
        f"Document title: {summary.document_title}",
        f"Note path: {summary.note_path}",
        f"Attachment dir: {summary.attachment_dir}",
    ]
    for section_name in ("exported_as_image", "placeholder_only"):
        lines.append(f"{section_name}:")
        items = grouped.get(section_name, [])
        if items:
            for item in items:
                lines.append(
                    f"- {item.object_type} [{item.object_classification}]: {item.detail}"
                    + (f" -> {item.output_path}" if item.output_path else "")
                )
        else:
            lines.append("- none")

    lines.append("Attachment link check:")
    if summary.broken_attachment_links:
        for link in summary.broken_attachment_links:
            lines.append(f"- broken: {link}")
    else:
        lines.append("- ok")

    lines.append("Risks:")
    if summary.risks:
        for risk in summary.risks:
            lines.append(f"- {risk}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def group_handled_objects(handled_objects: list[HandledObject]) -> dict[str, list[HandledObject]]:
    grouped = {
        "exported_as_image": [],
        "placeholder_only": [],
    }
    for item in handled_objects:
        grouped.setdefault(item.result, []).append(item)
    return grouped


def print_summary(summary: ImportSummary, summary_format: str) -> None:
    if summary_format == "json":
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
        return
    print(format_text_summary(summary))


def run(importer: LarkDocImporter, args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    if not vault.exists():
        raise FileNotFoundError(f"Vault does not exist: {vault}")

    source_document = importer.fetch_source_document(args.source)
    note_path = resolve_note_path(vault, args.note_path, args.note_dir, source_document.title).resolve()
    attachment_dir = resolve_attachment_dir(note_path, args.attachment_dir).resolve()
    if note_path.exists():
        raise NoteAlreadyExistsError(f"Refusing to modify existing note: {note_path}")

    ensure_parent_dirs(note_path, attachment_dir)
    result = importer.import_document(source_document, attachment_dir=attachment_dir)
    write_markdown(note_path, result.markdown)
    broken_links = verify_attachment_links(result.markdown, note_path, attachment_dir)

    summary = ImportSummary(
        source=args.source,
        document_title=result.title,
        note_path=str(note_path),
        attachment_dir=str(attachment_dir),
        handled_objects=result.handled_objects,
        broken_attachment_links=broken_links,
        risks=result.risks,
    )
    print_summary(summary, args.summary_format)
    return 1 if broken_links else 0


def main() -> int:
    args = parse_args()
    importer = LarkDocImporter()
    try:
        return run(importer, args)
    except NoteAlreadyExistsError as exc:
        print(f"Note already exists: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
