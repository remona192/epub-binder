import zipfile

from epub_binder_core.epub_io import extract_epub_metadata
from epub_binder_core.title_parser import EpubNameMeta, format_rename_name, parse_epub_name
from epub_binder_core.txt_detection import clean_chapter_marker_title
from epub_binder_core.txt_epub import build_txt_epub


def _write_minimal_epub(path, title, creator="", copyright_html=""):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
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
            f"""<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{creator}</dc:creator>
  </metadata>
  <manifest>
    <item id="body" href="text/chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="copy" href="text/copyright.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/><itemref idref="copy"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/text/chapter1.xhtml", "<html><body><h1>1화. 고구려 홍삼 캔디</h1></body></html>")
        zf.writestr("OEBPS/text/copyright.xhtml", copyright_html)


def test_copyright_title_overrides_chapterish_opf_title(tmp_path):
    epub_path = tmp_path / "632652_1.epub"
    _write_minimal_epub(
        epub_path,
        "1화. 고구려 홍삼 캔디",
        "",
        '<html><body><p class="title1"><b>고구려 몰락 귀족이 되었다</b></p>'
        "<p>지은이 : 작가명</p></body></html>",
    )

    meta = extract_epub_metadata(epub_path)

    assert meta.title == "고구려 몰락 귀족이 되었다"
    assert meta.creator == "작가명"
    assert meta.headings[0] == "고구려 몰락 귀족이 되었다"


def test_copyright_bold_plain_paragraph_title_overrides_heading(tmp_path):
    epub_path = tmp_path / "632652_1.epub"
    _write_minimal_epub(
        epub_path,
        "1화. 고구려 홍삼 캔디",
        "",
        '<html><body><div class="box_copyright">'
        '<p><span style="font-weight: bold;">고구려 몰락귀족이 되었다</span><br/></p>'
        "<p><b>지은이</b> : 멍애츼<br/></p>"
        "</div></body></html>",
    )

    meta = extract_epub_metadata(epub_path)
    parsed = parse_epub_name(
        epub_path,
        epub_path.name,
        opf_meta=EpubNameMeta(meta.title, meta.creator),
        html_headings=meta.headings,
    )

    assert meta.title == "고구려 몰락귀족이 되었다"
    assert format_rename_name(parsed) == "[멍애츼] 고구려 몰락귀족이 되었다 1화.epub"


def test_numeric_id_filename_keeps_episode_when_metadata_has_series_title(tmp_path):
    epub_path = tmp_path / "632652_1.epub"
    _write_minimal_epub(
        epub_path,
        "1화. 고구려 홍삼 캔디",
        "",
        '<html><body><p><b>고구려 몰락귀족이 되었다</b></p>'
        "<p><b>지은이</b> : 멍애츼</p></body></html>",
    )

    meta = extract_epub_metadata(epub_path)
    parsed = parse_epub_name(
        epub_path,
        epub_path.name,
        opf_meta=EpubNameMeta(meta.title, meta.creator),
        html_headings=meta.headings,
    )

    assert format_rename_name(parsed) == "[멍애츼] 고구려 몰락귀족이 되었다 1화.epub"


def test_opf_title_beats_front_section_heading_for_book_title():
    parsed = parse_epub_name(
        original_name="사사키_유헤이_머리말_―_부자가_될_수_있는_최적의_후보자는_월급쟁이다.epub",
        opf_meta=EpubNameMeta("돈을 쫓지 않는 부자의 심리", "사사키 유헤이"),
        html_headings=[
            "부자는 투자를 할 때도 참조점의 원칙을 지킨다",
            "머리말 ― 부자가 될 수 있는 최적의 후보자는 월급쟁이다",
        ],
    )

    assert format_rename_name(parsed) == "[사사키 유헤이] 돈을 쫓지 않는 부자의 심리.epub"


def test_reliable_opf_title_beats_preface_filename_marker_for_rename():
    parsed = parse_epub_name(
        original_name=(
            "\uc0ac\uc0ac\ud0a4_\uc720\ud5e4\uc774_\uba38\ub9ac\ub9d0_\u2015_"
            "\ubd80\uc790\uac00_\ub420_\uc218_\uc788\ub294_\ucd5c\uc801\uc758_"
            "\ud6c4\ubcf4\uc790\ub294_\uc6d4\uae09\uc7c1\uc774\ub2e4.epub"
        ),
        opf_meta=EpubNameMeta(
            "\ub3c8\uc744 \ucad3\uc9c0 \uc54a\ub294 \ubd80\uc790\uc758 \uc2ec\ub9ac",
            "\uc0ac\uc0ac\ud0a4 \uc720\ud5e4\uc774",
        ),
        html_headings=[
            "\ubd80\uc790\ub294 \ud22c\uc790\ub97c \ud560 \ub54c\ub3c4 \ucc38\uc870\uc810\uc758 \uc6d0\uce59\uc744 \uc9c0\ud0a8\ub2e4",
            "\uba38\ub9ac\ub9d0 \u2015 \ubd80\uc790\uac00 \ub420 \uc218 \uc788\ub294 \ucd5c\uc801\uc758 \ud6c4\ubcf4\uc790\ub294 \uc6d4\uae09\uc7c1\uc774\ub2e4",
        ],
    )

    assert (
        format_rename_name(parsed)
        == "[\uc0ac\uc0ac\ud0a4 \uc720\ud5e4\uc774] "
        "\ub3c8\uc744 \ucad3\uc9c0 \uc54a\ub294 \ubd80\uc790\uc758 \uc2ec\ub9ac.epub"
    )


def test_episode_range_filename_is_not_treated_as_volume_part():
    parsed = parse_epub_name(original_name="[호연] 회사원이 되마를 잘함 1-371.epub")

    assert format_rename_name(parsed) == "[호연] 회사원이 되마를 잘함 1-371화.epub"

    parsed = parse_epub_name(original_name="회귀 후 1000조 야구 제국 001-100 (완).epub")
    assert format_rename_name(parsed) == "회귀 후 1000조 야구 제국 1-100화 (완결).epub"


def test_txt_chapter_title_cleanup_keeps_numdot_angle_number_and_drops_start():
    assert clean_chapter_marker_title("시작 1화. 능력을 각성하다") == "1화. 능력을 각성하다"
    assert (
        clean_chapter_marker_title("57. < MTV Awards ‘Best kiss’ Performance (2) [유료 시작] >")
        == "57. MTV Awards ‘Best kiss’ Performance (2) [유료 시작]"
    )


def test_parse_removes_duplicate_author_prefix_from_body():
    parsed = parse_epub_name(
        original_name="[지나83] 지나83_미국_트럭커가_골동품으로_대박남_1_205_미완.epub"
    )

    assert not format_rename_name(parsed).startswith("[지나83] 지나83")


def test_parse_humanizes_txt_converted_underscore_title():
    parsed = parse_epub_name(
        original_name="[뇌조] 뇌조_1990_할리우드_망나니_배우가_되었다_1_216_미완.epub"
    )

    assert (
        format_rename_name(parsed)
        == "[뇌조] 1990 할리우드 망나니 배우가 되었다 1-216 미완.epub"
    )


def test_txt_epub_uses_reduced_indent():
    data = build_txt_epub([("1화", ["본문"])], "제목", "작가")
    with zipfile.ZipFile(__import__("io").BytesIO(data)) as zf:
        css = zf.read("OEBPS/style.css").decode("utf-8")

    assert "text-indent: 0.75em" in css
