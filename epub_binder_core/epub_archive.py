from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
import io
import os
import posixpath
import zipfile


def normalize_zip_path(*parts: str) -> str:
    """Return a safe POSIX-style path for entries inside an EPUB archive."""
    joined = posixpath.join(*(p.replace("\\", "/") for p in parts if p))
    normalized = posixpath.normpath(joined).replace("\\", "/")
    if normalized == ".":
        return ""
    while normalized.startswith("../"):
        normalized = normalized[3:]
    return normalized.lstrip("/")


def is_image_path(path: str, exts: Iterable[str] | None = None) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in tuple(exts or (".jpg", ".jpeg", ".png", ".webp", ".gif"))


def compression_for(filename: str) -> int:
    return zipfile.ZIP_STORED if filename == "mimetype" else zipfile.ZIP_DEFLATED


def write_epub_shell_files(root_dir: str | Path, *, rootfile_path: str = "content.opf") -> None:
    """Write the legacy merge container.xml and mimetype files into a directory."""

    root = Path(root_dir)
    meta_dir = root / "META-INF"
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / "container.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>'
        '<container version="1.0"'
        ' xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles>'
        f'<rootfile full-path="{rootfile_path}"'
        ' media-type="application/oebps-package+xml"/>'
        '</rootfiles></container>',
        encoding="utf-8",
    )
    (root / "mimetype").write_text("application/epub+zip", encoding="utf-8")


def _normalize_timestamp(timestamp: tuple | None) -> tuple[int, int, int, int, int, int] | None:
    if not timestamp:
        return None
    if len(timestamp) >= 6:
        return tuple(int(part) for part in timestamp[:6])  # type: ignore[return-value]
    year, month, day = timestamp[:3]
    return int(year), int(month), int(day), 0, 0, 0


def write_epub_directory_to_file(
    source_dir: str | Path,
    output_path: str | Path,
    *,
    timestamp: tuple | None = None,
) -> None:
    """Package an EPUB directory with legacy mimetype ordering and compression."""

    source = Path(source_dir)
    output = Path(output_path)
    if output.exists():
        output.unlink()
    ts = _normalize_timestamp(timestamp)

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        mime_arcname = "mimetype"
        mime_src = source / "mimetype"
        if ts:
            info = zipfile.ZipInfo(mime_arcname, date_time=ts)
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, mime_src.read_bytes())
        else:
            zf.write(mime_src, mime_arcname, compress_type=zipfile.ZIP_STORED)

        for root, _dirs, files in os.walk(source):
            for filename in files:
                if filename == "mimetype":
                    continue
                abs_path = Path(root) / filename
                arcname = os.path.relpath(abs_path, source)
                if ts:
                    info = zipfile.ZipInfo(arcname, date_time=ts)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    zf.writestr(info, abs_path.read_bytes())
                else:
                    zf.write(abs_path, arcname)


def apply_epub_timestamp(epub_bytes: bytes, ts: tuple[int, int, int, int, int, int]) -> bytes:
    """Rewrite all ZIP entries with the requested timestamp."""
    in_buf = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                new_info = zipfile.ZipInfo(item.filename, date_time=ts)
                new_info.compress_type = compression_for(item.filename)
                zout.writestr(new_info, data)
    return out_buf.getvalue()


def add_noise_to_epub(epub_bytes: bytes, level: int) -> bytes:
    """Add light random pixel noise to images inside an EPUB when Pillow exists."""
    try:
        from PIL import Image as Image
    except ImportError:
        return epub_bytes

    amp = {1: 3, 2: 12, 3: 25}.get(level, 3)
    image_exts = (".jpg", ".jpeg", ".png", ".webp")

    def noisy(data: bytes, ext: str) -> bytes:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        try:
            import numpy as np

            arr = np.array(img, dtype=np.int16)
            noise = np.random.randint(-amp, amp + 1, arr.shape, dtype=np.int16)
            arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
            out = Image.fromarray(arr)
        except ImportError:
            import random

            rng = random.Random()
            pixels = list(img.getdata())
            pixels = [
                tuple(max(0, min(255, channel + rng.randint(-amp, amp))) for channel in pixel)
                for pixel in pixels
            ]
            out = Image.new("RGB", img.size)
            out.putdata(pixels)

        buf = io.BytesIO()
        if ext in (".jpg", ".jpeg"):
            out.save(buf, "JPEG", quality=80, optimize=True)
        else:
            out.save(buf, "PNG", optimize=True)
        return buf.getvalue()

    in_buf = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                ext = Path(item.filename.lower()).suffix
                if ext in image_exts:
                    try:
                        data = noisy(data, ext)
                    except Exception:
                        pass
                zout.writestr(item, data, compress_type=compression_for(item.filename))
    return out_buf.getvalue()


def compress_epub_images(epub_bytes: bytes) -> bytes:
    """Recompress JPEG images inside an EPUB when Pillow exists."""
    try:
        from PIL import Image as Image
    except ImportError:
        return epub_bytes

    in_buf = io.BytesIO(epub_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.lower().endswith((".jpg", ".jpeg")):
                    try:
                        img = Image.open(io.BytesIO(data))
                        if img.mode not in ("RGB", "L"):
                            img = img.convert("RGB")
                        buf = io.BytesIO()
                        img.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
                        if buf.tell() < len(data):
                            data = buf.getvalue()
                    except Exception:
                        pass
                zout.writestr(item, data, compress_type=compression_for(item.filename))
    return out_buf.getvalue()
