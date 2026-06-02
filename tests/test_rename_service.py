from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.rename_service import build_rename_preview_rows  # noqa: E402


def test_build_rename_preview_rows_preserves_existing_names_and_guess_fallback():
    rows = build_rename_preview_rows(
        (
            ("a.epub", "원본 1.epub", "1 KB"),
            ("b.epub", "원본 2.epub", "1 KB"),
        ),
        existing_names={"a.epub": "수동 편집.epub"},
        guess_name=lambda _path, original: original.replace("원본", "추출"),
    )

    assert [row.new_name for row in rows] == ["수동 편집.epub", "추출 2.epub"]


def test_build_rename_preview_rows_normalizes_series_title_like_legacy_ui():
    rows = build_rename_preview_rows(
        (
            ("a.epub", "a.epub"),
            ("b.epub", "b.epub"),
        ),
        guess_name=lambda path, _original: {
            "a.epub": "버림받은 황비 1.epub",
            "b.epub": "버림 받은 황비 2.epub",
        }[path],
    )

    assert [row.new_name for row in rows] == [
        "버림받은 황비 1.epub",
        "버림받은 황비 2.epub",
    ]


def test_build_rename_preview_rows_normalizes_author_by_majority_and_length():
    rows = build_rename_preview_rows(
        (
            ("a.epub", "a.epub"),
            ("b.epub", "b.epub"),
        ),
        guess_name=lambda path, _original: {
            "a.epub": "[권아] 작품 1권.epub",
            "b.epub": "[권아인] 작품 2권.epub",
        }[path],
        series_key_func=lambda _name: "작품",
    )

    assert [row.new_name for row in rows] == [
        "[권아인] 작품 1권.epub",
        "[권아인] 작품 2권.epub",
    ]


def test_build_rename_preview_rows_unifies_mixed_volume_episode_units():
    rows = build_rename_preview_rows(
        (
            ("a.epub", "a.epub"),
            ("b.epub", "b.epub"),
            ("c.epub", "c.epub"),
            ("d.epub", "d.epub"),
            ("e.epub", "e.epub"),
        ),
        guess_name=lambda path, _original: {
            "a.epub": "[김현] 더 콜로니 1권.epub",
            "b.epub": "[김현] 더 콜로니 2권.epub",
            "c.epub": "[김현] 더 콜로니 3권.epub",
            "d.epub": "[김현] 더 콜로니 4권.epub",
            "e.epub": "[김현] 더 콜로니 5화.epub",
        }[path],
    )

    assert [row.new_name for row in rows] == [
        "[김현] 더 콜로니 1권.epub",
        "[김현] 더 콜로니 2권.epub",
        "[김현] 더 콜로니 3권.epub",
        "[김현] 더 콜로니 4권.epub",
        "[김현] 더 콜로니 5권.epub",
    ]


def test_build_rename_preview_rows_unifies_author_by_authorless_series_key():
    rows = build_rename_preview_rows(
        (
            ("a.epub", "a.epub"),
            ("b.epub", "b.epub"),
            ("c.epub", "c.epub"),
        ),
        guess_name=lambda path, _original: {
            "a.epub": "[조병래] 같은 꿈을 꾸다 in 삼국지 7권.epub",
            "b.epub": "[너와같은꿈] 같은 꿈을 꾸다 in 삼국지 8권.epub",
            "c.epub": "[조경래] 같은 꿈을 꾸다 in 삼국지 9권.epub",
        }[path],
    )
    assert [row.new_name for row in rows] == [
        "[조경래] 같은 꿈을 꾸다 in 삼국지 7권.epub",
        "[조경래] 같은 꿈을 꾸다 in 삼국지 8권.epub",
        "[조경래] 같은 꿈을 꾸다 in 삼국지 9권.epub",
    ]
