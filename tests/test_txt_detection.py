from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.txt_detection import detect_chapters  # noqa: E402


def test_detect_chapters_splits_simple_korean_hwa_headers():
    text = "1화\n첫 문장\n2화\n둘째 문장"

    chapters, subtitle_style = detect_chapters(text)

    assert subtitle_style is False
    assert chapters == [
        ("1화", ["첫 문장"]),
        ("2화", ["둘째 문장"]),
    ]


def test_detect_chapters_drops_title_author_intro_section():
    text = "작품명@작가명\n소개 문장\n1화\n본문"

    chapters, _subtitle_style = detect_chapters(text)

    assert chapters == [("1화", ["본문"])]


def test_detect_chapters_absorbs_subtitles_for_title_prefixed_style():
    text = "\n".join(
        [
            "작품명 1화",
            "첫 만남",
            "본문 1",
            "작품명 2화",
            "다음 이야기",
            "본문 2",
            "작품명 3화",
            "마지막 선택",
            "본문 3",
        ]
    )

    chapters, subtitle_style = detect_chapters(text)

    assert subtitle_style is True
    assert [title for title, _lines in chapters] == [
        "1화 첫 만남",
        "2화 다음 이야기",
        "3화 마지막 선택",
    ]
    assert chapters[0][1] == ["본문 1"]


def test_detect_chapters_custom_regex_has_priority():
    text = "막간\n소개\n@@ 1\n첫 본문\n@@ 2\n둘째 본문"

    chapters, _subtitle_style = detect_chapters(text, custom_regex=r"^@@\s*\d+")

    assert chapters == [
        ("시작", ["막간", "소개"]),
        ("@@ 1", ["첫 본문"]),
        ("@@ 2", ["둘째 본문"]),
    ]


def test_detect_chapters_fallback_splits_ascending_bare_number_titles():
    text = "\n".join(
        [
            "207 관정 선점(3)",
            "본문",
            "208 실버오크의 포도(1)",
            "본문",
            "209 실버오크의 포도(2)",
            "본문",
            "210 카스텔로 엠페러 (1)",
            "본문",
            "211 카스텔로 엠페러 (2)",
            "본문",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text)

    assert [title for title, _lines in chapters] == [
        "207 관정 선점(3)",
        "208 실버오크의 포도(1)",
        "209 실버오크의 포도(2)",
        "210 카스텔로 엠페러 (1)",
        "211 카스텔로 엠페러 (2)",
    ]


def test_strong_detection_ignores_numeric_body_shapes():
    text = "\n".join(
        [
            "26화 Big Ass Park(2)",
            "본문",
            "3-5-2를 유지하는 알레띠.",
            "1931-1932 시즌.",
            "0.003%쯤 되는 무시무시한 노예왕이라는 뜻이다.",
            "1-1) 커피믹스에 골든타임 이외의 브랜드는 존재하지 않습니다.",
            "27화 Big Ass Park(3)",
            "본문",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text, strength="strong", enforce_consistency=False)

    assert [title for title, _lines in chapters] == [
        "26화 Big Ass Park(2)",
        "27화 Big Ass Park(3)",
    ]
    assert any("3-5-2" in line for line in chapters[0][1])
    assert any("0.003%" in line for line in chapters[0][1])


def test_detect_chapters_accepts_indented_hash_number_titles():
    text = "\n".join(
        [
            "120. before",
            "body120",
            "\t#121. 500원에 뚫린 만리장성 방화벽(1)",
            "body121",
            "      #180. 세상에 돈으로 안 되는 일이 어디 있어?(2)",
            "body180",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == [
        "120. before",
        "#121. 500원에 뚫린 만리장성 방화벽(1)",
        "#180. 세상에 돈으로 안 되는 일이 어디 있어?(2)",
    ]


def test_detect_chapters_does_not_extract_decimal_percent_from_sentence():
    text = "\n".join(
        [
            "1화",
            "“그렇지. 15.4%였나? 이자소득세까지 나가.”",
            "-연이율 : 8.2% (복리)",
            "2화",
            "본문",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == ["1화", "2화"]
    assert any("15.4%" in line for line in chapters[0][1])
    assert any("8.2%" in line for line in chapters[0][1])


def test_detect_chapters_accepts_angle_wrapped_korean_part_titles():
    text = "\n".join(
        [
            "<1부> 열아홉",
            "첫 본문",
            "<2부> 스물하나",
            "둘째 본문",
            "<3부> 서른",
            "셋째 본문",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text)

    assert [title for title, _lines in chapters] == ["1부 열아홉", "2부 스물하나", "3부 서른"]
    assert chapters[0][1] == ["첫 본문"]


def test_detect_chapters_strips_balanced_brackets_from_special_titles():
    text = "\n".join(
        [
            "1화",
            "본문",
            "[에필로그 1]",
            "후일담 1",
            "[에필로그 2]",
            "후일담 2",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text)

    assert [title for title, _lines in chapters] == ["1화", "에필로그 1", "에필로그 2"]


def test_detect_chapters_ignores_inline_number_dot_body_sentence():
    text = "\n".join(
        [
            "60. before",
            "“택시 미터기로 칩시다. 1km당 100원이 올라가야 정상인데.”",
            "“그럼 우리 남은 돈 9.5조 원은 어디로 갈까요?”",
            "61. after",
            "body",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == ["60. before", "61. after"]
    assert any("1km" in line for line in chapters[0][1])
    assert any("9.5조" in line for line in chapters[0][1])


def test_detect_chapters_ignores_zero_padded_number_dot_body_sentence():
    text = "\n".join(
        [
            "<1부> 열아홉",
            "첫 본문",
            "0805. 숫자 네 개를 찍어 누르며 히죽 웃던 스무 살의 강희백이 눈앞에 스쳐 지나갔다.",
            "이어지는 본문",
            "[에필로그 1]",
            "후일담",
        ]
    )

    chapters, _subtitle_style = detect_chapters(text, enforce_consistency=False)

    assert [title for title, _lines in chapters] == ["1부 열아홉", "에필로그 1"]
    assert any("0805." in line for line in chapters[0][1])
