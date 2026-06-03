"""Shared HTML-to-Markdown conversion utility.

Uses ``html2text`` for high-quality conversion with proper handling of
headings, lists, emphasis, links, tables, and code blocks.
"""

from __future__ import annotations

import html2text


def html_to_markdown(html: str) -> str:
    """Convert an HTML string to clean Markdown.

    Args:
        html: Input HTML content.

    Returns:
        Markdown-formatted string.
    """
    h = html2text.HTML2Text()
    h.body_width = 0  # Don't wrap lines
    h.unicode_snob = True  # Use unicode instead of ascii approximations
    h.protect_links = True
    h.wrap_links = False
    h.single_line_break = False
    h.mark_code = True
    h.ignore_images = False
    h.ignore_emphasis = False
    h.ignore_links = False
    return h.handle(html).strip()
