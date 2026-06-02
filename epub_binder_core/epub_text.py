from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from html import unescape
import io
import posixpath
import re
import zipfile

from .epub_cleanup import remove_invisible_chars
from .toc import decode_markup_bytes, is_skip_page as default_is_skip_page
from .txt_parser import decode_txt_bytes


SkipPageDetector = Callable[[str, bytes], str | None]


@dataclass(frozen=True)
class TextSection:
    filename: str
    text: str


@dataclass(frozen=True)
class TextOutputOptions:
    remove_skip_pages: bool = True
    strip_invisible: bool = True
    cleanup_text: bool = True
    indent_paragraphs: bool = False


@dataclass(frozen=True)
class TextOutputResult:
    source_path: str
    output_path: str
    char_count: int


@dataclass(frozen=True)
class CombinedTextOutputResult:
    source_paths: tuple[str, ...]
    output_path: str
    char_count: int


def xml_attr(tag: str, name: str) -> str:
    match = re.search(rf"\b{name}\s*=\s*[\"']([^\"']+)[\"']", tag, re.IGNORECASE)
    return match.group(1).strip() if match else ""


def html_to_plain_text(raw_html: str) -> str:
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", raw_html)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|tr|td|th|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def cleanup_txt_text(text: str) -> str:
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    meta_line = re.compile(
        r"^(?:front|frontmatter|bodymatter|backmatter|section[\s_-]*0*\d{1,6})"
        r"(?:\.(?:xhtml|html|htm|xml))?$",
        re.IGNORECASE,
    )
    out_lines: list[str] = []
    prev_blank = False
    for line in value.split("\n"):
        line = re.sub(r"[ \t\f\v]+", " ", line).strip()
        if line and meta_line.match(line):
            continue
        if not line:
            if not prev_blank:
                out_lines.append("")
            prev_blank = True
        else:
            out_lines.append(line)
            prev_blank = False
    return "\n".join(out_lines).strip("\n")


def apply_txt_paragraph_indent(text: str) -> str:
    """Indent TXT paragraphs while preserving blank and already-indented lines."""
    out_lines: list[str] = []
    for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not line.strip():
            out_lines.append("")
            continue
        stripped = line.strip()
        if line.startswith((" ", "\t", "　")):
            out_lines.append(line)
        else:
            out_lines.append("　" + stripped)
    return "\n".join(out_lines).strip("\n")


def _ordered_html_files(zf: zipfile.ZipFile) -> list[str]:
    names = set(zf.namelist())
    opf_path = None
    try:
        container = decode_markup_bytes(zf.read("META-INF/container.xml"))
        match = re.search(r"full-path=[\"']([^\"']+\.opf)[\"']", container, re.IGNORECASE)
        if match:
            opf_path = match.group(1).replace("\\", "/")
    except Exception:
        opf_path = None

    ordered_files: list[str] = []
    if opf_path and opf_path in names:
        opf_raw = decode_markup_bytes(zf.read(opf_path))
        opf_dir = posixpath.dirname(opf_path)
        manifest: dict[str, str] = {}
        for item_match in re.finditer(r"<item\b[^>]*>", opf_raw, re.IGNORECASE):
            tag = item_match.group(0)
            item_id = xml_attr(tag, "id")
            href = xml_attr(tag, "href")
            media_type = xml_attr(tag, "media-type").lower()
            if not item_id or not href:
                continue
            if "xhtml" in media_type or "html" in media_type:
                manifest[item_id] = posixpath.normpath(posixpath.join(opf_dir, href)).replace("\\", "/")

        for spine_match in re.finditer(r"<itemref\b[^>]*>", opf_raw, re.IGNORECASE):
            item_id = xml_attr(spine_match.group(0), "idref")
            if item_id in manifest:
                ordered_files.append(manifest[item_id])

        if not ordered_files:
            ordered_files = sorted(set(manifest.values()))

    if not ordered_files:
        ordered_files = sorted(name for name in names if name.lower().endswith((".xhtml", ".html", ".htm")))
    return ordered_files


def read_epub_text_sections(
    epub_path: str | Path,
    *,
    remove_skip_pages: bool = True,
    strip_invisible: bool = True,
    cleanup_text: bool = True,
    skip_page_detector: SkipPageDetector | None = None,
) -> tuple[TextSection, ...]:
    epub_bytes = Path(epub_path).read_bytes()
    if strip_invisible:
        epub_bytes, _removed, _counts = remove_invisible_chars(epub_bytes)

    detector = skip_page_detector or default_is_skip_page
    sections: list[TextSection] = []
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        names = set(zf.namelist())
        for rel in _ordered_html_files(zf):
            if rel not in names:
                continue
            try:
                raw_bytes = zf.read(rel)
                raw = decode_markup_bytes(raw_bytes)
            except Exception:
                continue
            if remove_skip_pages:
                try:
                    reason = detector(rel, raw_bytes)
                except Exception:
                    reason = None
                if reason in ("copyright", "cover", "index"):
                    continue
            text = html_to_plain_text(raw)
            if cleanup_text:
                text = cleanup_txt_text(text)
            if text:
                sections.append(TextSection(Path(rel).name, text))
    return tuple(sections)


def extract_epub_text_sections(
    epub_path: str | Path,
    remove_skip_pages: bool = True,
    strip_invisible: bool = True,
    cleanup_text: bool = True,
    skip_page_detector: SkipPageDetector | None = None,
) -> list[tuple[str, str]]:
    return [
        (section.filename, section.text)
        for section in read_epub_text_sections(
            epub_path,
            remove_skip_pages=remove_skip_pages,
            strip_invisible=strip_invisible,
            cleanup_text=cleanup_text,
            skip_page_detector=skip_page_detector,
        )
    ]


def safe_txt_output_stem(src_path: str | Path) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", Path(src_path).stem).strip() or "output"


def unique_txt_output_path(output_dir: str | Path, stem: str) -> Path:
    out_dir = Path(output_dir)
    out_path = out_dir / f"{stem}.txt"
    index = 1
    while out_path.exists():
        out_path = out_dir / f"{stem} ({index}).txt"
        index += 1
    return out_path


def safe_combined_txt_output_stem(name: str | None = None) -> str:
    stem = re.sub(r'[\\/:*?"<>|]', "_", (name or "").strip()).strip()
    return stem or "merged"


def build_text_output_from_path(
    src_path: str | Path,
    options: TextOutputOptions | None = None,
    *,
    skip_page_detector: SkipPageDetector | None = None,
) -> str:
    options = options or TextOutputOptions()
    source = Path(src_path)
    if source.suffix.lower() == ".txt":
        out_text = decode_txt_bytes(source.read_bytes())
        if options.cleanup_text:
            out_text = cleanup_txt_text(out_text)
        if options.indent_paragraphs:
            out_text = apply_txt_paragraph_indent(out_text)
        return out_text.strip() + "\n"

    sections = extract_epub_text_sections(
        source,
        remove_skip_pages=options.remove_skip_pages,
        strip_invisible=options.strip_invisible,
        cleanup_text=options.cleanup_text,
        skip_page_detector=skip_page_detector,
    )
    if not sections:
        raise RuntimeError("추출 가능한 본문(xhtml/html)을 찾지 못했습니다.")

    lines: list[str] = []
    for _section_name, section_text in sections:
        if options.indent_paragraphs:
            section_text = apply_txt_paragraph_indent(section_text)
        lines.append(section_text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_combined_text_output_from_paths(
    src_paths: list[str | Path] | tuple[str | Path, ...],
    options: TextOutputOptions | None = None,
    *,
    skip_page_detector: SkipPageDetector | None = None,
) -> str:
    options = options or TextOutputOptions()
    lines: list[str] = []
    for src_path in src_paths:
        source = Path(src_path)
        text = build_text_output_from_path(
            source,
            options,
            skip_page_detector=skip_page_detector,
        ).strip()
        if not text:
            continue
        title = source.stem.strip()
        if title:
            lines.append(title)
            lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def write_text_output_from_path(
    src_path: str | Path,
    output_dir: str | Path,
    options: TextOutputOptions | None = None,
    *,
    skip_page_detector: SkipPageDetector | None = None,
) -> TextOutputResult:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_text = build_text_output_from_path(
        src_path,
        options,
        skip_page_detector=skip_page_detector,
    )
    out_path = unique_txt_output_path(out_dir, safe_txt_output_stem(src_path))
    out_path.write_text(out_text, encoding="utf-8")
    return TextOutputResult(str(src_path), str(out_path), len(out_text))


def write_combined_text_output_from_paths(
    src_paths: list[str | Path] | tuple[str | Path, ...],
    output_dir: str | Path,
    options: TextOutputOptions | None = None,
    *,
    output_stem: str | None = None,
    skip_page_detector: SkipPageDetector | None = None,
) -> CombinedTextOutputResult:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_text = build_combined_text_output_from_paths(
        src_paths,
        options,
        skip_page_detector=skip_page_detector,
    )
    out_path = unique_txt_output_path(
        out_dir,
        safe_combined_txt_output_stem(output_stem),
    )
    out_path.write_text(out_text, encoding="utf-8")
    return CombinedTextOutputResult(
        tuple(str(path) for path in src_paths),
        str(out_path),
        len(out_text),
    )
