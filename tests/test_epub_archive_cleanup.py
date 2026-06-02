from pathlib import Path
import io
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_archive import (  # noqa: E402
    apply_epub_timestamp,
    write_epub_directory_to_file,
    write_epub_shell_files,
)
from epub_binder_core.epub_cleanup import (  # noqa: E402
    scan_invisible_chars,
    strip_epub_in_memory,
)


def _stored_mimetype(zf: zipfile.ZipFile) -> None:
    info = zipfile.ZipInfo("mimetype")
    info.compress_type = zipfile.ZIP_STORED
    zf.writestr(info, b"application/epub+zip")


def _cleanup_sample() -> bytes:
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
    <dc:title>Sample</dc:title>
    <meta name="book-token" content="remove-me"/>
  </metadata>
  <manifest>
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
    <item id="copy" href="copyright.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="body"/>
    <itemref idref="copy"/>
  </spine>
</package>""",
        )
        zf.writestr("OEBPS/body.xhtml", "<html><body><p>A\u200bB</p></body></html>")
        zf.writestr("OEBPS/copyright.xhtml", "<html><body><p>copyright</p></body></html>")
    return buf.getvalue()


def test_scan_and_strip_cleanup_preserves_epub_structure():
    epub_bytes = _cleanup_sample()

    total, counts = scan_invisible_chars(epub_bytes)
    assert total == 1
    assert counts["U+200B"] == 1
    assert counts["book-token"] == 1

    cleaned, removed_pages, chars_removed, char_counts = strip_epub_in_memory(
        epub_bytes,
        skip_page_detector=lambda filename, _data: "copyright" if "copyright" in filename else None,
    )

    assert chars_removed == 1
    assert char_counts["book-token"] == 1
    assert removed_pages == [("copyright.xhtml", "copyright")]

    with zipfile.ZipFile(io.BytesIO(cleaned), "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert "OEBPS/copyright.xhtml" not in zf.namelist()
        assert b"\xe2\x80\x8b" not in zf.read("OEBPS/body.xhtml")
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
        assert "book-token" not in opf
        assert "copyright.xhtml" not in opf
        assert 'idref="copy"' not in opf


def test_apply_timestamp_preserves_mimetype_storage():
    stamped = apply_epub_timestamp(_cleanup_sample(), (2024, 1, 2, 0, 0, 0))

    with zipfile.ZipFile(io.BytesIO(stamped), "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert {info.date_time for info in infos} == {(2024, 1, 2, 0, 0, 0)}


def test_write_epub_directory_to_file_preserves_legacy_shell_and_timestamp(tmp_path):
    source = tmp_path / "merged"
    (source / "Text").mkdir(parents=True)
    (source / "content.opf").write_text("<package/>", encoding="utf-8")
    (source / "Text" / "chapter.xhtml").write_text("<html/>", encoding="utf-8")
    write_epub_shell_files(source)

    output = tmp_path / "output.epub"
    write_epub_directory_to_file(source, output, timestamp=(2025, 1, 2, 0, 0, 0))

    with zipfile.ZipFile(output, "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert {info.date_time for info in infos} == {(2025, 1, 2, 0, 0, 0)}
        assert set(zf.namelist()) == {
            "mimetype",
            "META-INF/container.xml",
            "content.opf",
            "Text/chapter.xhtml",
        }
        container = zf.read("META-INF/container.xml").decode("utf-8")
        assert 'full-path="content.opf"' in container
