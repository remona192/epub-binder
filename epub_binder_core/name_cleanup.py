from __future__ import annotations

from pathlib import Path
import re
import unicodedata


_EXT_RE = re.compile(r"\.(?:epub|txt|zip|7z)$", re.IGNORECASE)
_AUTHOR_PREFIX_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(.+)$")
_UNKNOWN_AUTHORS = {"", "미상", "unknown", "untitled"}


def clean_name_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def strip_extension_name(value: str) -> str:
    return _EXT_RE.sub("", Path(str(value or "")).name)


def split_bracket_author(value: str) -> tuple[str, str]:
    text = clean_name_text(value)
    match = _AUTHOR_PREFIX_RE.match(text)
    if not match:
        return "", text
    return clean_name_text(match.group(1)), clean_name_text(match.group(2))


def _strip_duplicate_author_prefix(title: str, author: str) -> str:
    title = clean_name_text(title)
    author = clean_name_text(author)
    if not title or not author or author.lower() in _UNKNOWN_AUTHORS:
        return title

    compact_author = re.sub(r"[\s_]+", "", author)
    compact_title = re.sub(r"[\s_]+", "", title)
    if not compact_author or not compact_title.lower().startswith(compact_author.lower()):
        return title

    # Prefer removing a clear token prefix such as "뇌조_..." or "지나83 ...".
    pattern = rf"^\s*{re.escape(author)}[\s_\-–—:：]+"
    stripped = re.sub(pattern, "", title, count=1, flags=re.IGNORECASE).strip()
    return clean_name_text(stripped or title)


def humanize_series_title(title: str, author: str = "") -> str:
    """Make a filename-derived title suitable for display and EPUB metadata."""
    title_author, body = split_bracket_author(strip_extension_name(title))
    author = clean_name_text(author or title_author)
    text = _strip_duplicate_author_prefix(body, author)

    # Common txt-source names use underscores as word separators. Preserve
    # trailing episode ranges as "1-216" instead of "1 216" or "1216".
    text = re.sub(
        r"(?<!\d)(\d{1,5})\s*[_~]\s*(\d{1,5})(?!\d)",
        r"\1-\2",
        text,
    )
    text = text.replace("_", " ")
    text = re.sub(
        r"(?<!\d)(\d{1,5})\s*[-~]\s*(\d{1,5})(?!\d)",
        r"\1-\2",
        text,
    )
    return clean_name_text(text)


def clean_series_title_author(title: str, author: str = "") -> tuple[str, str]:
    bracket_author, body = split_bracket_author(strip_extension_name(title))
    clean_author = clean_name_text(author)
    if clean_author.lower() in _UNKNOWN_AUTHORS and bracket_author:
        clean_author = bracket_author
    clean_title = humanize_series_title(body, clean_author or bracket_author)
    return clean_title, clean_author or "미상"
