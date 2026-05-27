from pathlib import Path
import io
import sys
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_io import extract_epub_metadata  # noqa: E402
from epub_binder_core.txt_epub import build_txt_epub  # noqa: E402
from epub_binder_core.txt_parser import decode_txt_bytes, extract_txt_metadata  # noqa: E402


def test_decode_txt_bytes_supports_korean_cp949():
    assert decode_txt_bytes("제목\n본문".encode("cp949")) == "제목\n본문"


def test_extract_txt_metadata_from_filename_and_header():
    assert extract_txt_metadata("[작가] 작품명.txt") == ("작품명", "작가")
    assert extract_txt_metadata("원본.txt", "새제목@새작가\n본문") == ("새제목", "새작가")
    assert extract_txt_metadata("원본.txt", "Title: Header Title\nAuthor: Header Author") == (
        "Header Title",
        "Header Author",
    )


def test_extract_txt_metadata_humanizes_series_filename_and_duplicate_author():
    assert extract_txt_metadata(
        "[뇌조] 뇌조_1990_할리우드_망나니_배우가_되었다_1_216_미완.txt"
    ) == ("1990 할리우드 망나니 배우가 되었다 1-216 미완", "뇌조")


def test_build_txt_epub_writes_valid_structure_with_cover(tmp_path):
    data = build_txt_epub(
        [("1화", ["본문 &amp; 내용"]), ("2화", [])],
        "작품",
        "작가",
        cover_data=b"\x89PNG\r\n\x1a\ncover",
        cover_ext=".png",
    )

    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        infos = zf.infolist()
        assert infos[0].filename == "mimetype"
        assert infos[0].compress_type == zipfile.ZIP_STORED
        names = set(zf.namelist())
        assert "META-INF/container.xml" in names
        assert "OEBPS/content.opf" in names
        assert "OEBPS/toc.ncx" in names
        assert "OEBPS/cover.png" in names
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
        assert 'properties="cover-image"' in opf
        assert '<itemref idref="cover-xhtml"/>' in opf
        ncx_root = ET.fromstring(zf.read("OEBPS/toc.ncx"))
        ns = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
        assert [
            navpoint.findtext("ncx:navLabel/ncx:text", namespaces=ns)
            for navpoint in ncx_root.findall(".//ncx:navPoint", ns)
        ] == ["표지", "1화", "2화"]

    out_path = tmp_path / "built.epub"
    out_path.write_bytes(data)
    meta = extract_epub_metadata(out_path)
    assert meta.title == "작품"
    assert meta.creator == "작가"
    assert meta.spine == ("cover-xhtml", "c0", "c1")
