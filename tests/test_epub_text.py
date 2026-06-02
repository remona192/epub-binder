from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_text import (  # noqa: E402
    apply_txt_paragraph_indent,
    cleanup_txt_text,
    extract_epub_text_sections,
)


def _write_text_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, b"application/epub+zip")
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
    <dc:title>Text Sample</dc:title>
  </metadata>
  <manifest>
    <item id="second" href="Text/second.xhtml" media-type="application/xhtml+xml"/>
    <item id="first" href="Text/first.xhtml" media-type="application/xhtml+xml"/>
    <item id="copy" href="Text/copyright.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="first"/>
    <itemref idref="copy"/>
    <itemref idref="second"/>
  </spine>
</package>""",
        )
        zf.writestr(
            "OEBPS/Text/first.xhtml",
            "<html><body><h1>첫 장</h1><p>A\u200bB<br/>C</p></body></html>",
        )
        zf.writestr("OEBPS/Text/copyright.xhtml", "<html><body><p>copyright</p></body></html>")
        zf.writestr("OEBPS/Text/second.xhtml", "<html><body><p>둘째 장</p></body></html>")


def test_extract_epub_text_sections_uses_spine_order_and_skip_detector(tmp_path):
    epub_path = tmp_path / "text.epub"
    _write_text_epub(epub_path)

    sections = extract_epub_text_sections(
        epub_path,
        skip_page_detector=lambda filename, _data: "copyright" if "copyright" in filename else None,
    )

    assert [name for name, _text in sections] == ["first.xhtml", "second.xhtml"]
    assert sections[0][1] == "첫 장\nAB\nC"
    assert sections[1][1] == "둘째 장"


def test_cleanup_and_indent_helpers():
    assert cleanup_txt_text("section0001.xhtml\n\n본문\n\n\n다음") == "본문\n\n다음"
    assert apply_txt_paragraph_indent("본문\n　이미 들여씀\n\n다음") == "　본문\n　이미 들여씀\n\n　다음"
