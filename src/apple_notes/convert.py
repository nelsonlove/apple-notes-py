"""HTML ↔ Markdown conversion for Apple Notes content."""

import markdown
from markdownify import markdownify


def html_to_markdown(html: str) -> str:
    """Convert HTML to Markdown using markdownify."""
    return markdownify(html, heading_style="ATX", strip=["img"]).strip()


def markdown_to_html(md: str) -> str:
    """Convert Markdown to HTML using the markdown library."""
    return markdown.markdown(md)
