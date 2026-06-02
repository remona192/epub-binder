from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.grouping import build_series_groups, normalize_group_key  # noqa: E402
from epub_binder_core.title_parser import series_zip_key_from_filename  # noqa: E402


def _legacy_fallback_group_shape(sources):
    groups: dict[str, list[tuple[str, str]]] = {}
    canonical: dict[str, str] = {}
    for path, name in sources:
        key = series_zip_key_from_filename(name, keep_author=True)
        norm_key = normalize_group_key(key)
        if norm_key not in canonical:
            canonical[norm_key] = key
        groups.setdefault(norm_key, []).append((path, name))

    single_file_count = sum(1 for items in groups.values() if len(items) < 2)
    groups = {key: value for key, value in groups.items() if len(value) >= 2}
    return groups, canonical, single_file_count


def test_series_zip_key_strips_dash_part_numbers():
    assert series_zip_key_from_filename("어떤 시리즈 1-1.epub") == "어떤 시리즈"
    assert series_zip_key_from_filename("어떤 시리즈 1-2.epub") == "어떤 시리즈"
    assert series_zip_key_from_filename("어떤 시리즈 1.1.epub") == "어떤 시리즈"


def test_series_zip_key_keeps_author_while_stripping_serial_tail():
    assert series_zip_key_from_filename("[작가] 어떤 시리즈 1.epub") == "[작가] 어떤 시리즈"
    assert series_zip_key_from_filename("[작가] 어떤 시리즈 외전.epub") == "[작가] 어떤 시리즈"


def test_build_series_groups_excludes_single_files_and_normalizes_spacing():
    result = build_series_groups(
        (
            ("a.epub", "버림받은 황비 1.epub"),
            ("b.epub", "버림 받은 황비 2.epub"),
            ("c.epub", "혼자 있는 책.epub"),
        )
    )

    assert result.single_file_count == 1
    assert len(result.groups) == 1
    group = result.groups[0]
    assert normalize_group_key(group.key) == normalize_group_key("버림받은 황비")
    assert group.items == (
        ("a.epub", "버림받은 황비 1.epub"),
        ("b.epub", "버림 받은 황비 2.epub"),
    )


def test_build_series_groups_keeps_dash_part_variants_together():
    result = build_series_groups(
        (
            ("a.epub", "어떤 시리즈 1-1.epub"),
            ("b.epub", "어떤 시리즈 1-2.epub"),
            ("c.epub", "어떤 시리즈 1-1..epub"),
        )
    )

    assert result.single_file_count == 0
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.key == "어떤 시리즈"
    assert group.items == (
        ("a.epub", "어떤 시리즈 1-1.epub"),
        ("b.epub", "어떤 시리즈 1-2.epub"),
        ("c.epub", "어떤 시리즈 1-1..epub"),
    )


def test_build_series_groups_matches_legacy_fallback_shape_for_zip_ui():
    sources = (
        ("a.epub", "[작가] 어떤 시리즈 1-1.epub"),
        ("b.epub", "[작가] 어떤 시리즈 1-2.epub"),
        ("c.epub", "버림받은 황비 1.epub"),
        ("d.epub", "버림 받은 황비 2.epub"),
        ("e.epub", "혼자 있는 책.epub"),
    )

    legacy_groups, legacy_canonical, legacy_single_count = _legacy_fallback_group_shape(sources)
    result = build_series_groups(sources, keep_author=True, min_items=2)

    assert result.single_file_count == legacy_single_count == 1
    assert {group.norm_key: list(group.items) for group in result.groups} == legacy_groups
    assert {group.norm_key: group.key for group in result.groups} == {
        norm_key: legacy_canonical[norm_key]
        for norm_key in legacy_groups
    }


def test_build_series_groups_merges_near_duplicate_series_titles():
    result = build_series_groups(
        (
            ("a.epub", "[간절히] 조선, 봉황이 포효하다 7권.epub"),
            ("b.epub", "[간절히] 조선, 봉황이 포효한다 8권.epub"),
        )
    )
    assert len(result.groups) == 1
    assert len(result.groups[0].items) == 2


def test_build_series_groups_keeps_part_and_side_volume_markers_together():
    result = build_series_groups(
        (
            ("a.epub", "너희들은 변호됐다 17권(2부).epub"),
            ("b.epub", "너희들은 변호됐다 29권 (완결).epub"),
            ("c.epub", "너희들은 변호됐다 8권.epub"),
            ("d.epub", "다른 작품 1권.epub"),
        )
    )

    assert result.single_file_count == 1
    assert len(result.groups) == 1
    assert result.groups[0].key == "너희들은 변호됐다"
    assert len(result.groups[0].items) == 3
