from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import io
import re
import zipfile

from .epub_archive import normalize_zip_path
from .toc import is_skip_page as default_is_skip_page


SkipPageDetector = Callable[[str, bytes], str | None]

_FULL_PATTERNS = {
    b"\xe2\x80\x8b": "U+200B",
    b"\xe2\x80\x8c": "U+200C",
    b"\xe2\x80\x8d": "U+200D",
    b"\xe2\x80\x8e": "U+200E",
    b"\xe2\x80\x8f": "U+200F",
    b"\xe1\xa0\x8e": "U+180E",
    b"\xe2\x81\xa0": "U+2060",
    b"\xe2\x81\xa1": "U+2061",
    b"\xe2\x81\xa2": "U+2062",
    b"\xe2\x81\xa3": "U+2063",
    b"\xe2\x81\xa4": "U+2064",
    b"\xe2\x81\xa6": "U+2066",
    b"\xe2\x81\xa7": "U+2067",
    b"\xe2\x81\xa8": "U+2068",
    b"\xe2\x81\xa9": "U+2069",
    b"\xe2\x81\xaa": "U+206A",
    b"\xe2\x81\xab": "U+206B",
    b"\xe2\x81\xac": "U+206C",
    b"\xe2\x81\xad": "U+206D",
    b"\xe2\x81\xae": "U+206E",
    b"\xe2\x81\xaf": "U+206F",
    b"\xcd\x8f": "U+034F",
    b"\xef\xbb\xbf": "U+FEFF",
    b"\xef\xbf\xb9": "U+FFF9",
    b"\xef\xbf\xba": "U+FFFA",
    b"\xef\xbf\xbb": "U+FFFB",
    b"\xf3\xa0\x80\x81": "U+E0001",
}
_TAGS_BLOCK = re.compile(b"\xf3\xa0[\x81-\x82][\x80-\xbf]|\xf3\xa0\x80[\xa0-\xbf]")
_BOOK_TOKEN = re.compile(rb"[^\r\n]*name=[\"']book-token[\"'][^\r\n]*(\r\n|\r|\n)?")
_TARGET_EXTS = (".html", ".xhtml", ".htm", ".xml", ".ncx", ".css")


@dataclass(frozen=True)
class StripOptions:
    strip_pages: bool = True


@dataclass(frozen=True)
class StripResult:
    cleaned_bytes: bytes
    removed_pages: tuple[tuple[str, str], ...]
    chars_removed: int
    char_counts: dict[str, int]


def remove_invisible_chars(epub_bytes: bytes) -> tuple[bytes, int, dict[str, int]]:
    """Remove invisible Unicode bytes and book-token metadata from EPUB content."""
    orig = zipfile.ZipFile(io.BytesIO(epub_bytes), "r")
    mime_dt = None
    for info in orig.infolist():
        if info.filename == "mimetype":
            mime_dt = info.date_time
            break

    cleaned_data: dict[str, bytes] = {}
    char_counts: dict[str, int] = {}

    for item in orig.infolist():
        fl = item.filename.lower()
        file_data = orig.read(item.filename)

        if item.filename.startswith("META-INF/"):
            continue

        if fl.endswith(".opf"):
            cleaned, n = _BOOK_TOKEN.subn(b"", file_data)
            if n:
                char_counts["book-token"] = char_counts.get("book-token", 0) + n
                cleaned_data[item.filename] = cleaned
            continue

        if not any(fl.endswith(ext) for ext in _TARGET_EXTS):
            continue

        modified = False
        for pattern, name in _FULL_PATTERNS.items():
            count = file_data.count(pattern)
            if count:
                char_counts[name] = char_counts.get(name, 0) + count
                file_data = file_data.replace(pattern, b"")
                modified = True

        matches = _TAGS_BLOCK.findall(file_data)
        if matches:
            char_counts["U+E0020~"] = char_counts.get("U+E0020~", 0) + len(matches)
            file_data = _TAGS_BLOCK.sub(b"", file_data)
            modified = True

        if modified:
            cleaned_data[item.filename] = file_data

    orig.close()
    removed_count = sum(count for name, count in char_counts.items() if name != "book-token")

    orig2 = zipfile.ZipFile(io.BytesIO(epub_bytes), "r")
    new_buf = io.BytesIO()
    new_zip = zipfile.ZipFile(new_buf, "w")

    for item in orig2.infolist():
        data = cleaned_data.get(item.filename)
        if data is None:
            data = orig2.read(item.filename)
        if item.filename != "mimetype" and mime_dt:
            item.date_time = mime_dt
        item.compress_type = zipfile.ZIP_STORED if item.filename == "mimetype" else zipfile.ZIP_DEFLATED
        new_zip.writestr(item, data)

    new_zip.close()
    orig2.close()
    return new_buf.getvalue(), removed_count, char_counts


def scan_invisible_chars(epub_bytes: bytes) -> tuple[int, dict[str, int]]:
    """Count invisible Unicode bytes without modifying the EPUB."""
    try:
        orig = zipfile.ZipFile(io.BytesIO(epub_bytes), "r")
    except Exception:
        return 0, {}
    char_counts: dict[str, int] = {}
    for item in orig.infolist():
        fl = item.filename.lower()
        if item.filename.startswith("META-INF/"):
            continue
        try:
            file_data = orig.read(item.filename)
        except Exception:
            continue
        if fl.endswith(".opf"):
            count = len(_BOOK_TOKEN.findall(file_data))
            if count:
                char_counts["book-token"] = char_counts.get("book-token", 0) + count
            continue
        if not any(fl.endswith(ext) for ext in _TARGET_EXTS):
            continue
        for pattern, name in _FULL_PATTERNS.items():
            count = file_data.count(pattern)
            if count:
                char_counts[name] = char_counts.get(name, 0) + count
        matches = _TAGS_BLOCK.findall(file_data)
        if matches:
            char_counts["U+E0020~"] = char_counts.get("U+E0020~", 0) + len(matches)
    orig.close()
    total = sum(count for name, count in char_counts.items() if name != "book-token")
    return total, char_counts


def strip_epub(
    epub_bytes: bytes,
    options: StripOptions | None = None,
    skip_page_detector: SkipPageDetector | None = None,
) -> StripResult:
    options = options or StripOptions()
    detector = skip_page_detector or default_is_skip_page
    cleaned, chars_removed, char_counts = remove_invisible_chars(epub_bytes)

    if not options.strip_pages:
        return StripResult(cleaned, (), chars_removed, char_counts)

    try:
        out_buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(cleaned), "r") as zin:
            try:
                container_xml = zin.read("META-INF/container.xml").decode("utf-8", "replace")
                opf_match = re.search(r"full-path=[\"']([^\"']+\.opf)[\"']", container_xml, re.IGNORECASE)
                if not opf_match:
                    return StripResult(cleaned, (), chars_removed, char_counts)
                opf_path = opf_match.group(1)
            except Exception:
                return StripResult(cleaned, (), chars_removed, char_counts)

            opf_dir = str(Path(opf_path).parent)
            if opf_dir == ".":
                opf_dir = ""
            opf_content = zin.read(opf_path).decode("utf-8", "replace")

            manifest: dict[str, str] = {}
            for match in re.finditer(r"<item\s([^>]*?)\s*/?>", opf_content, re.IGNORECASE):
                attrs = match.group(1)
                id_match = re.search(r"\bid=[\"']([^\"']+)[\"']", attrs)
                href_match = re.search(r"\bhref=[\"']([^\"']+)[\"']", attrs)
                if id_match and href_match:
                    manifest[id_match.group(1)] = href_match.group(1)

            spine_ids = re.findall(r"<itemref\s[^>]*idref=[\"']([^\"']+)[\"']", opf_content, re.IGNORECASE)
            skip_zip_paths: set[str] = set()
            removed_pages: list[tuple[str, str]] = []
            for item_id in spine_ids:
                href = manifest.get(item_id)
                if not href:
                    continue
                zip_path = normalize_zip_path(opf_dir, href)
                try:
                    file_data = zin.read(zip_path)
                except Exception:
                    continue
                reason = detector(href, file_data)
                if reason:
                    if reason == "cover":
                        continue
                    skip_zip_paths.add(zip_path)
                    removed_pages.append((Path(href).name, reason))

            if not skip_zip_paths:
                return StripResult(cleaned, (), chars_removed, char_counts)

            skip_ids = {
                item_id
                for item_id, href in manifest.items()
                if normalize_zip_path(opf_dir, href) in skip_zip_paths
            }

            def delete_spine(match: re.Match[str]) -> str:
                idref_match = re.search(r"idref=[\"']([^\"']+)[\"']", match.group(0))
                return "" if idref_match and idref_match.group(1) in skip_ids else match.group(0)

            def delete_manifest(match: re.Match[str]) -> str:
                id_match = re.search(r"\bid=[\"']([^\"']+)[\"']", match.group(1))
                return "" if id_match and id_match.group(1) in skip_ids else match.group(0)

            new_opf = re.sub(r"<itemref\s[^>]*/>", delete_spine, opf_content, flags=re.IGNORECASE)
            new_opf = re.sub(r"<itemref\s[^>]*>[^<]*</itemref>", delete_spine, new_opf, flags=re.IGNORECASE)
            new_opf = re.sub(r"<item\s([^>]*?)\s*/?>", delete_manifest, new_opf, flags=re.IGNORECASE)

            with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    norm = item.filename.replace("\\", "/")
                    if norm in skip_zip_paths:
                        continue
                    if norm == opf_path:
                        zout.writestr(item, new_opf.encode("utf-8"))
                    elif norm == "mimetype":
                        zout.writestr(item, zin.read(item.filename), compress_type=zipfile.ZIP_STORED)
                    else:
                        zout.writestr(item, zin.read(item.filename))

        return StripResult(out_buf.getvalue(), tuple(removed_pages), chars_removed, char_counts)
    except Exception:
        return StripResult(cleaned, (), chars_removed, char_counts)


def strip_epub_in_memory(
    epub_bytes: bytes,
    skip_page_detector: SkipPageDetector | None = None,
) -> tuple[bytes, list[tuple[str, str]], int, dict[str, int]]:
    result = strip_epub(epub_bytes, skip_page_detector=skip_page_detector)
    return result.cleaned_bytes, list(result.removed_pages), result.chars_removed, result.char_counts
