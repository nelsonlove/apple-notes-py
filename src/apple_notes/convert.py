"""HTML ↔ Markdown conversion for Apple Notes content."""

import re

import markdown
from markdownify import markdownify


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify."""
    return markdownify(html, heading_style="ATX", strip=["img"]).strip()


def markdown_to_html(md: str) -> str:
    """Convert Markdown to HTML using the markdown library."""
    html = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )
    # Apple Notes collapses whitespace between block elements.
    # Add <br> before h2-h6 so subheadings get breathing room.
    html = re.sub(r"(<h[2-6][ >])", r"<br>\1", html)
    html = re.sub(r"(</h[2-6]>)", r"\1<br>", html)
    return html
