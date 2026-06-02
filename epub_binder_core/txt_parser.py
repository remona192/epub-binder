from __future__ import annotations

from pathlib import Path
import re

from .name_cleanup import clean_series_title_author


def decode_txt_bytes(raw: bytes) -> str:
    """Decode TXT bytes with deterministic Korean-friendly fallbacks."""
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16")
        except Exception:
            pass
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    try:
        from charset_normalizer import from_bytes

        detected = from_bytes(raw).best()
        if detected:
            return str(detected)
    except Exception:
        pass
    for encoding in ("utf-16",):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def extract_txt_metadata(filename: str, text: str = "") -> tuple[str, str]:
    """Extract ``(title, author)`` from a filename and optional TXT header."""
    name = Path(filename).stem
    title, author = name, "미상"

    match = re.match(r"^\s*\[([^\]]+)\]\s*(.+)$", name)
    if match:
        author = match.group(1).strip()
        title = match.group(2).strip()
    elif " - " in name:
        left, right = name.split(" - ", 1)
        title, author = left.strip(), right.strip()
    elif re.search(r"\sby\s", name, re.IGNORECASE):
        left, right = re.split(r"\sby\s", name, maxsplit=1, flags=re.IGNORECASE)
        title, author = left.strip(), right.strip()

    if text:
        head = text[:1500]
        title_match = re.search(
            r"^\s*(?:제\s*목|Title)\s*[:：]\s*(.+)$",
            head,
            re.MULTILINE | re.IGNORECASE,
        )
        if title_match and title == name:
            title = title_match.group(1).strip()

        author_match = re.search(
            r"^\s*(?:작\s*가|작\s*자|지은이|Author)\s*[:：]\s*(.+)$",
            head,
            re.MULTILINE | re.IGNORECASE,
        )
        if author_match and author == "미상":
            author = author_match.group(1).strip()

        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        at_match = re.match(r"^([^@\n]{1,80}?)@([^\s@][^\n]{0,60})$", first_line)
        if at_match:
            title_at = at_match.group(1).strip()
            author_at = at_match.group(2).strip()
            if title == name and title_at:
                title = title_at
            if author == "미상" and author_at:
                author = author_at
    return clean_series_title_author(title, author)
