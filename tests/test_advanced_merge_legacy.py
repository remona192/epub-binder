import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from epub_binder_app.workers import MergeWorker


def _xhtml(
    title: str,
    body: str,
    image_src: str | None = None,
    *,
    body_is_html: bool = False,
    title_heading: bool = True,
) -> str:
    image = f'<div><img alt="{title}" src="{image_src}"/></div>' if image_src else ""
    body_content = body if body_is_html else f"<p>{body}</p>"
    heading = f"<h2>{title}</h2>" if title_heading else ""
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        f"<head><title>{title}</title></head>"
        f"<body>{heading}{image}{body_content}</body></html>"
    )


def _make_epub(
    tmp_path: Path,
    stem: str,
    volume_no: int,
    cover_bytes: bytes,
    *,
    one_page_body: str | None = None,
) -> Path:
    epub_path = tmp_path / f"{stem}.epub"
    if one_page_body is None:
        manifest_items = """    <item id="cover-img" href="Images/cover.jpg" media-type="image/jpeg"/>
    <item id="cover-page" href="Text/cover.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap1" href="Text/chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="chap2" href="Text/chapter2.xhtml" media-type="application/xhtml+xml"/>"""
        spine_items = """    <itemref idref="cover-page"/>
    <itemref idref="chap1"/>
    <itemref idref="chap2"/>"""
        cover_meta = '    <meta name="cover" content="cover-img"/>'
    else:
        manifest_items = """    <item id="cover-img" href="Images/cover.jpg" media-type="image/jpeg"/>
    <item id="chap1" href="Text/chapter1.xhtml" media-type="application/xhtml+xml"/>"""
        spine_items = '    <itemref idref="chap1"/>'
        cover_meta = '    <meta name="cover" content="cover-img"/>'

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Legacy Merge {volume_no}</dc:title>
    <dc:creator>Tester</dc:creator>
    <dc:language>ko</dc:language>
    <dc:identifier id="bookid">urn:uuid:test-{volume_no}</dc:identifier>
{cover_meta}
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{manifest_items}
  </manifest>
  <spine toc="ncx">
{spine_items}
  </spine>
</package>
"""
    if one_page_body is None:
        navpoints = f"""    <navPoint id="cover" playOrder="1">
      <navLabel><text>Cover</text></navLabel>
      <content src="Text/cover.xhtml"/>
    </navPoint>
    <navPoint id="chap1" playOrder="2">
      <navLabel><text>Chapter {volume_no}-1</text></navLabel>
      <content src="Text/chapter1.xhtml"/>
    </navPoint>
    <navPoint id="chap2" playOrder="3">
      <navLabel><text>Chapter {volume_no}-2</text></navLabel>
      <content src="Text/chapter2.xhtml"/>
    </navPoint>"""
    else:
        navpoints = """    <navPoint id="chap1" playOrder="1">
      <navLabel><text>Chapter Container</text></navLabel>
      <content src="Text/chapter1.xhtml"/>
    </navPoint>"""

    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:test-{volume_no}"/></head>
  <docTitle><text>Legacy Merge {volume_no}</text></docTitle>
  <navMap>
{navpoints}
  </navMap>
</ncx>
"""
    with zipfile.ZipFile(epub_path, "w") as zf:
        zf.writestr(
            "mimetype",
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        if one_page_body is None:
            zf.writestr("OEBPS/Images/cover.jpg", cover_bytes)
            zf.writestr(
                "OEBPS/Text/cover.xhtml",
                _xhtml("Cover", "", "../Images/cover.jpg"),
            )
        else:
            zf.writestr("OEBPS/Images/cover.jpg", cover_bytes)
        zf.writestr(
            "OEBPS/Text/chapter1.xhtml",
            _xhtml(
                f"Chapter {volume_no}-1",
                one_page_body if one_page_body is not None else f"Body {volume_no}-1",
                body_is_html=one_page_body is not None,
                title_heading=one_page_body is None,
            ),
        )
        if one_page_body is None:
            zf.writestr(
                "OEBPS/Text/chapter2.xhtml",
                _xhtml(f"Chapter {volume_no}-2", f"Body {volume_no}-2"),
            )
    return epub_path


def _xml_from_zip(zf: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(zf.read(name))


def _opf_manifest_hrefs(opf_root: ET.Element) -> list[str]:
    ns = {"opf": "http://www.idpf.org/2007/opf"}
    return [
        item.attrib["href"]
        for item in opf_root.findall(".//opf:manifest/opf:item", ns)
    ]


def _opf_spine_idrefs(opf_root: ET.Element) -> list[str]:
    ns = {"opf": "http://www.idpf.org/2007/opf"}
    return [
        item.attrib["idref"]
        for item in opf_root.findall(".//opf:spine/opf:itemref", ns)
    ]


def _opf_manifest_by_id(opf_root: ET.Element) -> dict[str, str]:
    ns = {"opf": "http://www.idpf.org/2007/opf"}
    return {
        item.attrib["id"]: item.attrib["href"]
        for item in opf_root.findall(".//opf:manifest/opf:item", ns)
    }


def _ncx_content_srcs(ncx_root: ET.Element) -> list[str]:
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    return [
        content.attrib["src"].split("#", 1)[0]
        for content in ncx_root.findall(".//ncx:content", ns)
    ]


def _ncx_content_srcs_with_fragments(ncx_root: ET.Element) -> list[str]:
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    return [
        content.attrib["src"]
        for content in ncx_root.findall(".//ncx:content", ns)
    ]


def _ncx_navpoints(ncx_root: ET.Element) -> list[tuple[str, str]]:
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    navpoints = []
    for navpoint in ncx_root.findall(".//ncx:navPoint", ns):
        label = navpoint.findtext("ncx:navLabel/ncx:text", namespaces=ns)
        content = navpoint.find("ncx:content", ns)
        if label is None or content is None:
            continue
        navpoints.append((label, content.attrib["src"].split("#", 1)[0]))
    return navpoints


def _ncx_top_level_navpoints(ncx_root: ET.Element) -> list[ET.Element]:
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    nav_map = ncx_root.find("ncx:navMap", ns)
    assert nav_map is not None
    return nav_map.findall("ncx:navPoint", ns)


def test_advanced_legacy_merge_output_references_and_cover_pruning(tmp_path):
    first = _make_epub(tmp_path, "volume-1", 1, b"first-cover-image")
    second = _make_epub(tmp_path, "volume-2", 2, b"second-cover-image")
    output = tmp_path / "merged.epub"

    worker = MergeWorker(
        epub_files=[str(first), str(second)],
        output_path=str(output),
        title="Merged Legacy",
        add_toc=True,
        toc_titles=["Volume 1", "Volume 2"],
        flat_toc=False,
        keep_vol_covers=False,
    )
    worker.run()

    assert output.exists()
    with zipfile.ZipFile(output) as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert "META-INF/container.xml" in names
        assert "content.opf" in names

        opf_root = _xml_from_zip(zf, "content.opf")
        ncx_root = _xml_from_zip(zf, "toc.ncx")
        zip_entries = set(names)

        for href in _opf_manifest_hrefs(opf_root):
            assert href in zip_entries, href

        for src in _ncx_content_srcs(ncx_root):
            assert src in zip_entries, src

        manifest_by_id = _opf_manifest_by_id(opf_root)
        spine_hrefs = [manifest_by_id[idref] for idref in _opf_spine_idrefs(opf_root)]
        image_hrefs = {
            href for href in manifest_by_id.values() if re.search(r"\.(jpe?g|png|gif|webp)$", href)
        }

        assert image_hrefs == {"OEBPS/Images/cover.jpg"}
        assert spine_hrefs.count("OEBPS/Text/cover.xhtml") == 1
        assert all("Text/1/cover.xhtml" not in href for href in spine_hrefs)
        assert all("Text/2/cover.xhtml" not in href for href in spine_hrefs)
        assert all("volume" not in href.lower() for href in image_hrefs)
        assert sum(href.endswith("/chapter1.xhtml") for href in spine_hrefs) == 2
        assert sum(href.endswith("/chapter2.xhtml") for href in spine_hrefs) == 2

        ncx_srcs = _ncx_content_srcs(ncx_root)
        assert ncx_srcs.count("OEBPS/Text/cover.xhtml") == 1
        assert sum(src.endswith("/chapter1.xhtml") for src in ncx_srcs) >= 2
        assert sum(src.endswith("/chapter2.xhtml") for src in ncx_srcs) >= 2

        navpoints = _ncx_navpoints(ncx_root)
        assert navpoints[0] == ("표지", "OEBPS/Text/cover.xhtml")
        body_navpoints = [
            (label, src)
            for label, src in navpoints
            if label.startswith("Chapter ")
        ]
        assert [label for label, _ in body_navpoints] == [
            "Chapter 1-1",
            "Chapter 1-2",
            "Chapter 2-1",
            "Chapter 2-2",
        ]
        for _, src in body_navpoints:
            assert src in zip_entries, src
        assert "OEBPS/Text/1/cover.xhtml" not in ncx_srcs
        assert "OEBPS/Text/2/cover.xhtml" not in ncx_srcs


def test_advanced_legacy_merge_vol_chap_flat_ncx_entry_is_leaf(tmp_path):
    first = _make_epub(tmp_path, "시리즈 1권 1화", 1, b"first-cover-image")
    second = _make_epub(tmp_path, "시리즈 1권 2화", 2, b"second-cover-image")
    output = tmp_path / "merged-flat.epub"

    worker = MergeWorker(
        epub_files=[str(first), str(second)],
        output_path=str(output),
        title="Merged Legacy",
        add_toc=True,
        toc_titles=["시리즈 1권", "시리즈 1권"],
        flat_toc=True,
        keep_vol_covers=False,
    )
    worker.run()

    assert output.exists()
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    with zipfile.ZipFile(output) as zf:
        ncx_root = _xml_from_zip(zf, "toc.ncx")

    top_level_navpoints = _ncx_top_level_navpoints(ncx_root)
    flat_entry = next(
        navpoint
        for navpoint in top_level_navpoints
        if navpoint.findtext("ncx:navLabel/ncx:text", namespaces=ns) == "시리즈 1권 1화"
    )

    content = flat_entry.find("ncx:content", ns)
    assert content is not None
    assert content.attrib["src"] == "OEBPS/Text/1/chapter1.xhtml"
    assert flat_entry.findall(".//ncx:navPoint", ns) == []


def test_advanced_legacy_merge_vol_chap_grouping_ncx_parent_and_children(tmp_path):
    first = _make_epub(tmp_path, "시리즈 1권 1화", 1, b"first-cover-image")
    second = _make_epub(tmp_path, "시리즈 1권 2화", 2, b"second-cover-image")
    output = tmp_path / "merged-grouped.epub"

    worker = MergeWorker(
        epub_files=[str(first), str(second)],
        output_path=str(output),
        title="Merged Legacy",
        add_toc=True,
        toc_titles=["시리즈 1권", "시리즈 1권"],
        flat_toc=False,
        keep_vol_covers=False,
    )
    worker.run()

    assert output.exists()
    ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
    with zipfile.ZipFile(output) as zf:
        ncx_root = _xml_from_zip(zf, "toc.ncx")

    parent = next(
        navpoint
        for navpoint in _ncx_top_level_navpoints(ncx_root)
        if navpoint.findtext("ncx:navLabel/ncx:text", namespaces=ns) == "시리즈 1권"
    )
    parent_content = parent.find("ncx:content", ns)
    assert parent_content is not None
    assert parent_content.attrib["src"] == "OEBPS/Text/1/chapter1.xhtml"

    children = parent.findall("ncx:navPoint", ns)
    assert [
        child.findtext("ncx:navLabel/ncx:text", namespaces=ns)
        for child in children
    ] == ["1화", "2화"]
    assert [
        child.find("ncx:content", ns).attrib["src"]
        for child in children
    ] == ["OEBPS/Text/1/chapter1.xhtml", "OEBPS/Text/3/chapter1.xhtml"]


def test_advanced_legacy_merge_single_page_sub_navs_write_anchor_navpoints(tmp_path):
    one_page_body = """
<h2>Prologue</h2>
<p>Opening body with enough narrative text to avoid the legacy short index-page
heuristic that treats compact lists of numbered headings as generated
navigation instead of readable chapter text.</p>
<h2>Chapter 1</h2>
<p>First chapter body with more deterministic prose so this one XHTML spine
item remains classified as body content during the advanced merge page-skip
pass.</p>
<h2>Chapter 2</h2>
<p>Second chapter body continues the same fixture text and keeps the regression
focused on automatic subheading anchor injection rather than skip-page
detection.</p>
"""
    source = _make_epub(
        tmp_path,
        "single-page",
        1,
        b"cover-image",
        one_page_body=one_page_body,
    )
    output = tmp_path / "merged-single-page-subnav.epub"

    worker = MergeWorker(
        epub_files=[str(source)],
        output_path=str(output),
        title="Merged Single Page Subnav",
        add_toc=True,
        toc_titles=["Single Page"],
        flat_toc=False,
        keep_vol_covers=False,
    )
    worker.run()

    assert output.exists()
    with zipfile.ZipFile(output) as zf:
        ncx_root = _xml_from_zip(zf, "toc.ncx")
        chapter_html = zf.read("OEBPS/Text/1/chapter1.xhtml").decode("utf-8")

    assert '<a id="sub_0001_001"></a><h2>Prologue</h2>' in chapter_html
    assert '<a id="sub_0001_002"></a><h2>Chapter 1</h2>' in chapter_html
    assert '<a id="sub_0001_003"></a><h2>Chapter 2</h2>' in chapter_html

    srcs = [
        src
        for src in _ncx_content_srcs_with_fragments(ncx_root)
        if src.startswith("OEBPS/Text/1/chapter1.xhtml")
    ]
    assert srcs == [
        "OEBPS/Text/1/chapter1.xhtml",
        "OEBPS/Text/1/chapter1.xhtml#sub_0001_002",
        "OEBPS/Text/1/chapter1.xhtml#sub_0001_003",
    ]


def test_advanced_legacy_merge_removes_continued_notice(tmp_path):
    first = _make_epub(
        tmp_path,
        "notice-1",
        1,
        b"first-cover-image",
        one_page_body="<h2>1화</h2><p>본문입니다.</p><p>다음권에 계속됩니다.</p>",
    )
    second = _make_epub(
        tmp_path,
        "notice-2",
        2,
        b"second-cover-image",
        one_page_body="<h2>2화</h2><p>이어지는 본문입니다.</p>",
    )
    output = tmp_path / "merged-notice.epub"

    worker = MergeWorker(
        epub_files=[str(first), str(second)],
        output_path=str(output),
        title="Merged Notice",
        add_toc=True,
        toc_titles=["1화", "2화"],
        flat_toc=True,
        keep_vol_covers=False,
    )
    worker.run()

    with zipfile.ZipFile(output) as zf:
        merged_html = "\n".join(
            zf.read(name).decode("utf-8", errors="replace")
            for name in zf.namelist()
            if name.startswith("OEBPS/Text/") and name.endswith(".xhtml")
        )

    assert "다음권에 계속됩니다" not in merged_html
    assert "본문입니다" in merged_html
