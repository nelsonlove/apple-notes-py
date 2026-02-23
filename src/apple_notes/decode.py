"""Gzip + protobuf decoding of Apple Notes content blobs."""

import zlib

from .proto.notestore_pb2 import NoteStoreProto


def decode_note_content(content: bytes | None) -> str:
    """Decode a ZICNOTEDATA.ZDATA blob into plain text.

    The blob is gzip-compressed protobuf. The message hierarchy is:
    NoteStoreProto → Document → Note → note_text
    """
    if not content:
        return ""

    if not content.startswith(b"\x1f\x8b"):
        return ""

    decompressed = zlib.decompress(content, 16 + zlib.MAX_WBITS)

    note_store = NoteStoreProto()
    note_store.ParseFromString(decompressed)

    if note_store.document and note_store.document.note:
        return note_store.document.note.note_text or ""

    return ""


def _parse_note(content: bytes | None):
    """Decompress + parse protobuf, returning the Note message or None."""
    if not content or not content.startswith(b"\x1f\x8b"):
        return None
    decompressed = zlib.decompress(content, 16 + zlib.MAX_WBITS)
    ns = NoteStoreProto()
    ns.ParseFromString(decompressed)
    if ns.document and ns.document.note:
        return ns.document.note
    return None


# ── style_type constants ────────────────────────────────────────────────
_TITLE = 0
_HEADING = 1
_SUBHEADING = 2
_MONOSPACED = 4
_BULLET = 100
_DASH = 101
_NUMBERED = 102
_CHECKLIST = 103


def decode_note_to_markdown(content: bytes | None, skip_title: bool = True) -> str:
    """Decode a ZICNOTEDATA.ZDATA blob into Markdown, preserving formatting.

    Walks attribute_run entries to reconstruct headings, lists, bold/italic,
    strikethrough, links, checklists, and code blocks.

    Args:
        content: Raw gzip+protobuf blob from ZICNOTEDATA.ZDATA.
        skip_title: Drop the first paragraph (the note title) since it
                    duplicates the metadata title field.
    """
    note = _parse_note(content)
    if not note:
        return ""

    text = note.note_text or ""
    runs = note.attribute_run
    if not runs or not text:
        return text

    # ── Step 1: split runs into paragraphs ──────────────────────────
    # Each paragraph = ([(text_chunk, run), ...], ParagraphStyle | None)
    paragraphs: list[tuple[list[tuple[str, object]], object | None]] = []
    cur_segs: list[tuple[str, object]] = []
    cur_style = None

    pos = 0
    for run in runs:
        run_style = run.paragraph_style if run.HasField("paragraph_style") else None

        chunk = text[pos : pos + run.length]
        pos += run.length

        parts = chunk.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                # newline boundary → finish paragraph
                paragraphs.append((cur_segs, cur_style))
                cur_segs = []
                cur_style = None
            if part:
                cur_segs.append((part, run))
            # capture the most specific paragraph style from any run
            if run_style and (cur_style is None or run_style.style_type != -1):
                cur_style = run_style

    if cur_segs:
        paragraphs.append((cur_segs, cur_style))

    # optionally drop the first paragraph (title)
    if skip_title and paragraphs:
        paragraphs = paragraphs[1:]

    # ── Step 2: render each paragraph to Markdown ───────────────────
    _LIST_STYLES = {_BULLET, _DASH, _NUMBERED, _CHECKLIST}
    md_lines: list[str] = []
    in_code = False
    prev_st = -1

    for segs, style in paragraphs:
        st = style.style_type if style else -1

        # Build inline content, merging adjacent runs with same formatting
        raw_parts: list[tuple[str, int, int, int, str]] = []  # (text, weight, strike, ul, link)
        for seg_text, run in segs:
            seg_text = seg_text.replace("\ufffc", "")
            if not seg_text:
                continue
            key = (run.font_weight, run.strikethrough, run.underlined, run.link or "")
            if raw_parts and (raw_parts[-1][1], raw_parts[-1][2], raw_parts[-1][3], raw_parts[-1][4]) == key:
                # merge with previous segment
                raw_parts[-1] = (raw_parts[-1][0] + seg_text, *key)
            else:
                raw_parts.append((seg_text, *key))

        # Skip empty paragraphs that carry a non-default style
        if not raw_parts:
            if st == -1 or st is None:
                # preserve intentional blank lines
                if in_code:
                    md_lines.append("")
                else:
                    md_lines.append("")
            # otherwise drop empty styled paragraphs (empty headings, list items, etc.)
            continue

        # code-fence transitions
        if st == _MONOSPACED and not in_code:
            md_lines.append("```")
            in_code = True
        elif st != _MONOSPACED and in_code:
            md_lines.append("```")
            in_code = False

        # apply inline formatting
        parts: list[str] = []
        for seg_text, wt, strike, ul, link in raw_parts:
            if st == _MONOSPACED:
                parts.append(seg_text)
                continue
            fmt = seg_text
            if wt == 1:
                fmt = f"**{fmt}**"
            elif wt == 2:
                fmt = f"*{fmt}*"
            elif wt >= 3:
                fmt = f"***{fmt}***"
            if strike:
                fmt = f"~~{fmt}~~"
            if link:
                fmt = f"[{fmt}]({link})"
            parts.append(fmt)

        inline = "".join(parts)

        # paragraph-level prefix
        is_heading = st in (_TITLE, _HEADING, _SUBHEADING)
        is_list = st in _LIST_STYLES

        # blank line after a list block when transitioning to non-list
        if prev_st in _LIST_STYLES and not is_list and md_lines and md_lines[-1] != "":
            md_lines.append("")

        # ensure exactly one blank line before headings
        if is_heading and md_lines and md_lines[-1] != "":
            md_lines.append("")

        if st == _TITLE:
            md_lines.append(f"# {inline}")
        elif st == _HEADING:
            md_lines.append(f"## {inline}")
        elif st == _SUBHEADING:
            md_lines.append(f"### {inline}")
        elif st == _MONOSPACED:
            md_lines.append(inline)
        elif st in (_BULLET, _DASH):
            indent = "  " * (style.indent_amount if style else 0)
            md_lines.append(f"{indent}- {inline}")
        elif st == _NUMBERED:
            indent = "  " * (style.indent_amount if style else 0)
            md_lines.append(f"{indent}1. {inline}")
        elif st == _CHECKLIST:
            indent = "  " * (style.indent_amount if style else 0)
            done = style.HasField("checklist") and style.checklist.done == 1 if style else False
            marker = "[x]" if done else "[ ]"
            md_lines.append(f"{indent}- {marker} {inline}")
        else:
            md_lines.append(inline)

        # ensure exactly one blank line after headings
        if is_heading:
            md_lines.append("")

        prev_st = st

    if in_code:
        md_lines.append("```")

    return "\n".join(md_lines)
