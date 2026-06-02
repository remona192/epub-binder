from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape
import io
import re
import zipfile

from .epub_archive import apply_epub_timestamp, compression_for, normalize_zip_path
from .epub_cleanup import remove_invisible_chars
from .merge_plan import NcxNavEntry, render_ncx_nav_point


ProgressCallback = Callable[["MergeProgressEvent"], None]


@dataclass(frozen=True)
class MergeOptions:
    title: str = "Merged EPUB"
    add_toc: bool = True
    toc_titles: tuple[str, ...] = ()
    custom_cover: bytes | None = None
    custom_cover_ext: str = ".jpg"
    timestamp: tuple[int, int, int, int, int, int] | None = None
    strip_invisible: bool = True


@dataclass(frozen=True)
class MergeProgressEvent:
    percent: int
    message: str = ""
    tag: str = "info"
    index: int = 0


@dataclass(frozen=True)
class MergeResult:
    ok: bool
    output_path: Path
    input_count: int
    spine_count: int
    warnings: tuple[str, ...] = field(default_factory=tuple)


def _read_text(zf: zipfile.ZipFile, name: str) -> str:
    data = zf.read(name)
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _opf_path(zf: zipfile.ZipFile) -> str:
    container = _read_text(zf, "META-INF/container.xml")
    match = re.search(r"full-path=[\"']([^\"']+\.opf)[\"']", container, re.IGNORECASE)
    if not match:
        raise ValueError("OPF path not found")
    return match.group(1)


def _manifest(opf_raw: str) -> dict[str, tuple[str, str]]:
    items: dict[str, tuple[str, str]] = {}
    for match in re.finditer(r"<item\s([^>]*?)\s*/?>", opf_raw, re.IGNORECASE):
        attrs = match.group(1)
        item_id = re.search(r"\bid=[\"']([^\"']+)[\"']", attrs)
        href = re.search(r"\bhref=[\"']([^\"']+)[\"']", attrs)
        media = re.search(r"\bmedia-type=[\"']([^\"']+)[\"']", attrs)
        if item_id and href:
            items[item_id.group(1)] = (href.group(1), media.group(1) if media else "")
    return items


def _spine(opf_raw: str) -> list[str]:
    return re.findall(r"<itemref\s[^>]*idref=[\"']([^\"']+)[\"']", opf_raw, re.IGNORECASE)


def _media_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".xhtml": "application/xhtml+xml",
        ".html": "application/xhtml+xml",
        ".htm": "application/xhtml+xml",
        ".css": "text/css",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def _write_epub(output_path: Path, entries: list[tuple[str, bytes]], timestamp: tuple | None) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name)
            if timestamp:
                info.date_time = timestamp
            info.compress_type = compression_for(name)
            zf.writestr(info, data)
    data = buf.getvalue()
    if timestamp:
        data = apply_epub_timestamp(data, timestamp)
    output_path.write_bytes(data)


def merge_epubs(
    inputs: Sequence[str | Path],
    output_path: str | Path,
    options: MergeOptions | None = None,
    progress: ProgressCallback | None = None,
) -> MergeResult:
    """Merge spine XHTML documents into a simple, valid EPUB.

    This service is intentionally conservative. The legacy GUI still owns the
    advanced production merge path until that behavior is fully covered by
    regression tests.
    """
    options = options or MergeOptions()
    output = Path(output_path)
    input_paths = [Path(path) for path in inputs]
    if not input_paths:
        raise ValueError("at least one EPUB input is required")

    warnings: list[str] = []
    content_entries: list[tuple[str, bytes, str, str]] = []

    for index, path in enumerate(input_paths):
        if progress:
            progress(MergeProgressEvent(int(index / len(input_paths) * 80), f"reading {path.name}", index=index))
        epub_bytes = path.read_bytes()
        if options.strip_invisible:
            epub_bytes, _, _ = remove_invisible_chars(epub_bytes)
        with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
            opf = _opf_path(zf)
            opf_raw = _read_text(zf, opf)
            opf_dir = str(Path(opf).parent)
            if opf_dir == ".":
                opf_dir = ""
            manifest = _manifest(opf_raw)
            for spine_index, item_id in enumerate(_spine(opf_raw), start=1):
                href_media = manifest.get(item_id)
                if not href_media:
                    warnings.append(f"{path.name}: missing manifest item {item_id}")
                    continue
                href, media_type = href_media
                if media_type not in {"application/xhtml+xml", "text/html"}:
                    continue
                source = normalize_zip_path(opf_dir, href)
                try:
                    data = zf.read(source)
                except KeyError:
                    warnings.append(f"{path.name}: missing spine file {source}")
                    continue
                out_name = f"OEBPS/Text/vol{index + 1:03d}_{spine_index:04d}{Path(source).suffix or '.xhtml'}"
                label = options.toc_titles[index] if index < len(options.toc_titles) else path.stem
                content_entries.append((out_name, data, label, "application/xhtml+xml"))

    if not content_entries:
        raise ValueError("no XHTML spine content found")

    manifest_lines = []
    spine_lines = []
    nav_point_lines: list[str] = []
    entries: list[tuple[str, bytes]] = [
        ("mimetype", b"application/epub+zip"),
        (
            "META-INF/container.xml",
            b"""<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        ),
    ]

    if options.custom_cover:
        ext = options.custom_cover_ext if options.custom_cover_ext.startswith(".") else f".{options.custom_cover_ext}"
        cover_name = f"OEBPS/Images/cover{ext.lower()}"
        entries.append((cover_name, options.custom_cover))
        manifest_lines.append(
            f'    <item id="cover-image" href="Images/cover{ext.lower()}" media-type="{_media_type(cover_name)}"/>'
        )

    for idx, (name, data, label, media_type) in enumerate(content_entries, start=1):
        item_id = f"item{idx:04d}"
        href = name.removeprefix("OEBPS/")
        entries.append((name, data))
        manifest_lines.append(f'    <item id="{item_id}" href="{escape(href)}" media-type="{media_type}"/>')
        spine_lines.append(f'    <itemref idref="{item_id}"/>')
        nav_point_lines.extend(
            render_ncx_nav_point(
                NcxNavEntry(f"navPoint-{idx}", label, href, idx),
                indent=4,
            )
        )

    if options.add_toc:
        manifest_lines.append('    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')

    title = escape(options.title or "Merged EPUB")
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:language>ko</dc:language>
    <dc:identifier id="BookId">epub-binder-merged</dc:identifier>
  </metadata>
  <manifest>
{chr(10).join(manifest_lines)}
  </manifest>
  <spine toc="ncx">
{chr(10).join(spine_lines)}
  </spine>
</package>"""
    entries.append(("OEBPS/content.opf", opf.encode("utf-8")))

    if options.add_toc:
        ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="epub-binder-merged"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
{chr(10).join(nav_point_lines)}
  </navMap>
</ncx>"""
        entries.append(("OEBPS/toc.ncx", ncx.encode("utf-8")))

    if progress:
        progress(MergeProgressEvent(90, "writing output"))
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_epub(output, entries, options.timestamp)
    if progress:
        progress(MergeProgressEvent(100, "done"))
    return MergeResult(True, output, len(input_paths), len(content_entries), tuple(warnings))
