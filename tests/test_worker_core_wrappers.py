import io
import zipfile

from epub_binder_app import workers
from epub_binder_app.ui.helpers import natural_sort_key
from epub_binder_core.cover import extract_cover_image as core_extract_cover_image
from epub_binder_core.epub_cleanup import (
    remove_invisible_chars as core_remove_invisible_chars,
    scan_invisible_chars as core_scan_invisible_chars,
    strip_epub_in_memory as core_strip_epub_in_memory,
)


def _stored_mimetype(zf: zipfile.ZipFile) -> None:
    info = zipfile.ZipInfo("mimetype")
    info.compress_type = zipfile.ZIP_STORED
    zf.writestr(info, b"application/epub+zip")


def _tiny_epub() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        _stored_mimetype(zf)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Tiny</dc:title>
    <meta name="book-token" content="remove-me"/>
  </metadata>
  <manifest>
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/body.xhtml", "<html><body><p>A\u200bB\u2060C</p></body></html>")
    return buf.getvalue()


def _cover_epub() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        _stored_mimetype(zf)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Cover Tiny</dc:title>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    <item id="cover-image" href="Images/cover.jpg" media-type="image/jpeg"/>
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/body.xhtml", '<html><body><img src="Images/cover.jpg"/></body></html>')
        zf.writestr("OEBPS/Images/cover.jpg", b"not-a-real-jpeg-but-cover-bytes")
    return buf.getvalue()


def _zip_shape(epub_bytes: bytes) -> list[tuple[str, int, tuple[int, int, int, int, int, int], bytes]]:
    with zipfile.ZipFile(io.BytesIO(epub_bytes), "r") as zf:
        return [
            (info.filename, info.compress_type, info.date_time, zf.read(info.filename))
            for info in zf.infolist()
        ]


def test_worker_cleanup_wrappers_match_core_on_tiny_epub():
    epub_bytes = _tiny_epub()

    assert workers.scan_invisible_chars(epub_bytes) == core_scan_invisible_chars(epub_bytes)

    worker_cleaned, worker_total, worker_counts = workers.remove_invisible_chars(epub_bytes)
    core_cleaned, core_total, core_counts = core_remove_invisible_chars(epub_bytes)

    assert _zip_shape(worker_cleaned) == _zip_shape(core_cleaned)
    assert worker_total == core_total == 2
    assert worker_counts == core_counts


def test_worker_strip_wrapper_uses_core_skip_page_detector():
    epub_bytes = _tiny_epub()

    worker_cleaned, worker_removed, worker_total, worker_counts = workers.strip_epub_in_memory(epub_bytes)
    core_cleaned, core_removed, core_total, core_counts = core_strip_epub_in_memory(
        epub_bytes,
        skip_page_detector=workers.is_skip_page,
    )

    assert _zip_shape(worker_cleaned) == _zip_shape(core_cleaned)
    assert worker_removed == core_removed
    assert worker_total == core_total
    assert worker_counts == core_counts


def test_worker_cover_wrapper_uses_natural_sort_key():
    epub_bytes = _cover_epub()

    assert workers.extract_cover_image(epub_bytes) == core_extract_cover_image(
        epub_bytes,
        sort_key=natural_sort_key,
    )
