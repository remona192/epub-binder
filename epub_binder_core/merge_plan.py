from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from html import escape as html_escape, unescape
from pathlib import Path
import re
from typing import Callable
from urllib.parse import unquote
from xml.sax.saxutils import escape as xml_escape, quoteattr


SkipPageDetector = Callable[[str, bytes], str | None]


@dataclass(frozen=True)
class ImagePrunePlan:
    referenced_basenames: frozenset[str]
    protected_basenames: frozenset[str]
    remove_manifest_ids: frozenset[str]
    removable_file_basenames: frozenset[str]


@dataclass(frozen=True)
class NcxNavEntry:
    nav_id: str
    label: str
    src: str
    play_order: int
    children: tuple["NcxNavEntry", ...] = ()

    def __init__(
        self,
        nav_id: str,
        label: str,
        src: str,
        play_order: int,
        children: Iterable["NcxNavEntry"] = (),
    ) -> None:
        object.__setattr__(self, "nav_id", str(nav_id))
        object.__setattr__(self, "label", str(label))
        object.__setattr__(self, "src", str(src))
        object.__setattr__(self, "play_order", int(play_order))
        object.__setattr__(self, "children", tuple(children))


@dataclass(frozen=True)
class VolumeChapterTocPlan:
    groups: dict[int, tuple[tuple[int, str, str, int], ...]]
    ungrouped: tuple[tuple[int, str, str], ...]
    filename_chapter_numbers: dict[int, int]
    filename_volume_numbers: dict[int, int]
    chapter_only_filename_numbers: dict[int, int]
    filename_toc_labels: dict[int, str]
    force_filename_toc: bool
    use_grouping: bool
    use_flat: bool


@dataclass(frozen=True)
class NcxBuildResult:
    entries: tuple[NcxNavEntry, ...]
    next_play_order: int
    next_book_index: int


@dataclass(frozen=True)
class TocPageLink:
    href: str
    label: str
    children: tuple["TocPageLink", ...] = ()

    def __init__(
        self,
        href: str,
        label: str,
        children: Iterable["TocPageLink"] = (),
    ) -> None:
        object.__setattr__(self, "href", str(href))
        object.__setattr__(self, "label", str(label))
        object.__setattr__(self, "children", tuple(children))


_IMG_SRC_RE = re.compile(r"<img\b[^>]+\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
_IMAGE_ATTR_RE = re.compile(
    r"(?:src|href)=[\"']([^\"']+\.(?:jpg|jpeg|png|gif|webp))(?:[?#][^\"']*)?[\"']",
    re.IGNORECASE,
)
_CSS_IMAGE_URL_RE = re.compile(
    r"url\([\"']?([^\"')]+\.(?:jpg|jpeg|png|gif|webp))(?:[?#][^\"')]*)?[\"']?\)",
    re.IGNORECASE,
)
_IMG_TAG_RE = re.compile(r"<img\b", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[^>]*>.*?</style>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_FLAT_TOC_NCX_INDEX_RE = re.compile(
    r"^(?:\ucc28\ub840|\ubaa9\ucc28|contents?|table\s*of\s*contents?)$",
    re.IGNORECASE,
)
_OPF_ID_SAFE_RE = re.compile(r"[^a-zA-Z0-9_\-]")


def _decode_markup(html_or_bytes: str | bytes) -> str:
    if isinstance(html_or_bytes, str):
        return html_or_bytes
    return html_or_bytes.decode("utf-8", "replace")


def _image_ref_basename(ref: str) -> str:
    ref = unescape(str(ref))
    ref = unquote(ref.split("#", 1)[0].split("?", 1)[0])
    return Path(ref.replace("\\", "/")).name.lower()


def cover_asset_basenames(html_or_bytes: str | bytes) -> frozenset[str]:
    """Return lower-case image source basenames referenced by markup."""

    raw = _decode_markup(html_or_bytes)
    names: set[str] = set()
    for src in _IMG_SRC_RE.findall(raw):
        name = _image_ref_basename(src)
        if name:
            names.add(name)
    return frozenset(names)


def referenced_image_basenames(markup_or_css: str | bytes | Iterable[str | bytes]) -> frozenset[str]:
    """Collect lower-case image basenames referenced by kept XHTML/CSS."""

    if isinstance(markup_or_css, (str, bytes)):
        items = (markup_or_css,)
    else:
        items = markup_or_css
    refs: set[str] = set()
    for item in items:
        raw = _decode_markup(item)
        for match in _IMAGE_ATTR_RE.finditer(raw):
            name = _image_ref_basename(match.group(1))
            if name:
                refs.add(name)
        for match in _CSS_IMAGE_URL_RE.finditer(raw):
            name = _image_ref_basename(match.group(1))
            if name:
                refs.add(name)
    return frozenset(refs)


def _manifest_iter(manifest):
    if isinstance(manifest, Mapping):
        for item_id, value in manifest.items():
            href, media_type = value[:2]
            yield str(item_id), str(href), str(media_type)
        return
    for item in manifest:
        item_id = getattr(item, "id", None)
        href = getattr(item, "href", None)
        media_type = getattr(item, "media_type", None)
        if item_id is None and isinstance(item, tuple) and len(item) >= 3:
            item_id, href, media_type = item[:3]
        if item_id is None or href is None:
            continue
        yield str(item_id), str(href), str(media_type or "")


def sanitize_opf_id(item_id: str) -> str:
    return _OPF_ID_SAFE_RE.sub("_", str(item_id))


def merge_series_name_from_title(title: str) -> str:
    series_name = re.sub(r"\s*\d+[-~]\d+\s*[\uad8c\ud654\ubd80]?\s*$", "", title or "")
    series_name = re.sub(r"\s*\d+\s*[\uad8c\ud654\ubd80]\s*$", "", series_name).strip()
    return series_name


def infer_creator_from_title_or_filename(title: str, first_input_stem: str = "") -> str:
    match = re.match(r"^\[([^\]]+)\]", title or "")
    if match:
        return match.group(1).strip()
    match = re.match(r"^_([^_]{1,10})__", first_input_stem or "")
    if match:
        return match.group(1).strip()
    return ""


def plan_volume_chapter_toc(
    toc_entries: Iterable[tuple[int, str, str]],
    input_filenames: Iterable[str],
    *,
    filename_toc_labels: Mapping[int, str] | None = None,
    flat_toc: bool = False,
    force_filename_toc: bool = False,
) -> VolumeChapterTocPlan:
    """Analyze legacy merge TOC entries for volume/chapter grouping decisions."""

    filenames = tuple(input_filenames)
    filename_labels = dict(filename_toc_labels or {})
    groups: dict[int, list[tuple[int, str, str, int]]] = {}
    ungrouped: list[tuple[int, str, str]] = []
    filename_chapters: dict[int, int] = {}
    filename_volumes: dict[int, int] = {}
    chapter_only: dict[int, int] = {}

    for epub_index, label, href in toc_entries:
        stem = Path(filenames[epub_index]).stem if 0 <= epub_index < len(filenames) else ""
        volume_match = re.search(r"(\d+)\s*\uad8c", stem)
        chapter_match = re.search(r"(\d+)\s*\ud654", stem)
        if chapter_match:
            chapter_only[epub_index] = int(chapter_match.group(1))
        if volume_match and chapter_match:
            volume_number = int(volume_match.group(1))
            chapter_number = int(chapter_match.group(1))
            filename_chapters[epub_index] = chapter_number
            filename_volumes[epub_index] = volume_number
            groups.setdefault(volume_number, []).append((epub_index, label, href, chapter_number))
        else:
            ungrouped.append((epub_index, label, href))

    frozen_groups = {
        volume_number: tuple(entries)
        for volume_number, entries in groups.items()
    }
    return VolumeChapterTocPlan(
        groups=frozen_groups,
        ungrouped=tuple(ungrouped),
        filename_chapter_numbers=filename_chapters,
        filename_volume_numbers=filename_volumes,
        chapter_only_filename_numbers=chapter_only,
        filename_toc_labels=filename_labels,
        force_filename_toc=bool(force_filename_toc),
        use_grouping=(not flat_toc) and any(len(entries) >= 2 for entries in frozen_groups.values()),
        use_flat=bool(flat_toc and filename_chapters),
    )


def volume_parent_label(volume_number: int, sample_label: str) -> str:
    """Return the legacy parent label for a grouped volume/chapter TOC node."""

    label = re.sub(r"\s*\uc81c?\s*\d+\s*\ud654.*$", "", sample_label or "").strip()
    if not re.search(rf"(?<!\d){int(volume_number)}\s*\uad8c", label):
        label = re.sub(r"\s*\d+\s*\uad8c\s*$", "", label).strip()
        label = f"{label} {int(volume_number)}\uad8c".strip()
    return label


def flat_volume_chapter_label(label: str, chapter_number: int | None) -> str:
    """Append the filename chapter number for legacy flat TOC labels when needed."""

    if chapter_number is not None and not re.search(r"\d+\s*\ud654", label or ""):
        return f"{label} {int(chapter_number)}\ud654".strip()
    return label


def has_multi_volume_label_marker(label: str) -> bool:
    """Return whether a legacy TOC label should count as a multi-volume marker."""

    text = str(label or "")
    if re.search(r"\d+\s*[\uad8c\ubd80]|\uc678\uc804|\ubc88\uc678|\ud2b9\uc804", text):
        return True
    if re.search(r"\d+\s*\ud654", text):
        return False
    return bool(re.search(r"\s\d+\s*$", text))


def should_use_multi_volume_ncx(
    toc_entries: Iterable[tuple[int, str, str]],
    spine_epub_indices: Iterable[int],
    *,
    flat_toc: bool,
    volume_chapter_grouping: bool,
) -> bool:
    """Return the legacy multi-volume NCX branch decision."""

    pages_per_epub: dict[object, int] = {}
    for epub_index in spine_epub_indices:
        pages_per_epub[epub_index] = pages_per_epub.get(epub_index, 0) + 1
    all_single_page = (
        len(pages_per_epub) > 1
        and all(count == 1 for count in pages_per_epub.values())
    )
    marker_count = sum(
        1 for _epub_index, label, _href in toc_entries
        if has_multi_volume_label_marker(label)
    )
    return (
        marker_count >= 2
        and not flat_toc
        and not all_single_page
        and not volume_chapter_grouping
    )


def build_volume_chapter_ncx_entries(
    ungrouped: Iterable[tuple[int, str, str]],
    groups: Mapping[int, Iterable[tuple[int, str, str, int]]],
    *,
    start_play_order: int = 1,
    start_book_index: int = 0,
) -> NcxBuildResult:
    """Build legacy NCX entries for volume/chapter grouped merge output."""

    play_order = int(start_play_order)
    book_index = int(start_book_index)
    entries: list[NcxNavEntry] = []

    for _epub_index, label, href in ungrouped:
        book_index += 1
        entries.append(NcxNavEntry(f"book{book_index:03d}", label, href, play_order))
        play_order += 1

    for volume_number in sorted(groups.keys()):
        group_entries = sorted(tuple(groups[volume_number]), key=lambda entry: entry[3])
        if not group_entries:
            continue
        book_index += 1
        parent_id = f"book{book_index:03d}"
        parent_order = play_order
        play_order += 1

        children: list[NcxNavEntry] = []
        for _epub_index, _label, href, chapter_number in group_entries:
            book_index += 1
            children.append(
                NcxNavEntry(
                    f"book{book_index:03d}",
                    f"{chapter_number}\ud654",
                    href,
                    play_order,
                )
            )
            play_order += 1

        entries.append(
            NcxNavEntry(
                parent_id,
                volume_parent_label(volume_number, group_entries[0][1]),
                group_entries[0][2],
                parent_order,
                children,
            )
        )

    return NcxBuildResult(tuple(entries), play_order, book_index)


def build_multi_volume_ncx_entry(
    label: str,
    first_href: str,
    book_pages: Iterable[tuple[str, str, str]],
    *,
    book_index: int,
    start_play_order: int = 1,
) -> NcxBuildResult:
    """Build one legacy NCX parent entry for multi-volume merge output."""

    play_order = int(start_play_order)
    current_book_index = int(book_index)
    parent_order = play_order
    play_order += 1

    children: list[NcxNavEntry] = []
    for item_id, href, page_title in book_pages:
        if not page_title:
            continue
        children.append(
            NcxNavEntry(
                f"book{current_book_index:03d}_{item_id}",
                page_title,
                href,
                play_order,
            )
        )
        play_order += 1

    parent = NcxNavEntry(
        f"book{current_book_index:03d}",
        label,
        first_href,
        parent_order,
        children,
    )
    return NcxBuildResult((parent,), play_order, current_book_index)


def _toc_page_link_from_item(item) -> TocPageLink:
    if isinstance(item, TocPageLink):
        return item
    if isinstance(item, Mapping):
        children = tuple(_toc_page_link_from_item(child) for child in item.get("children", ()))
        return TocPageLink(item.get("href", ""), item.get("label", ""), children)
    if isinstance(item, tuple):
        if len(item) >= 3:
            return TocPageLink(item[2], item[1])
        if len(item) == 2:
            return TocPageLink(item[0], item[1])
    raise TypeError(f"Unsupported TOC page entry: {item!r}")


def _render_toc_page_link(link: TocPageLink) -> str:
    href = html_escape(link.href, quote=True)
    label = html_escape(link.label, quote=True)
    if not link.children:
        return f'<li><a href="{href}">{label}</a></li>\n'
    child_html = "".join(_render_toc_page_link(child) for child in link.children)
    return f'<li><a href="{href}">{label}</a><ul>\n{child_html}</ul></li>\n'


def render_toc_page_document(
    entries: Iterable[TocPageLink | Mapping | tuple],
    *,
    bg: str = "#f4f6fb",
    text: str = "#1a2035",
    accent: str = "#2272d8",
) -> str:
    """Render the legacy merge XHTML TOC page from precomputed links."""

    toc_html = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        '<head><title>\ubaa9\ucc28</title>'
        f'<style>'
        f'body{{font-family:sans-serif;padding:2em;'
        f'background:{bg};color:{text}}}'
        f'h1{{font-size:1.3em;color:{accent};margin-bottom:1em}}'
        f'ol{{padding-left:1.5em}}li{{margin:.5em 0}}'
        f'ul{{padding-left:1.5em;list-style:disc}}'
        f'a{{color:{accent};text-decoration:none}}'
        f'a:hover{{text-decoration:underline}}'
        f'</style></head><body><h1>\U0001f4da \ubaa9\ucc28</h1><ol>\n'
    )
    toc_html += "".join(_render_toc_page_link(_toc_page_link_from_item(entry)) for entry in entries)
    toc_html += '</ol></body></html>'
    return toc_html


def render_merge_opf(
    title: str,
    epub_merge_id: str,
    manifest: Mapping[str, tuple[str, str]] | Iterable[object],
    spine_ids: Iterable[str],
    *,
    creator: str = "",
    publisher: str = "",
    language: str = "ko",
) -> str:
    """Render the advanced legacy merge OPF package document."""

    manifest_items = tuple(_manifest_iter(manifest))
    has_cover = any(item_id == "cover-image" for item_id, _href, _media_type in manifest_items)
    opf_lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<package unique-identifier="uuid_id" version="2.0"'
        ' xmlns="http://www.idpf.org/2007/opf">',
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
        f'    <dc:title>{xml_escape(title or "")}</dc:title>',
    ]
    if creator:
        opf_lines.append(f'    <dc:creator>{xml_escape(creator)}</dc:creator>')
    if publisher:
        opf_lines.append(f'    <dc:publisher>{xml_escape(publisher)}</dc:publisher>')
    opf_lines += [
        f'    <dc:language>{xml_escape(language or "ko")}</dc:language>',
        f'    <dc:identifier id="uuid_id">{xml_escape(epub_merge_id)}</dc:identifier>',
    ]
    if has_cover:
        opf_lines.append('    <meta name="cover" content="cover-image"/>')
    series_name = merge_series_name_from_title(title or "")
    if series_name:
        opf_lines.append(f'    <meta name="calibre:series" content="{xml_escape(series_name)}"/>')
        opf_lines.append(f'    <meta name="calibre:series_index" content="1"/>')
    opf_lines += ['</metadata>', '<manifest>']
    opf_lines.append(
        '    <item id="ncx" href="toc.ncx"'
        ' media-type="application/x-dtbncx+xml"/>')
    for item_id, href, media_type in manifest_items:
        opf_lines.append(
            f'    <item id="{sanitize_opf_id(item_id)}" href="{href}" media-type="{media_type}"/>')
    opf_lines.append('</manifest>')
    opf_lines.append('<spine toc="ncx">')
    for item_id in spine_ids:
        opf_lines.append(f'    <itemref idref="{sanitize_opf_id(item_id)}"/>')
    opf_lines.append('</spine>')
    if has_cover:
        opf_lines += [
            '<guide>',
            '    <reference type="cover" title="Cover" href="OEBPS/Text/cover.xhtml"/>',
            '</guide>',
        ]
    opf_lines.append('</package>')
    return "\n".join(opf_lines)


def render_ncx_nav_point(entry: NcxNavEntry, indent: int = 8) -> list[str]:
    """Render one NCX navPoint and its children using legacy indentation."""

    space = " " * indent
    child_space = " " * (indent + 4)
    lines = [
        f'{space}<navPoint id={quoteattr(entry.nav_id)} playOrder="{entry.play_order}">',
        f'{child_space}<navLabel><text>{xml_escape(entry.label)}</text></navLabel>',
        f'{child_space}<content src={quoteattr(entry.src)}/>',
    ]
    for child in entry.children:
        lines.extend(render_ncx_nav_point(child, indent + 4))
    lines.append(f"{space}</navPoint>")
    return lines


def render_ncx_document(
    title: str,
    epub_merge_id: str,
    entries: Iterable[NcxNavEntry],
    *,
    depth: int = 2,
) -> str:
    """Render a complete NCX document from precomputed nav entries."""

    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">',
        '<head>',
        f'    <meta name="dtb:uid" content="{xml_escape(epub_merge_id)}"/>',
        f'    <meta name="dtb:depth" content="{int(depth)}"/>',
        '    <meta name="dtb:totalPageCount" content="0"/>',
        '    <meta name="dtb:maxPageNumber" content="0"/>',
        '</head>',
        f'<docTitle><text>{xml_escape(title or "")}</text></docTitle>',
        '<navMap>',
    ]
    for entry in entries:
        lines.extend(render_ncx_nav_point(entry, 8))
    lines += ['</navMap>', '</ncx>']
    return "\n".join(lines)


def plan_unreferenced_image_prune(
    manifest: Mapping[str, tuple[str, str]] | Iterable[object],
    referenced_basenames: Iterable[str],
    *,
    protected_manifest_ids: Iterable[str] = ("cover-image",),
) -> ImagePrunePlan:
    """Plan removal of image manifest entries/files not referenced by kept content."""

    refs = frozenset(str(name).lower() for name in referenced_basenames if name)
    protected_ids = frozenset(str(item_id) for item_id in protected_manifest_ids)
    manifest_items = tuple(_manifest_iter(manifest))
    protected_names = frozenset(
        _image_ref_basename(href)
        for item_id, href, _media_type in manifest_items
        if item_id in protected_ids and href
    )
    remove_ids: set[str] = set()
    removable_names: set[str] = set()
    for item_id, href, media_type in manifest_items:
        if not str(media_type).lower().startswith("image/"):
            continue
        basename = _image_ref_basename(href)
        if item_id in protected_ids or basename in refs:
            continue
        remove_ids.add(item_id)
        if basename and basename not in protected_names:
            removable_names.add(basename)
    return ImagePrunePlan(
        referenced_basenames=refs,
        protected_basenames=protected_names,
        remove_manifest_ids=frozenset(remove_ids),
        removable_file_basenames=frozenset(removable_names),
    )


def page_has_image_and_short_text(content_bytes: bytes, max_text_len: int = 80) -> bool:
    """Return True when a page contains an image and little non-style text."""

    raw = _decode_markup(content_bytes)
    if not _IMG_TAG_RE.search(raw):
        return False
    text_only = _STYLE_RE.sub("", raw)
    text_only = _TAG_RE.sub("", text_only)
    text_only = unescape(text_only)
    text_only = re.sub(r"\s+", " ", text_only).strip()
    return len(text_only) < max_text_len


def decide_merge_page_skip(
    href: str,
    content_bytes: bytes,
    *,
    ncx_label: str = "",
    book_index: int = 0,
    spine_position: int = 1,
    keep_vol_covers: bool = False,
    flat_toc: bool = False,
    skip_page_detector: SkipPageDetector | None = None,
) -> str | None:
    """Classify advanced merge pages that legacy MergeWorker would skip."""

    keep_this_cover = keep_vol_covers and not flat_toc
    skip_reason = None

    if skip_page_detector is not None:
        try:
            skip_reason = skip_page_detector(href, content_bytes)
        except Exception:
            skip_reason = None

    if skip_reason == "cover" and book_index > 0 and keep_this_cover:
        skip_reason = None

    label = ncx_label.strip().lower()
    if not skip_reason and label == "cover" and not (book_index > 0 and keep_this_cover):
        if page_has_image_and_short_text(content_bytes):
            skip_reason = "cover"

    if not skip_reason and flat_toc and _FLAT_TOC_NCX_INDEX_RE.match(label):
        skip_reason = "index"

    if not skip_reason and flat_toc and Path(href).stem.lower() == "book_title":
        skip_reason = "index"

    if not skip_reason and book_index > 0 and spine_position <= 2 and not keep_this_cover:
        if page_has_image_and_short_text(content_bytes):
            skip_reason = "cover"

    return skip_reason
