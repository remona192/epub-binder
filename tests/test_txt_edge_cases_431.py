from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.txt_chapters import (  # noqa: E402
    absorb_flow_subheadings,
    absorb_obvious_numeric_flow_noise,
    extract_chapter_number,
    filter_ascending_chapters,
    preserve_unicode_chapter_subtitles,
    strip_angle_wrapped_chapter_titles,
)


def test_txt_chapter_helpers_handle_new_edge_cases():
    assert extract_chapter_number("175.The Oprah Winfrey show (2)") == 175
    assert extract_chapter_number("3.6kg is body text") is None

    normalized = preserve_unicode_chapter_subtitles([
        ("1,000 LP 2,000 LP 88화", []),
        ("< #55. 기술을 살리는 돈, 기업을 죽이는 돈(1) >", []),
    ])
    assert normalized == [
        ("88화", []),
        ("55. 기술을 살리는 돈, 기업을 죽이는 돈(1)", []),
    ]


def test_txt_chapter_helpers_repair_wine_flow_noise():
    chapters = filter_ascending_chapters([
        ("108. Cute monster(2)", ["108"]),
        ("109. Cute monster(3)", ["109"]),
        ("1. Broken vineyard", ["noise1"]),
        ("0.1% body sentence", ["noise2"]),
        ("1. Ruined vineyard", ["noise3"]),
        ("114. Dispute(1)", ["114"]),
        ("115. Dispute(2)", ["115"]),
    ])
    assert [title for title, _lines in chapters] == [
        "108. Cute monster(2)",
        "109. Cute monster(3)",
        "114. Dispute(1)",
        "115. Dispute(2)",
    ]
    assert "<b>1. Broken vineyard</b>" in chapters[1][1]

    repaired = filter_ascending_chapters([
        ("92. Old bottle(3)", ["92"]),
        ("93. Walnut farm(1)", ["93"]),
        ("# alert # 94\uD654. Walnut farm(2) >", ["94"]),
        ("95. Cult wine(1)", ["95"]),
    ])
    assert [title for title, _lines in repaired] == [
        "92. Old bottle(3)",
        "93. Walnut farm(1)",
        "94\uD654. Walnut farm(2) >",
        "95. Cult wine(1)",
    ]

    absorbed = absorb_flow_subheadings([
        ("130.", ["body"]),
        ("#1NATION #최지한]", ["tag text"]),
        ("에필로그 해석 : 궁금하면 <Flagship> 보셈~ㅋㅋㅋㅋ", ["noise"]),
        ("131.", ["next"]),
    ])
    assert absorbed == [
        ("130.", [
            "body",
            "<b>#1NATION #최지한]</b>",
            "tag text",
            "<b>에필로그 해석 : 궁금하면 &lt;Flagship&gt; 보셈~ㅋㅋㅋㅋ</b>",
            "noise",
        ]),
        ("131.", ["next"]),
    ]


def test_txt_chapter_helpers_clean_final_preview_noise():
    assert strip_angle_wrapped_chapter_titles([
        ("156. < 두 번째 샌프란시스코(3) >", ["body"]),
    ]) == [("156. 두 번째 샌프란시스코(3)", ["body"])]

    assert absorb_obvious_numeric_flow_noise([
        ("132. 흔들리는 미국(3)", ["a"]),
        ("10. 꿀벌과 농사(1)", ["noise"]),
        ("133. 흔들리는 미국(4)", ["b"]),
    ]) == [
        ("132. 흔들리는 미국(3)", ["a", "<b>10. 꿀벌과 농사(1)</b>", "noise"]),
        ("133. 흔들리는 미국(4)", ["b"]),
    ]
