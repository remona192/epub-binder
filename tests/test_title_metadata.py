import io
import zipfile

from epub_binder_core import title_metadata


def test_metadata_helpers_extract_opf_and_copyright_html():
    opf = "<metadata><dc:title><![CDATA[작품_제목 1권]]></dc:title></metadata>"
    html = """
    <html><body>
      <p class="block_4">탈옥한 천재마법사</p>
      <p>지은이｜진설우</p><p>편집부｜유서영</p>
    </body></html>
    """

    assert title_metadata.read_dc_tag(opf, "dc:title") == "작품_제목 1권"
    assert title_metadata.extract_title_from_html(html) == "탈옥한 천재마법사"
    assert title_metadata.extract_creator_from_html(html) == "진설우"


def test_metadata_helpers_clean_and_classify_titles():
    assert title_metadata.normalize_title("작품_제목&nbsp;？") == "작품 제목 ？"
    assert title_metadata.clean_opf_series_title("[현판] 제12화 작품명 12권") == "작품명"
    assert title_metadata.strip_trailing_volume_suffix("작품명 3권") == "작품명"
    assert title_metadata.is_chapterish_title("제12화 귀환")
    assert title_metadata.is_generic_ncx_label("제1화")
    assert title_metadata.is_generic_ncx_label("1.")
    assert title_metadata.is_generic_ncx_label("2")


def test_find_series_volume_heading_in_zip_reads_front_spine_html():
    opf = """
    <package><manifest>
      <item id="c1" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>
    </manifest><spine><itemref idref="c1"/></spine></package>
    """
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as zf:
        zf.writestr("OPS/text/chapter1.xhtml", "<html><body><h1>케이 18권</h1></body></html>")
    data.seek(0)

    with zipfile.ZipFile(data) as zf:
        assert title_metadata.find_series_volume_heading_in_zip(zf, opf, "OPS") == "케이 18권"
