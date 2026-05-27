from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_io import (  # noqa: E402
    extract_epub_metadata,
    find_extracted_opf_path,
    parse_legacy_merge_opf,
    parse_ncx_labels,
    parse_ncx_labels_from_opf_dir,
)


def test_extracts_opf_metadata_and_heading(tmp_path):
    epub_path = tmp_path / "sample.epub"
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
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
    <dc:title>신가</dc:title>
    <dc:creator>케이</dc:creator>
  </metadata>
  <manifest>
    <item id="html1" href="section0001.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="html1"/>
  </spine>
</package>""",
        )
        zf.writestr("OEBPS/section0001.xhtml", '<html><body><h2 class="0">케이 18권</h2></body></html>')

    meta = extract_epub_metadata(epub_path)

    assert meta.title == "신가"
    assert meta.creator == "케이"
    assert meta.opf_path == "OEBPS/content.opf"
    assert meta.spine == ("html1",)
    assert meta.headings == ("케이 18권",)


def test_legacy_merge_opf_parser_reads_manifest_and_spine_shapes():
    opf = """
    <package>
      <manifest>
        <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
        <item id='chap1' href='Text/chapter1.xhtml' media-type='application/xhtml+xml'></item>
        <item id="img cover" href="../Images/cover.jpg" media-type="image/jpeg" />
      </manifest>
      <spine>
        <itemref idref="chap1"/>
        <itemref linear="yes" idref='chap2'></itemref>
      </spine>
    </package>
    """

    manifest, spine = parse_legacy_merge_opf(opf)

    assert manifest == {
        "ncx": "toc.ncx",
        "chap1": "Text/chapter1.xhtml",
        "img cover": "../Images/cover.jpg",
    }
    assert spine == ["chap1", "chap2"]


def test_legacy_merge_ncx_parser_reads_doc_title_and_basename_labels():
    ncx = """
    <ncx>
      <docTitle><text><![CDATA[AT&amp;T Volume]]></text></docTitle>
      <navMap>
        <navPoint id="n1">
          <navLabel><text>Chapter &amp; One</text></navLabel>
          <content src="Text/chapter1.xhtml#frag"/>
        </navPoint>
        <navPoint id="n2">
          <navLabel><text><![CDATA[둘째 장]]></text></navLabel>
          <content src="Text\\chapter2.xhtml"/>
        </navPoint>
      </navMap>
    </ncx>
    """

    labels, doc_title = parse_ncx_labels(ncx)

    assert doc_title == "AT&T Volume"
    assert labels == {
        "chapter1.xhtml": "Chapter & One",
        "chapter2.xhtml": "둘째 장",
    }


def test_extracted_epub_opf_and_ncx_helpers_find_legacy_paths(tmp_path):
    extracted = tmp_path / "book"
    opf_dir = extracted / "OEBPS"
    meta_inf = extracted / "META-INF"
    nested = opf_dir / "Nested"
    nested.mkdir(parents=True)
    meta_inf.mkdir()
    (meta_inf / "container.xml").write_text(
        '<container><rootfile full-path="OEBPS/content.opf"/></container>',
        encoding="utf-8",
    )
    (nested / "toc.ncx").write_text(
        """
        <ncx>
          <docTitle><text>Nested Doc</text></docTitle>
          <navMap><navPoint><navLabel><text>One</text></navLabel>
          <content src="Text/one.xhtml"/></navPoint></navMap>
        </ncx>
        """,
        encoding="utf-8",
    )

    assert Path(find_extracted_opf_path(extracted)) == opf_dir / "content.opf"
    assert parse_ncx_labels_from_opf_dir(opf_dir) == ({"one.xhtml": "One"}, "Nested Doc")
