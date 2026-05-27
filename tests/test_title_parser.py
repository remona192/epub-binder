from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_io import extract_epub_metadata  # noqa: E402
from epub_binder_core.title_parser import (  # noqa: E402
    EpubNameMeta,
    format_rename_name,
    parse_epub_name,
    series_zip_key_from_filename,
)


def test_quaedo_volume_part_rename_name():
    parsed = parse_epub_name(
        original_name="쾌도무적 1권 - 3.epub",
        opf_meta=EpubNameMeta(title="쾌도무적 1-3", creator="박성진(금시조)"),
    )

    assert format_rename_name(parsed) == "[박성진(금시조)] 쾌도무적 1권 - 3.epub"


def test_quaedo_zip_key_without_author():
    assert series_zip_key_from_filename("쾌도무적 1권 - 3.epub", keep_author=False) == "쾌도무적"


def test_quaedo_bad_duplicate_volume_zip_key_keeps_author():
    assert (
        series_zip_key_from_filename("[박성진(금시조)] 쾌도무적 1 1권.epub")
        == "[박성진(금시조)] 쾌도무적"
    )


def test_series_zip_key_ignores_trailing_number_parens():
    assert series_zip_key_from_filename("[간절히] 조선, 봉황이 포효한다 (2).epub") == "[간절히] 조선, 봉황이 포효한다"
    assert series_zip_key_from_filename("[간절히] 조선, 봉황이 포효한다 (6).epub") == "[간절히] 조선, 봉황이 포효한다"


def test_series_zip_key_handles_volume_with_part_or_side_marker():
    assert series_zip_key_from_filename("너희들은 변호됐다 17권(2부).epub") == "너희들은 변호됐다"
    assert series_zip_key_from_filename("너희들은 변호됐다 29권 (완결).epub") == "너희들은 변호됐다"
    assert series_zip_key_from_filename("홍등가의 소드마스터 17권 외전.epub") == "홍등가의 소드마스터"
    assert series_zip_key_from_filename("킹방원 메이커 19권 외전.epub") == "킹방원 메이커"


def test_format_rename_preserves_volume_side_story_marker():
    parsed = parse_epub_name(original_name="[망신창이] 홍등가의 소드마스터 17권 (외전).epub")
    assert format_rename_name(parsed) == "[망신창이] 홍등가의 소드마스터 17권 (외전).epub"

    parsed = parse_epub_name(original_name="[날아오르기] 킹방원 메이커 19권 외전.epub")
    assert format_rename_name(parsed) == "[날아오르기] 킹방원 메이커 19권 (외전).epub"


def test_parse_ignores_source_marker_n_suffix():
    parsed = parse_epub_name(original_name="[고담] 반 리로디드 [개정판] 06 (N).epub")
    assert format_rename_name(parsed) == "[고담] 반 리로디드 [개정판] 6권.epub"


def test_parse_strips_creator_role_suffix():
    parsed = parse_epub_name(
        original_name="씨월드PK 08.epub",
        opf_meta=EpubNameMeta(title="씨월드PK 8(완결)", creator="김현준 저"),
    )
    assert format_rename_name(parsed) == "[김현준] 씨월드PK 8권 (완결).epub"


def test_parse_prefers_leading_author_for_anthology_titles():
    parsed = parse_epub_name(
        original_name="이영도 단편선.epub",
        opf_meta=EpubNameMeta(title="이영도단편집", creator="김민영"),
    )
    assert format_rename_name(parsed) == "[이영도] 이영도단편집.epub"


def test_parse_preserves_edition_marker_from_filename_when_meta_overrides_title():
    parsed = parse_epub_name(
        original_name="[고담] 반 리로디드 [개정판] 06 (N).epub",
        opf_meta=EpubNameMeta(title="반 리로디드 6", creator="고담"),
    )
    assert format_rename_name(parsed) == "[고담] 반 리로디드 [개정판] 6권.epub"


def test_heading_title_keeps_numeric_class_heading():
    parsed = parse_epub_name(
        original_name="section0001.epub",
        html_headings=["케이 18권"],
    )

    assert parsed.series == "케이"
    assert parsed.volume == "18권"


def test_rename_prefers_html_heading_over_opf_title_fixture(tmp_path):
    epub_path = tmp_path / "section0001.epub"
    with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zf:
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
    <dc:title>잘못된 OPF 제목 99권</dc:title>
    <dc:creator>테스트 작가</dc:creator>
  </metadata>
  <manifest>
    <item id="body" href="section0001.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/></spine>
</package>""",
        )
        zf.writestr(
            "OEBPS/section0001.xhtml",
            '<html><body><h2 class="0">진짜 작품 3권</h2></body></html>',
        )

    meta = extract_epub_metadata(epub_path)
    parsed = parse_epub_name(
        path=epub_path,
        original_name=epub_path.name,
        opf_meta=EpubNameMeta(title=meta.title, creator=meta.creator),
        html_headings=meta.headings,
    )

    assert format_rename_name(parsed) == "[테스트 작가] 진짜 작품 3권.epub"


def test_parse_ignores_generic_book_start_heading_and_uses_title_source():
    parsed = parse_epub_name(
        original_name="안녕이라 그랬어 (단편) (교보).epub",
        opf_meta=EpubNameMeta(title="안녕이라 그랬어", creator="김애란"),
        html_headings=["책의 시작", "안녕이라 그랬어"],
    )
    assert format_rename_name(parsed) == "[김애란] 안녕이라 그랬어.epub"


def test_numeric_id_rename_keeps_metadata_title_and_filename_episode():
    parsed = parse_epub_name(
        original_name="632652_10.epub",
        opf_meta=EpubNameMeta(title="고구려 몰락귀족이 되었다", creator="맹애취"),
        html_headings=["시작 10화. 고구려 홍삼 캔디"],
    )

    assert format_rename_name(parsed) == "[맹애취] 고구려 몰락귀족이 되었다 10화.epub"


def test_reliable_opf_title_beats_preface_filename_marker():
    parsed = parse_epub_name(
        original_name="사사키_유헤이_머리말_―_부자가_될_수_있는_최적의_후보자는_월급쟁이다.epub",
        opf_meta=EpubNameMeta(title="돈을 쫓지 않는 부자의 심리", creator="사사키 유헤이"),
        html_headings=[
            "부자는 투자를 할 때도 참조점의 원칙을 지킨다",
            "머리말 ― 부자가 될 수 있는 최적의 후보자는 월급쟁이다",
        ],
    )

    assert format_rename_name(parsed) == "[사사키 유헤이] 돈을 쫓지 않는 부자의 심리.epub"
