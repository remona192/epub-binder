from pathlib import Path
import io
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_io import extract_epub_metadata  # noqa: E402
from epub_binder_core.merge import MergeOptions, merge_epubs  # noqa: E402


def _write_source_epub(path: Path, title: str, body: str) -> None:
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
            f"""<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
  </metadata>
  <manifest>
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/body.xhtml", body)


def test_basic_merge_writes_valid_epub_structure(tmp_path):
    first = tmp_path / "first.epub"
    second = tmp_path / "second.epub"
    out = tmp_path / "merged.epub"
    _write_source_epub(first, "First", "<html><body><h1>One</h1></body></html>")
    _write_source_epub(second, "Second", "<html><body><h1>Two</h1></body></html>")

    result = merge_epubs(
        [first, second],
        out,
        MergeOptions(title="Bundle", toc_titles=("One", "Two")),
    )

    assert result.ok is True
    assert result.input_count == 2
    assert result.spine_count == 2

    with zipfile.ZipFile(out, "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        names = set(zf.namelist())
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/toc.ncx" in names
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
        assert 'href="Text/vol001_0001.xhtml"' in opf
        assert 'href="Text/vol002_0001.xhtml"' in opf
        ncx_root = ET.fromstring(zf.read("OEBPS/toc.ncx"))
        ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
        assert [
            navpoint.findtext("ncx:navLabel/ncx:text", namespaces=ns)
            for navpoint in ncx_root.findall(".//ncx:navPoint", ns)
        ] == ["One", "Two"]

    meta = extract_epub_metadata(out)
    assert meta.title == "Bundle"
    assert meta.spine == ("item0001", "item0002")
