from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.txt_chapters import (  # noqa: E402
    analyze_chapter_suspects,
    absorb_flow_subheadings,
    extract_chapter_number,
    fill_numeric_gaps,
    filter_ascending_chapters,
    is_pure_chapter_marker,
    merge_short_chapters,
    merge_auto_suspect_chapters,
    normalize_chapter_style,
    normalize_messy_toc_markers,
    preserve_unicode_chapter_subtitles,
    restore_unicode_chapter_subtitles,
    strip_chapter_subtitles,
)
from epub_binder_core.txt_detection import detect_chapters  # noqa: E402
from epub_binder_app.ui.main_window import detect_chapters as app_detect_chapters  # noqa: E402


def test_txt_chapter_helpers_handle_numbering_and_short_markers():
    titles = ["1. Start", "Chapter 12", "003: padded", "No chapter"]
    assert [extract_chapter_number(title) for title in titles] == [1, None, 3, None]

    marker_titles = ["", "Chapter 12", "Part 2", "No chapter"]
    assert [is_pure_chapter_marker(title) for title in marker_titles] == [True, True, True, False]

    ascending_chapters = [
        ("1.", ["one"]),
        ("2.", ["two"]),
        ("99.", ["noise"]),
        ("3.", ["three"]),
        ("4.", ["four"]),
    ]
    assert filter_ascending_chapters(ascending_chapters) == [
        ("1.", ["one"]),
        ("2.", ["two", "<b>99.</b>", "noise"]),
        ("3.", ["three"]),
        ("4.", ["four"]),
    ]

    gap_chapters = [
        ("1.", ["one"]),
        ("2.", ["two", "3. three", "still three"]),
        ("4.", ["four"]),
        ("5.", ["five"]),
    ]
    assert fill_numeric_gaps(gap_chapters) == [
        ("1.", ["one"]),
        ("2.", ["two"]),
        ("3. three", ["still three"]),
        ("4.", ["four"]),
        ("5.", ["five"]),
    ]

    short_chapters = [
        ("Chapter 1", []),
        ("Subtitle", []),
        ("Chapter 2", ["body"]),
        ("Chapter 3", ["x"]),
    ]
    assert merge_short_chapters(short_chapters, min_chars=5) == [
        ("Subtitle Chapter 2 Chapter 3", ["body", "<b>Chapter 3</b>", "x"])
    ]

    style_chapters = [
        ("1. Start", ["one"]),
        ("2) Middle", ["two"]),
        ("3. End", ["three"]),
    ]
    assert normalize_chapter_style(style_chapters) == [
        ("1. Start", ["one"]),
        ("2. Middle", ["two"]),
        ("3. End", ["three"]),
    ]

    unicode_chapters = [
        ("1화. Teen Heart-throb +45", []),
        ("2화", []),
        ("시작 3화", []),
        ("4화. Once upon a time in Hollywood (1) +34", []),
        ("57. < MTV Awards 'Best kiss' Performance (2) [유료 시작] >", []),
    ]
    assert normalize_chapter_style(preserve_unicode_chapter_subtitles(unicode_chapters)) == [
        ("1. Teen Heart-throb +45", []),
        ("2화", []),
        ("3화", []),
        ("4. Once upon a time in Hollywood (1) +34", []),
        ("57. < MTV Awards 'Best kiss' Performance (2) [유료 시작] >", []),
    ]

    assert absorb_flow_subheadings([
        ("212.", ["body"]),
        ("특전 확인하고 지고마룡 헬크라수스 사체 해체해 볼까?", ["x"]),
        ("특전 보상 메시지 출발!", ["y" * 2000]),
        ("213.", ["next"]),
    ]) == [
        (
            "212.",
            [
                "body",
                "<b>특전 확인하고 지고마룡 헬크라수스 사체 해체해 볼까?</b>",
                "x",
                "<b>특전 보상 메시지 출발!</b>",
                "y" * 2000,
            ],
        ),
        ("213.", ["next"]),
    ]

    assert absorb_flow_subheadings([
        ("175화 경고", ["body"]),
        ("프롤로그 시간차 안무로 책장 파라락 넘기듯이 표현한 장면.", ["x" * 2500]),
        ("176화 새집 구경", ["next"]),
    ]) == [
        (
            "175화 경고",
            [
                "body",
                "<b>프롤로그 시간차 안무로 책장 파라락 넘기듯이 표현한 장면.</b>",
                "x" * 2500,
            ],
        ),
        ("176화 새집 구경", ["next"]),
    ]

    restored = restore_unicode_chapter_subtitles(
        [("1.", []), ("2.", []), ("3.", [])],
        "\n".join([
            "1화. Teen Heart-throb +45",
            "1.",
            "body",
            "2화. Once upon a time in Hollywood (1) +34",
            "2.",
            "body",
        ]),
    )
    assert restored == [
        ("1. Teen Heart-throb +45", []),
        ("2. Once upon a time in Hollywood (1) +34", []),
        ("3.", []),
    ]


def test_filter_ascending_chapters_absorbs_out_of_order_false_positive():
    chapters = [
        ("1.", ["a"]),
        ("2.", ["b"]),
        ("99.", ["noise"]),
        ("3.", ["c"]),
        ("4.", ["d"]),
    ]

    filtered = filter_ascending_chapters(chapters)

    assert [title for title, _lines in filtered] == ["1.", "2.", "3.", "4."]
    assert filtered[1][1] == ["b", "<b>99.</b>", "noise"]


def test_fill_numeric_gaps_splits_missing_number_from_body():
    chapters = [
        ("1.", ["one"]),
        ("2.", ["two", "3. three", "still three"]),
        ("4.", ["four"]),
        ("5.", ["five"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == ["1.", "2.", "3. three", "4.", "5."]
    assert filled[1][1] == ["two"]
    assert filled[2][1] == ["still three"]
    assert filled[3][1] == ["four"]


def test_fill_numeric_gaps_recovers_embedded_missing_episode():
    chapters = [
        ("196화 구도지설(2)", ["body", "프롤로그의 인트로가 흘러나왔다. 197화 아이돌의 밤(1)"]),
        ("198화 아이돌의 밤(2)", ["next"]),
        ("199화 아이돌의 밤(3)", ["end"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == [
        "196화 구도지설(2)",
        "197화 아이돌의 밤(1)",
        "198화 아이돌의 밤(2)",
        "199화 아이돌의 밤(3)",
    ]
    assert filled[0][1] == ["body", "프롤로그의 인트로가 흘러나왔다."]


def test_merge_short_chapters_drops_pure_empty_marker_and_prefixes_subtitle():
    chapters = [
        ("1.", []),
        ("First meeting", []),
        ("2.", ["body"]),
    ]

    merged = merge_short_chapters(chapters)

    assert merged == [("First meeting 2.", ["body"])]


def test_normalize_chapter_style_uses_dominant_unit_style():
    chapters = [
        ("1화 Start", ["a"]),
        ("2. Middle", ["b"]),
        ("3화 End", ["c"]),
    ]

    normalized = normalize_chapter_style(chapters)

    assert [title for title, _lines in normalized] == ["1화 Start", "2화 Middle", "3화 End"]


def test_normalize_messy_toc_markers_unifies_numeric_markers():
    text = "\n".join(
        [
            "1화",
            "body1",
            "002",
            "body2",
            "<003>",
            "body3",
            "101",
            "body4",
        ]
    )

    normalized = normalize_messy_toc_markers(text)

    assert normalized == "1화\nbody1\n2화\nbody2\n3화\nbody3\n101화\nbody4"


def test_strip_chapter_subtitles_keeps_only_markers():
    chapters = [
        ("시작 001 : 친구 따라 남미 갔다 장관된 썰 푼다.", ["body"]),
        ("2. 남미에서 대통령 권한 대행 된 썰 푼다", ["body"]),
        ("3화 방송을 통해 재하가 귀신으로부터 팀원들을 지키는 장면을", ["body"]),
    ]

    assert strip_chapter_subtitles(chapters) == [
        ("1.", ["body"]),
        ("2.", ["body"]),
        ("3.", ["body"]),
    ]


def test_preserve_unicode_titles_strips_start_before_numeric_dot_marker():
    chapters = preserve_unicode_chapter_subtitles([
        ("\uC2DC\uC791 001 : \uCE5C\uAD6C \uB530\uB77C \uB0A8\uBBF8 \uAC14\uB2E4", ["body"]),
    ])

    assert chapters == [("1. \uCE5C\uAD6C \uB530\uB77C \uB0A8\uBBF8 \uAC14\uB2E4", ["body"])]


def test_fill_numeric_gaps_does_not_split_body_numbered_list_run():
    chapters = [
        ("1.", ["body", "2. list item", "3. list item", "4. list item"]),
        ("5.", ["real"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == ["1.", "5."]
    assert "2. list item" in filled[0][1]


def test_fill_numeric_gaps_does_not_split_one_item_inside_long_numbered_list():
    chapters = [
        ("3화", [
            "시스템에 따르면, 유물의 등급은 총 6개로 나눠진다.",
            "1. 국보급부터 시작해서.",
            "2. 보물급",
            "3. 걸작급.",
            "4. 희귀급.",
            "5. 레트로급.",
            "6. 모조품.",
        ]),
        ("5화", ["real"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == ["3화", "5화"]
    assert "4. 희귀급." in filled[0][1]


def test_merge_short_chapters_keeps_short_numeric_flow_markers():
    chapters = [
        ("87.", ["body"]),
        ("88화", ["body88"]),
        ("89.", ["body"]),
    ]

    assert merge_short_chapters(chapters, min_chars=100) == chapters


def test_fill_numeric_gaps_recovers_escaped_angle_hash_heading():
    chapters = [
        ("53. before", ["prev"]),
        ("54. title", ["body", "&lt; #55. hidden title &gt;", "next body"]),
        ("56. next", ["real"]),
        ("57. after", ["after"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == ["53. before", "54. title", "#55. hidden title", "56. next", "57. after"]
    assert filled[2][1] == ["next body"]


def test_fill_numeric_gaps_recovers_no_space_dot_heading():
    chapters = [
        ("174. first", ["body", "175.The Oprah Winfrey show (2)", "next body"]),
        ("176. next", ["real"]),
        ("177. after", ["after"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == [
        "174. first",
        "175.The Oprah Winfrey show (2)",
        "176. next",
        "177. after",
    ]
    assert filled[1][1] == ["next body"]


def test_merge_short_chapters_combines_empty_duplicate_title_marker():
    chapters = [
        ("7. Swing in Chicago (1) +20", []),
        ("7. Swing in Chicago (1) +20", ["body"]),
        ("8. Swing in Chicago (2) +20", []),
        ("8.", ["next"]),
    ]

    merged = merge_short_chapters(chapters)

    assert merged == [
        ("7. Swing in Chicago (1) +20", ["body"]),
        ("8. Swing in Chicago (2) +20", ["next"]),
    ]


def test_fill_numeric_gaps_splits_spaced_missing_numdot_titles():
    chapters = [
        ("1. \ub300\ub959 \ud1b5\ud569 \uac24\ub7ec\ub9ac", ["body1"]),
        (
            "2. \uae30\uc5b5(1)",
            [
                "body2",
                "3. \uae30\uc5b5(2)",
                "body3",
                "4. \uc704\uae30 (1)",
                "body4",
                "5. \uc704\uae30(2)",
                "body5",
                "6. \uc0ac\uacc4\uc758 \uc232 (1)",
                "body6",
                "7. \uc0ac\uacc4\uc758 \uc232 (2)",
                "body7",
            ],
        ),
        ("8. \uc0ac\uacc4\uc758 \uc232 (3)", ["body8"]),
    ]

    filled = fill_numeric_gaps(chapters)

    assert [title for title, _lines in filled] == [
        "1. \ub300\ub959 \ud1b5\ud569 \uac24\ub7ec\ub9ac",
        "2. \uae30\uc5b5(1)",
        "3. \uae30\uc5b5(2)",
        "4. \uc704\uae30 (1)",
        "5. \uc704\uae30(2)",
        "6. \uc0ac\uacc4\uc758 \uc232 (1)",
        "7. \uc0ac\uacc4\uc758 \uc232 (2)",
        "8. \uc0ac\uacc4\uc758 \uc232 (3)",
    ]
    assert filled[2][1] == ["body3"]


def test_analyze_suspects_does_not_flag_short_hwa_flow_marker():
    chapters = [
        ("2\ud654", ["body2"]),
        ("3\ud654.", ["short"]),
        ("4\ud654 \ud68c\uadc0\uae09.", ["body4"]),
    ]

    assert analyze_chapter_suspects(chapters) == []


def test_app_detect_preserves_colon_chapter_title_with_part_marker():
    text = "\n".join(
        [
            "149. \ub0a8\ubbf8\uc5d0\uc11c \uc11d\uc720\ud310 \uc370 \ud47c\ub2e4(4)",
            "body149",
            "150 : \ub0a8\ubbf8\uc5d0\uc11c \ud574\uc678 \ud22c\uc790\ud55c \uc370 \ud47c\ub2e4. [2\ubd80 \uc2dc\uc791]",
            "body150",
            "151. \ub0a8\ubbf8\uc5d0\uc11c \ud574\uc678 \ud22c\uc790\ud55c \uc370 \ud47c\ub2e4(2)",
            "body151",
        ]
    )

    chapters, _subtitle_style = app_detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == [
        "149. \ub0a8\ubbf8\uc5d0\uc11c \uc11d\uc720\ud310 \uc370 \ud47c\ub2e4(4)",
        "150 : \ub0a8\ubbf8\uc5d0\uc11c \ud574\uc678 \ud22c\uc790\ud55c \uc370 \ud47c\ub2e4. [2\ubd80 \uc2dc\uc791]",
        "151. \ub0a8\ubbf8\uc5d0\uc11c \ud574\uc678 \ud22c\uc790\ud55c \uc370 \ud47c\ub2e4(2)",
    ]


def test_app_detect_ignores_number_beon_body_sentence_between_hwa_flow():
    text = "\n".join(
        [
            "182\ud654 \uc678\uc804",
            "body182",
            "1129 \ubc88\uc774\ub77c.",
            "\ubb38\uc7a5",
            "183\ud654 \uc678\uc804",
            "body183",
        ]
    )

    chapters, _subtitle_style = app_detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == ["182\ud654 \uc678\uc804", "183\ud654 \uc678\uc804"]


def test_detect_chapters_ignores_long_inline_hwa_body_sentence():
    text = "\n".join([
        "1\ud654",
        "1\ud654 \ub2e8\uccb4 \uad00\ub78c\uc744 \uc704\ud574\uc11c\uc600\ub2e4. \uc774\uac83\ub3c4 \ub179\ud654\ud574\uc11c \ubc29\uc1a1\uc5d0 \ub098\uac08 \ubaa8\uc591\uc774\ub2e4.",
        "2\ud654",
        "\ubcf8\ubb38",
        "3\ud654",
        "\ubcf8\ubb38",
    ])

    chapters, _subtitle_style = detect_chapters(text, "normal", enforce_consistency=False)

    assert [title for title, _lines in chapters] == ["1\ud654", "2\ud654", "3\ud654"]
    assert any("\ub2e8\uccb4 \uad00\ub78c" in line for line in chapters[0][1])


def test_analyze_chapter_suspects_marks_review_rows_without_merging_gaps():
    chapters = [
        ("1.", ["body"]),
        ("#TAG", ["tag"]),
        ("2.", ["body"]),
        ("4.", ["body"]),
        ("3.", ["late"]),
        ("5.", ["body"]),
    ]

    suspects = analyze_chapter_suspects(chapters)

    assert [(item["row"], item["kind"], item["auto_merge"]) for item in suspects] == [
        (1, "flow", True),
        (3, "gap", False),
        (4, "order", True),
        (5, "gap", False),
    ]

    merged = merge_auto_suspect_chapters(chapters)

    assert [title for title, _lines in merged] == ["1.", "2.", "4.", "5."]
    assert "<b>#TAG</b>" in merged[0][1]
    assert "<b>3.</b>" in merged[2][1]


def test_analyze_chapter_suspects_auto_merges_inline_numbered_list_title():
    chapters = [
        ("3\ud654", ["body"]),
        ("4\ud654 \ud76c\uadc0\uae09. 5. \ub808\ud2b8\ub85c\uae09. 6. \ubaa8\uc870\ud488.", ["body list"]),
        ("5\ud654", ["real"]),
    ]

    suspects = analyze_chapter_suspects(chapters)

    assert [(item["row"], item["kind"], item["auto_merge"]) for item in suspects] == [
        (1, "inline-list", True),
    ]

    merged = merge_auto_suspect_chapters(chapters)

    assert [title for title, _lines in merged] == ["3\ud654", "5\ud654"]
    assert "<b>4\ud654 \ud76c\uadc0\uae09. 5. \ub808\ud2b8\ub85c\uae09. 6. \ubaa8\uc870\ud488.</b>" in merged[0][1]


def test_analyze_chapter_suspects_does_not_flag_parenthesized_subtitle_numbers():
    chapters = [
        ("1. Title (1) +20", ["body"]),
        ("2. Title (2) +20", ["body"]),
        ("3. Title (3) +20", ["body"]),
    ]

    assert analyze_chapter_suspects(chapters) == []
