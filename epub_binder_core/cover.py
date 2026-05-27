from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import io
import os
import re
import zipfile

from .epub_archive import normalize_zip_path


SortKey = Callable[[str], object]


@dataclass(frozen=True)
class CoverCandidate:
    filename: str
    data: bytes
    ext: str
    size: int
    source: str
    is_default: bool
    label: str


def _default_sort_key(value: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _image_paths(names: list[str]) -> list[str]:
    return [
        name
        for name in names
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        and "__MACOSX" not in name
        and not os.path.basename(name).startswith("._")
    ]


def _opf_info(zf: zipfile.ZipFile) -> tuple[str, str, str]:
    container = zf.read("META-INF/container.xml").decode("utf-8", "replace")
    match = re.search(r"full-path=[\"']([^\"']+\.opf)[\"']", container, re.IGNORECASE)
    if not match:
        raise ValueError("OPF path not found")
    opf_path = match.group(1)
    opf_raw = zf.read(opf_path).decode("utf-8", "replace")
    opf_dir = str(Path(opf_path).parent)
    if opf_dir == ".":
        opf_dir = ""
    return opf_path, opf_raw, opf_dir


def _full_path(opf_dir: str, href: str) -> str:
    return normalize_zip_path(opf_dir, href)


def _first_img_from_html(zf: zipfile.ZipFile, html_path: str, names: set[str]) -> str | None:
    xhtml = zf.read(html_path).decode("utf-8", "replace")
    image_match = re.search(r"<img[^>]+src=[\"']([^\"']+)[\"']", xhtml, re.IGNORECASE)
    if not image_match:
        return None
    img_path = normalize_zip_path(str(Path(html_path).parent), image_match.group(1))
    return img_path if img_path in names else None


def extract_cover_image(epub_bytes: bytes, sort_key: SortKey | None = None) -> tuple[bytes | None, str | None]:
    """Return the default cover image as ``(bytes, ext)``."""
    try:
        with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
            names = zf.namelist()
            name_set = set(names)
            cover_data = None
            cover_ext = ".jpg"
            opf_raw = ""
            opf_dir = ""

            try:
                _, opf_raw, opf_dir = _opf_info(zf)
                cover_id = None
                for match in re.finditer(r"<meta[^>]+name=[\"']cover[\"'][^>]*content=[\"']([^\"']+)[\"']", opf_raw):
                    cover_id = match.group(1)
                    break
                if not cover_id:
                    for match in re.finditer(
                        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*name=[\"']cover[\"'][^>]*/>",
                        opf_raw,
                    ):
                        cover_id = match.group(1)
                        break
                if cover_id:
                    for match in re.finditer(r"<item\s[^>]*id=[\"']" + re.escape(cover_id) + r"[\"'][^>]*/>", opf_raw):
                        href = re.search(r"href=[\"']([^\"']+)[\"']", match.group(0))
                        media_type = re.search(r"media-type=[\"']([^\"']+)[\"']", match.group(0))
                        if not href:
                            break
                        full = _full_path(opf_dir, href.group(1))
                        media = media_type.group(1) if media_type else ""
                        if "image" in media and full in name_set:
                            cover_data = zf.read(full)
                            cover_ext = Path(full).suffix.lower() or ".jpg"
                        elif ("xhtml" in media or "html" in media) and full in name_set:
                            img_path = _first_img_from_html(zf, full, name_set)
                            if img_path:
                                cover_data = zf.read(img_path)
                                cover_ext = Path(img_path).suffix.lower() or ".jpg"
                        break
            except Exception:
                pass

            if not cover_data:
                for name in names:
                    if name.lower().endswith((".jpg", ".jpeg", ".png")) and "cover" in name.lower():
                        if "__MACOSX" not in name and not os.path.basename(name).startswith("._"):
                            cover_data = zf.read(name)
                            cover_ext = Path(name).suffix.lower()
                            break

            if not cover_data and opf_raw:
                try:
                    spine_ids = re.findall(r"<itemref\s[^>]*idref=[\"']([^\"']+)[\"']", opf_raw)
                    manifest = {}
                    for match in re.finditer(r"<item\s([^>]*?)\s*/?>", opf_raw, re.IGNORECASE):
                        item_id = re.search(r"\bid=[\"']([^\"']+)[\"']", match.group(1))
                        href = re.search(r"\bhref=[\"']([^\"']+)[\"']", match.group(1))
                        if item_id and href:
                            manifest[item_id.group(1)] = href.group(1)
                    for spine_id in spine_ids[:3]:
                        href = manifest.get(spine_id)
                        if not href:
                            continue
                        full = _full_path(opf_dir, href)
                        if full not in name_set:
                            continue
                        img_path = _first_img_from_html(zf, full, name_set)
                        if img_path:
                            cover_data = zf.read(img_path)
                            cover_ext = Path(img_path).suffix.lower() or ".jpg"
                            break
                except Exception:
                    pass

            if not cover_data:
                imgs = _image_paths(names)
                if imgs:
                    key = sort_key or _default_sort_key
                    imgs.sort(key=lambda item: key(os.path.basename(item)))
                    cover_data = zf.read(imgs[0])
                    cover_ext = Path(imgs[0]).suffix.lower()

            if cover_data:
                return cover_data, cover_ext
    except Exception:
        pass
    return None, None


def extract_cover_candidates(
    epub_bytes: bytes,
    include_all_images: bool = False,
    sort_key: SortKey | None = None,
) -> list[dict[str, object]]:
    """Return legacy-compatible cover candidate dictionaries."""
    candidates: list[dict[str, object]] = []
    seen: set[str] = set()

    def add(filename: str, data: bytes, source: str) -> None:
        if filename in seen:
            return
        seen.add(filename)
        ext = Path(filename).suffix.lower() or ".jpg"
        label_parts = [os.path.basename(filename)]
        if source == "opf_meta":
            label_parts.append("(OPF meta)")
        elif source == "guide":
            label_parts.append("(guide)")
        elif source == "name":
            label_parts.append("(filename)")
        elif source == "spine_img":
            label_parts.append("(first page img)")
        elif source == "first":
            label_parts.append("(first image)")
        candidates.append(
            {
                "filename": filename,
                "data": data,
                "ext": ext,
                "size": len(data),
                "source": source,
                "is_default": False,
                "label": " ".join(label_parts),
            }
        )

    try:
        with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
            names = zf.namelist()
            name_set = set(names)
            opf_raw = ""
            opf_dir = ""
            try:
                _, opf_raw, opf_dir = _opf_info(zf)
            except Exception:
                pass

            if opf_raw:
                cover_id = None
                for match in re.finditer(r"<meta[^>]+name=[\"']cover[\"'][^>]*content=[\"']([^\"']+)[\"']", opf_raw):
                    cover_id = match.group(1)
                    break
                if not cover_id:
                    for match in re.finditer(
                        r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*name=[\"']cover[\"'][^>]*/>",
                        opf_raw,
                    ):
                        cover_id = match.group(1)
                        break
                if cover_id:
                    for match in re.finditer(r"<item\s[^>]*id=[\"']" + re.escape(cover_id) + r"[\"'][^>]*/>", opf_raw):
                        href = re.search(r"href=[\"']([^\"']+)[\"']", match.group(0))
                        media_type = re.search(r"media-type=[\"']([^\"']+)[\"']", match.group(0))
                        if not href:
                            break
                        full = _full_path(opf_dir, href.group(1))
                        media = media_type.group(1) if media_type else ""
                        if "image" in media and full in name_set:
                            add(full, zf.read(full), "opf_meta")
                        elif ("xhtml" in media or "html" in media) and full in name_set:
                            img_path = _first_img_from_html(zf, full, name_set)
                            if img_path:
                                add(img_path, zf.read(img_path), "opf_meta")
                        break

                for match in re.finditer(
                    r"<reference[^>]+type=[\"']cover[\"'][^>]+href=[\"']([^\"']+)[\"']",
                    opf_raw,
                    re.IGNORECASE,
                ):
                    full = _full_path(opf_dir, match.group(1))
                    if full.lower().endswith((".xhtml", ".html", ".htm")):
                        if full in name_set:
                            img_path = _first_img_from_html(zf, full, name_set)
                            if img_path:
                                add(img_path, zf.read(img_path), "guide")
                    elif full in name_set and full.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        add(full, zf.read(full), "guide")

            for name in names:
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")) and "cover" in name.lower():
                    if "__MACOSX" not in name and not os.path.basename(name).startswith("._"):
                        add(name, zf.read(name), "name")

            if opf_raw:
                try:
                    spine_ids = re.findall(r"<itemref\s[^>]*idref=[\"']([^\"']+)[\"']", opf_raw)
                    manifest = {}
                    for match in re.finditer(r"<item\s([^>]*?)\s*/?>", opf_raw, re.IGNORECASE):
                        item_id = re.search(r"\bid=[\"']([^\"']+)[\"']", match.group(1))
                        href = re.search(r"\bhref=[\"']([^\"']+)[\"']", match.group(1))
                        if item_id and href:
                            manifest[item_id.group(1)] = href.group(1)
                    for spine_id in spine_ids[:3]:
                        href = manifest.get(spine_id)
                        if not href:
                            continue
                        full = _full_path(opf_dir, href)
                        if full not in name_set:
                            continue
                        img_path = _first_img_from_html(zf, full, name_set)
                        if img_path:
                            add(img_path, zf.read(img_path), "spine_img")
                except Exception:
                    pass

            imgs = _image_paths(names)
            if imgs:
                key = sort_key or _default_sort_key
                imgs.sort(key=lambda item: key(os.path.basename(item)))
                add(imgs[0], zf.read(imgs[0]), "first")

            if include_all_images:
                for name in imgs:
                    if name not in seen:
                        add(name, zf.read(name), "image")
    except Exception:
        pass

    if candidates:
        candidates[0]["is_default"] = True
    return candidates


def collect_cover_candidates(
    epub_bytes: bytes,
    include_all_images: bool = False,
    sort_key: SortKey | None = None,
) -> tuple[CoverCandidate, ...]:
    return tuple(
        CoverCandidate(
            filename=str(item["filename"]),
            data=bytes(item["data"]),
            ext=str(item["ext"]),
            size=int(item["size"]),
            source=str(item["source"]),
            is_default=bool(item["is_default"]),
            label=str(item["label"]),
        )
        for item in extract_cover_candidates(epub_bytes, include_all_images, sort_key)
    )
