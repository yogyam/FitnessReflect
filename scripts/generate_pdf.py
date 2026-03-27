from __future__ import annotations

import sys
import textwrap
from pathlib import Path


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_X = 54
MARGIN_TOP = 56
MARGIN_BOTTOM = 56
BODY_FONT_SIZE = 12
BODY_LEADING = 16
TITLE_FONT_SIZE = 22
TITLE_LEADING = 28
HEADING_FONT_SIZE = 16
HEADING_LEADING = 22
FOOTER_FONT_SIZE = 10


def escape_pdf_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", "")
    )


def parse_markdown(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[tuple[str, str]] = []
    paragraph_buffer: list[str] = []
    bullet_buffer: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_buffer:
            blocks.append(("paragraph", " ".join(part.strip() for part in paragraph_buffer)))
            paragraph_buffer.clear()

    def flush_bullets() -> None:
        if bullet_buffer:
            for bullet in bullet_buffer:
                blocks.append(("bullet", bullet))
            bullet_buffer.clear()

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# "):
            flush_paragraph()
            flush_bullets()
            blocks.append(("title", stripped[2:].strip()))
        elif stripped.startswith("## "):
            flush_paragraph()
            flush_bullets()
            blocks.append(("heading", stripped[3:].strip()))
        elif stripped.startswith("- "):
            flush_paragraph()
            bullet_buffer.append(stripped[2:].strip())
        elif not stripped:
            flush_paragraph()
            flush_bullets()
            blocks.append(("spacer", ""))
        else:
            flush_bullets()
            paragraph_buffer.append(stripped)

    flush_paragraph()
    flush_bullets()
    return blocks


def wrap_text(text: str, width: int) -> list[str]:
    return textwrap.wrap(
        text,
        width=width,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]


def block_lines(block_type: str, text: str) -> list[tuple[str, str, int, int]]:
    if block_type == "title":
        return [("F2", line, TITLE_FONT_SIZE, TITLE_LEADING) for line in wrap_text(text, 42)] + [
            ("spacer", "", 0, 10)
        ]
    if block_type == "heading":
        return [("F2", line, HEADING_FONT_SIZE, HEADING_LEADING) for line in wrap_text(text, 60)] + [
            ("spacer", "", 0, 4)
        ]
    if block_type == "paragraph":
        return [("F1", line, BODY_FONT_SIZE, BODY_LEADING) for line in wrap_text(text, 88)] + [
            ("spacer", "", 0, 6)
        ]
    if block_type == "bullet":
        wrapped = wrap_text(text, 82)
        first, *rest = wrapped
        rendered = [("F1", f"- {first}", BODY_FONT_SIZE, BODY_LEADING)]
        rendered.extend(("F1", f"  {line}", BODY_FONT_SIZE, BODY_LEADING) for line in rest)
        return rendered
    return [("spacer", "", 0, 8)]


def paginate(lines: list[tuple[str, str, int, int]]) -> list[list[tuple[str, str, int, int]]]:
    pages: list[list[tuple[str, str, int, int]]] = []
    current_page: list[tuple[str, str, int, int]] = []
    available_height = PAGE_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM - 24
    used_height = 0

    for line in lines:
        leading = line[3]
        if used_height + leading > available_height and current_page:
            pages.append(current_page)
            current_page = []
            used_height = 0
        current_page.append(line)
        used_height += leading

    if current_page:
        pages.append(current_page)
    return pages


def content_stream(page_lines: list[tuple[str, str, int, int]], page_number: int, page_total: int) -> bytes:
    commands = ["BT"]
    y = PAGE_HEIGHT - MARGIN_TOP
    current_font: tuple[str, int] | None = None

    for font_name, text, font_size, leading in page_lines:
        if font_name == "spacer":
            y -= leading
            continue
        if current_font != (font_name, font_size):
            commands.append(f"/{font_name} {font_size} Tf")
            current_font = (font_name, font_size)
        commands.append(f"1 0 0 1 {MARGIN_X} {y} Tm")
        commands.append(f"({escape_pdf_text(text)}) Tj")
        y -= leading

    commands.append("ET")
    commands.extend(
        [
            "BT",
            f"/F3 {FOOTER_FONT_SIZE} Tf",
            f"1 0 0 1 {MARGIN_X} 32 Tm",
            f"(The Luma Guide) Tj",
            f"1 0 0 1 {PAGE_WIDTH - 100} 32 Tm",
            f"({page_number} / {page_total}) Tj",
            "ET",
        ]
    )
    return "\n".join(commands).encode("utf-8")


def build_pdf(page_streams: list[bytes]) -> bytes:
    objects: list[bytes] = []

    def add_object(data: str | bytes) -> int:
        payload = data.encode("utf-8") if isinstance(data, str) else data
        objects.append(payload)
        return len(objects)

    add_object("<< /Type /Catalog /Pages 2 0 R >>")
    add_object("<< /Type /Pages /Count 0 /Kids [] >>")
    font_regular_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    font_bold_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
    font_italic_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >>")

    page_ids: list[int] = []
    content_ids: list[int] = []

    for stream in page_streams:
        stream_id = add_object(
            b"<< /Length "
            + str(len(stream)).encode("utf-8")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )
        content_ids.append(stream_id)
        page_ids.append(0)

    kids_refs = []
    for index, content_id in enumerate(content_ids):
        page_object = (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_regular_id} 0 R /F2 {font_bold_id} 0 R /F3 {font_italic_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids[index] = add_object(page_object)
        kids_refs.append(f"{page_ids[index]} 0 R")

    objects[1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{' '.join(kids_refs)}] >>".encode("utf-8")

    pdf_parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0]
    current_offset = len(pdf_parts[0])

    for index, obj in enumerate(objects, start=1):
        entry = f"{index} 0 obj\n".encode("utf-8") + obj + b"\nendobj\n"
        offsets.append(current_offset)
        pdf_parts.append(entry)
        current_offset += len(entry)

    xref_start = current_offset
    xref_lines = [f"0 {len(objects) + 1}", "0000000000 65535 f "]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n ")
    xref = ("xref\n" + "\n".join(xref_lines) + "\n").encode("utf-8")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"
    ).encode("utf-8")

    return b"".join(pdf_parts) + xref + trailer


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/generate_pdf.py <input.md> <output.pdf>")
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    blocks = parse_markdown(input_path)
    lines: list[tuple[str, str, int, int]] = []
    for block_type, text in blocks:
        lines.extend(block_lines(block_type, text))

    pages = paginate(lines)
    streams = [content_stream(page, index + 1, len(pages)) for index, page in enumerate(pages)]
    output_path.write_bytes(build_pdf(streams))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
