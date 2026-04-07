from __future__ import annotations

import re
from typing import Any


INLINE_PATTERN = re.compile(
    r"\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*]+)\*"
)


def markdown_to_notion_blocks(markdown: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    paragraph_lines: list[str] = []
    code_lines: list[str] = []
    table_lines: list[str] = []
    in_code_block = False
    code_language = "plain text"

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return
        text = " ".join(part.strip() for part in paragraph_lines if part.strip())
        if text:
            blocks.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": _rich_text(text)},
                }
            )
        paragraph_lines.clear()

    def flush_table() -> None:
        if not table_lines:
            return
        blocks.append(_code_block("\n".join(table_lines), "plain text"))
        table_lines.clear()

    for line in markdown.splitlines() + [""]:
        stripped = line.strip()

        if in_code_block:
            if stripped.startswith("```"):
                blocks.append(_code_block("\n".join(code_lines), code_language))
                code_lines.clear()
                code_language = "plain text"
                in_code_block = False
            else:
                code_lines.append(line)
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            flush_table()
            in_code_block = True
            code_language = stripped[3:].strip() or "plain text"
            continue

        if stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            table_lines.append(line)
            continue
        flush_table()

        if not stripped:
            flush_paragraph()
            continue

        if stripped == "---":
            flush_paragraph()
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading_match:
            flush_paragraph()
            level = len(heading_match.group(1))
            blocks.append(
                {
                    "object": "block",
                    "type": f"heading_{level}",
                    f"heading_{level}": {"rich_text": _rich_text(heading_match.group(2).strip())},
                }
            )
            continue

        quote_match = re.match(r"^>\s+(.*)$", stripped)
        if quote_match:
            flush_paragraph()
            blocks.append(
                {
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": _rich_text(quote_match.group(1).strip())},
                }
            )
            continue

        bullet_match = re.match(r"^[-*]\s+(.*)$", stripped)
        if bullet_match:
            flush_paragraph()
            blocks.append(
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _rich_text(bullet_match.group(1).strip())},
                }
            )
            continue

        numbered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        if numbered_match:
            flush_paragraph()
            blocks.append(
                {
                    "object": "block",
                    "type": "numbered_list_item",
                    "numbered_list_item": {"rich_text": _rich_text(numbered_match.group(1).strip())},
                }
            )
            continue

        paragraph_lines.append(stripped)

    return blocks


def markdown_to_preview(markdown: str, max_length: int = 220) -> str:
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("```"):
            continue
        if line.startswith("- ") or re.match(r"^\d+\.\s+", line):
            line = re.sub(r"^(-|\d+\.)\s+", "", line)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", line)
        line = line.replace("**", "").replace("*", "").replace("`", "")
        if line:
            return line[:max_length].strip()
    flattened = " ".join(part.strip() for part in markdown.splitlines() if part.strip())
    flattened = flattened.replace("**", "").replace("*", "").replace("`", "")
    return flattened[:max_length].strip()


def notion_blocks_to_markdown(blocks: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for block in blocks:
        block_type = block.get("type", "")
        payload = block.get(block_type, {})
        if block_type == "paragraph":
            lines.append(_rich_text_to_markdown(payload.get("rich_text", [])))
            lines.append("")
        elif block_type == "heading_1":
            lines.append(f"# {_rich_text_to_markdown(payload.get('rich_text', []))}")
            lines.append("")
        elif block_type == "heading_2":
            lines.append(f"## {_rich_text_to_markdown(payload.get('rich_text', []))}")
            lines.append("")
        elif block_type == "heading_3":
            lines.append(f"### {_rich_text_to_markdown(payload.get('rich_text', []))}")
            lines.append("")
        elif block_type == "bulleted_list_item":
            lines.append(f"- {_rich_text_to_markdown(payload.get('rich_text', []))}")
        elif block_type == "numbered_list_item":
            lines.append(f"1. {_rich_text_to_markdown(payload.get('rich_text', []))}")
        elif block_type == "quote":
            lines.append(f"> {_rich_text_to_markdown(payload.get('rich_text', []))}")
            lines.append("")
        elif block_type == "code":
            language = payload.get("language", "plain text")
            lines.append(f"```{language}")
            lines.append(_rich_text_to_markdown(payload.get("rich_text", [])))
            lines.append("```")
            lines.append("")
        elif block_type == "divider":
            lines.append("---")
            lines.append("")
    return "\n".join(lines).strip()


def _code_block(text: str, language: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": _rich_text(text or " "),
            "language": _normalize_code_language(language),
        },
    }


def _rich_text(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cursor = 0
    for match in INLINE_PATTERN.finditer(text):
        if match.start() > cursor:
            result.extend(_plain_segment(text[cursor : match.start()]))

        if match.group(1) and match.group(2):
            result.extend(_styled_segment(match.group(1), link=match.group(2)))
        elif match.group(3):
            result.extend(_styled_segment(match.group(3), bold=True))
        elif match.group(4):
            result.extend(_styled_segment(match.group(4), code=True))
        elif match.group(5):
            result.extend(_styled_segment(match.group(5), italic=True))
        cursor = match.end()

    if cursor < len(text):
        result.extend(_plain_segment(text[cursor:]))

    return result or _plain_segment(" ")


def _plain_segment(text: str) -> list[dict[str, Any]]:
    return _styled_segment(text)


def _styled_segment(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    link: str | None = None,
) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for chunk in _chunk_text(text):
        if not chunk:
            continue
        segments.append(
            {
                "type": "text",
                "text": {
                    "content": chunk,
                    "link": {"url": link} if link else None,
                },
                "annotations": {
                    "bold": bold,
                    "italic": italic,
                    "strikethrough": False,
                    "underline": False,
                    "code": code,
                    "color": "default",
                },
            }
        )
    return segments


def _rich_text_to_markdown(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        if item.get("type") != "text":
            continue
        text = item.get("plain_text") or item.get("text", {}).get("content", "")
        annotations = item.get("annotations", {})
        link_payload = item.get("text", {}).get("link") or {}
        link = item.get("href") or link_payload.get("url")
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if link:
            text = f"[{text}]({link})"
        parts.append(text)
    return "".join(parts)


def _chunk_text(text: str, size: int = 1800) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)] or [""]


def _normalize_code_language(language: str) -> str:
    value = language.strip().lower()
    mapping = {
        "text": "plain text",
        "plaintext": "plain text",
        "bash": "shell",
        "sh": "shell",
        "zsh": "shell",
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "md": "markdown",
    }
    return mapping.get(value, value or "plain text")
