from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import os
from pathlib import Path
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

from .title_metadata import extract_creator_from_html, extract_title_from_html, normalize_title


_CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
_OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}
_HEADING_RE = re.compile(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_CDATA_RE = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)
_COPYRIGHT_PAGE_RE = re.compile(
    r"(?:copyright|copy|colophon|imprint|rights|book[_-]?info|endpg|end[_-]?page)",
    re.IGNORECASE,
)
_CHAPTERISH_TITLE_RE = re.compile(
    r"^\s*(?:\uC2DC\uC791\s+)?(?:\uC81C\s*)?\d{1,5}\s*(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)\b"
    r"|^\s*#?\s*\d{1,5}\s*[.)]\s*\S+"
    r"|^\s*(?:Prologue|Epilogue|Interlude|Chapter|CHAPTER|chapter|Ch\.?)\s*\d*\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ManifestItem:
    id: str
    href: str
    media_type: str
    properties: str = ""


@dataclass(frozen=True)
class EpubMetadata:
    title: str = ""
    creator: str = ""
    opf_path: str = ""
    spine: tuple[str, ...] = ()
    manifest: tuple[ManifestItem, ...] = ()
    ncx_labels: tuple[str, ...] = ()
    headings: tuple[str, ...] = ()


def _read_text(zf: zipfile.ZipFile, name: str) -> str:
    data = zf.read(name)
    for encoding in ("utf-8", "utf-8-sig", "cp949"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _clean_html_text(value: str) -> str:
    text = _TAG_RE.sub("", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _opf_path_from_container(zf: zipfile.ZipFile) -> str:
    container_xml = _read_text(zf, "META-INF/container.xml")
    root = ET.fromstring(container_xml)
    rootfile = root.find(".//c:rootfile", _CONTAINER_NS)
    if rootfile is None:
        raise ValueError("container.xml에 OPF rootfile이 없습니다.")
    opf_path = rootfile.attrib.get("full-path", "").strip()
    if not opf_path:
        raise ValueError("OPF 경로가 비어 있습니다.")
    return opf_path


def _metadata_text(root: ET.Element, name: str) -> str:
    elem = root.find(f".//dc:{name}", _OPF_NS)
    if elem is not None and elem.text:
        return re.sub(r"\s+", " ", elem.text).strip()
    return ""


def xml_attr(tag: str, name: str) -> str:
    match = re.search(rf'\b{name}\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_manifest(root: ET.Element) -> tuple[ManifestItem, ...]:
    items: list[ManifestItem] = []
    for item in root.findall(".//opf:manifest/opf:item", _OPF_NS):
        items.append(
            ManifestItem(
                id=item.attrib.get("id", ""),
                href=item.attrib.get("href", ""),
                media_type=item.attrib.get("media-type", ""),
                properties=item.attrib.get("properties", ""),
            )
        )
    return tuple(items)


def _parse_spine(root: ET.Element) -> tuple[str, ...]:
    ids: list[str] = []
    for itemref in root.findall(".//opf:spine/opf:itemref", _OPF_NS):
        idref = itemref.attrib.get("idref", "")
        if idref:
            ids.append(idref)
    return tuple(ids)


def find_extracted_opf_path(base: str | Path) -> str:
    """Return the OPF path from an already-extracted EPUB directory."""
    base_path = Path(base)
    container_path = base_path / "META-INF" / "container.xml"
    if not container_path.exists():
        raise FileNotFoundError("container.xml 없음")
    container = container_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'full-path="([^"]+\.opf)"', container)
    if not match:
        raise ValueError("OPF 경로 없음")
    return str(base_path / match.group(1).replace("/", os.sep))


def parse_legacy_merge_opf(opf_text: str) -> tuple[dict[str, str], list[str]]:
    """Parse OPF manifest hrefs and spine idrefs in the shape used by MergeWorker."""
    manifest: dict[str, str] = {}
    item_pattern = re.compile(r"<item\s([^>]*?)\s*/?>", re.IGNORECASE)
    for match in item_pattern.finditer(opf_text or ""):
        attrs = match.group(1)
        item_id = re.search(r'\bid=["\']([^"\']+)["\']', attrs)
        href = re.search(r'\bhref=["\']([^"\']+)["\']', attrs)
        if item_id and href:
            manifest[item_id.group(1)] = href.group(1)
    spine = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_text or "")
    return manifest, spine


def _clean_ncx_label(value: str) -> str:
    text = re.sub(r"\s+", " ", unescape(value or ""))
    return _CDATA_RE.sub(r"\1", text).strip()


def parse_ncx_labels(ncx_text: str) -> tuple[dict[str, str], str]:
    """Parse legacy NCX labels by content basename plus the NCX docTitle."""
    ncx_labels: dict[str, str] = {}
    doc_title = ""
    doc_match = re.search(
        r"<docTitle[^>]*>.*?<text[^>]*>(.*?)</text>",
        ncx_text or "",
        re.IGNORECASE | re.DOTALL,
    )
    if doc_match:
        doc_title = _clean_ncx_label(doc_match.group(1))

    nav_pattern = re.compile(
        r"<navPoint[^>]*>.*?<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>.*?"
        r"<content[^>]*src=[\"']([^\"'#]+)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in nav_pattern.finditer(ncx_text or ""):
        label = _clean_ncx_label(match.group(1))
        href = match.group(2).strip()
        basename = Path(href.replace("\\", "/")).name.lower()
        if label and basename:
            ncx_labels[basename] = label
    return ncx_labels, doc_title


def parse_ncx_labels_from_opf_dir(opf_dir: str | Path) -> tuple[dict[str, str], str]:
    """Find toc.ncx near an extracted OPF directory and parse legacy labels."""
    opf_dir_path = Path(opf_dir)
    candidates = [
        opf_dir_path / "toc.ncx",
        opf_dir_path / "OEBPS" / "toc.ncx",
    ]
    ncx_path = next((path for path in candidates if path.exists()), None)
    if ncx_path is None:
        for root, _dirs, files in os.walk(opf_dir_path):
            for filename in files:
                if filename.lower() == "toc.ncx":
                    ncx_path = Path(root) / filename
                    break
            if ncx_path is not None:
                break
    if ncx_path is None:
        return {}, ""
    try:
        raw = ncx_path.read_text(encoding="utf-8", errors="replace")
        return parse_ncx_labels(raw)
    except Exception:
        return {}, ""


def _extract_ncx_labels(zf: zipfile.ZipFile, opf_path: str, manifest: tuple[ManifestItem, ...]) -> tuple[str, ...]:
    ncx = next((item for item in manifest if item.media_type == "application/x-dtbncx+xml"), None)
    if not ncx:
        return ()
    ncx_path = posixpath.normpath(posixpath.join(posixpath.dirname(opf_path), ncx.href))
    if ncx_path not in zf.namelist():
        return ()
    try:
        root = ET.fromstring(_read_text(zf, ncx_path))
    except ET.ParseError:
        return ()
    labels: list[str] = []
    for elem in root.iter():
        if _local_name(elem.tag) == "text" and elem.text:
            label = re.sub(r"\s+", " ", elem.text).strip()
            if label:
                labels.append(label)
    return tuple(labels)


def _extract_headings(zf: zipfile.ZipFile, opf_path: str, manifest: tuple[ManifestItem, ...]) -> tuple[str, ...]:
    names = set(zf.namelist())
    opf_dir = posixpath.dirname(opf_path)
    headings: list[str] = []
    for item in manifest:
        if item.media_type not in {"application/xhtml+xml", "text/html"}:
            continue
        html_path = posixpath.normpath(posixpath.join(opf_dir, item.href))
        if html_path not in names:
            continue
        html = _read_text(zf, html_path)
        for match in _HEADING_RE.finditer(html):
            text = _clean_html_text(match.group(1))
            if text:
                headings.append(text)
        if headings:
            break
    return tuple(headings)


def _looks_chapterish_title(value: str) -> bool:
    text = normalize_title(value or "")
    if not text:
        return False
    return bool(_CHAPTERISH_TITLE_RE.search(text))


def _extract_copyright_metadata(
    zf: zipfile.ZipFile,
    opf_path: str,
    manifest: tuple[ManifestItem, ...],
) -> tuple[str, str]:
    names = set(zf.namelist())
    opf_dir = posixpath.dirname(opf_path)
    html_items = [
        item for item in manifest
        if item.media_type in {"application/xhtml+xml", "text/html"}
    ]
    preferred = [
        item for item in html_items
        if _COPYRIGHT_PAGE_RE.search(item.href or "") or _COPYRIGHT_PAGE_RE.search(item.id or "")
    ]
    candidates = preferred or html_items[-5:]
    title = ""
    creator = ""
    for item in candidates:
        html_path = posixpath.normpath(posixpath.join(opf_dir, item.href))
        if html_path not in names:
            continue
        try:
            html = _read_text(zf, html_path)
        except Exception:
            continue
        if not title:
            found_title = extract_title_from_html(html)
            if not found_title:
                for para in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL):
                    text = _clean_html_text(para)
                    if not text:
                        continue
                    if re.search(r"(?:\uC9C0\uC740\uC774|\uC800\uC790|\uC791\uAC00|\uBC1C\uD589|\uD3B8\uC9D1|ISBN|copyright|rights|email|http)", text, re.IGNORECASE):
                        continue
                    if 2 < len(text) < 80 and re.search(r"[\uAC00-\uD7A3A-Za-z]{2,}", text):
                        found_title = text
                        break
            if found_title and not _looks_chapterish_title(found_title):
                title = normalize_title(found_title)
        if not creator:
            found_creator = extract_creator_from_html(html)
            if found_creator:
                creator = normalize_title(found_creator)
        if title and creator:
            break
    return title, creator


def extract_epub_metadata(path: str | Path) -> EpubMetadata:
    with zipfile.ZipFile(path, "r") as zf:
        opf_path = _opf_path_from_container(zf)
        root = ET.fromstring(_read_text(zf, opf_path))
        manifest = _parse_manifest(root)
        spine = _parse_spine(root)
        opf_title = _metadata_text(root, "title")
        opf_creator = _metadata_text(root, "creator")
        copyright_title, copyright_creator = _extract_copyright_metadata(zf, opf_path, manifest)
        title = opf_title
        if copyright_title and (not title or _looks_chapterish_title(title)):
            title = copyright_title
        creator = opf_creator or copyright_creator
        headings = _extract_headings(zf, opf_path, manifest)
        if copyright_title:
            headings = (copyright_title,) + tuple(h for h in headings if normalize_title(h) != copyright_title)
        return EpubMetadata(
            title=title,
            creator=creator,
            opf_path=opf_path,
            spine=spine,
            manifest=manifest,
            ncx_labels=_extract_ncx_labels(zf, opf_path, manifest),
            headings=headings,
        )
