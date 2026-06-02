from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.duplicate_cleanup import build_duplicate_groups, parse_duplicate_candidate
from epub_binder_core.duplicate_service import (
    move_duplicate_candidates_to_trash,
    restore_latest_dedupe_trash,
    scan_duplicate_folder,
    verify_duplicate_groups_hashes,
)


def _touch(path: Path, size: int = 10):
    path.write_bytes(b"x" * size)
    return path


def test_duplicate_candidate_parses_complete_range_and_author(tmp_path):
    path = _touch(tmp_path / "[작가] 작품 이름 1-210 완결.epub", 20)

    candidate = parse_duplicate_candidate(path)

    assert candidate.author == "작가"
    assert candidate.display_title == "작품 이름"
    assert candidate.complete is True
    assert candidate.incomplete is False
    assert candidate.range_start == 1
    assert candidate.range_end == 210


def test_duplicate_group_prefers_complete_wider_range_and_extension(tmp_path):
    paths = [
        _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300),
        _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100),
        _touch(tmp_path / "[작가] 작품 이름 1-210 완결.epub", 50),
    ]

    groups = build_duplicate_groups(paths, keep_per_extension=False)

    assert len(groups) == 1
    assert groups[0].keeper.name == "[작가] 작품 이름 1-210 완결.epub"
    assert {item.name for item in groups[0].removable} == {
        "[작가] 작품 이름 1-175 미완.txt",
        "[작가] 작품 이름 1-210 완결.txt",
    }


def test_duplicate_group_keeps_one_per_extension_when_enabled(tmp_path):
    paths = [
        _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300),
        _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100),
        _touch(tmp_path / "[작가] 작품 이름 1-210 완결.epub", 50),
    ]

    groups = build_duplicate_groups(paths, keep_per_extension=True)

    assert len(groups) == 1
    assert groups[0].keeper.name == "[작가] 작품 이름 1-210 완결.txt"
    assert [item.name for item in groups[0].removable] == ["[작가] 작품 이름 1-175 미완.txt"]


def test_duplicate_candidate_humanizes_underscore_range_and_at_author(tmp_path):
    path = _touch(tmp_path / "크툴루_세계관에_광기를_숨김_1_200_完,_후기_포함_@불멸의밤.txt", 20)

    candidate = parse_duplicate_candidate(path)

    assert candidate.author == "불멸의밤"
    assert candidate.display_title == "크툴루 세계관에 광기를 숨김"
    assert candidate.complete is True
    assert candidate.range_start == 1
    assert candidate.range_end == 200
    assert "작가 없음" not in candidate.risky


def test_duplicate_group_matches_same_filename_even_when_only_one_has_author(tmp_path):
    old = _touch(tmp_path / "크툴루 세계관에 광기를 숨김 1-186.txt", 10)
    new = _touch(tmp_path / "크툴루_세계관에_광기를_숨김_1_200_完,_후기_포함_@불멸의밤.txt", 20)

    groups = build_duplicate_groups([old, new], keep_per_extension=True)

    assert len(groups) == 1
    assert groups[0].keeper.name == new.name
    assert [item.name for item in groups[0].removable] == [old.name]


def test_duplicate_group_does_not_merge_separate_volumes(tmp_path):
    paths = [
        _touch(tmp_path / "[녹오미] N번째 인생 1권.txt", 10),
        _touch(tmp_path / "[녹오미] N번째 인생 2권.txt", 20),
        _touch(tmp_path / "[녹오미] N번째 인생 3권.txt", 30),
        _touch(tmp_path / "[녹오미] N번째 인생 4권 완결.txt", 40),
    ]

    groups = build_duplicate_groups(paths, keep_per_extension=True)

    assert groups == []


def test_duplicate_group_does_not_merge_separate_seasons(tmp_path):
    paths = [
        _touch(tmp_path / "죽은_아내가_돌아왔다_시즌2_1_68화_완결_@황금백수.epub", 10),
        _touch(tmp_path / "죽은_아내가_돌아왔다_시즌1_1_98화_완결_@황금백수.epub", 20),
    ]

    candidates = [parse_duplicate_candidate(path) for path in paths]
    groups = build_duplicate_groups(paths, keep_per_extension=True)

    assert candidates[0].display_title == "죽은 아내가 돌아왔다 시즌2"
    assert candidates[0].range_start == 1
    assert candidates[0].range_end == 68
    assert candidates[1].display_title == "죽은 아내가 돌아왔다 시즌1"
    assert candidates[1].range_start == 1
    assert candidates[1].range_end == 98
    assert groups == []


def test_duplicate_group_does_not_merge_part_with_main_title(tmp_path):
    paths = [
        _touch(tmp_path / "[초코치치] 북부대공의 불면증 2부 (완결).txt", 10),
        _touch(tmp_path / "[초코치치] 북부대공의 불면증.txt", 20),
    ]

    candidates = [parse_duplicate_candidate(path) for path in paths]
    groups = build_duplicate_groups(paths, keep_per_extension=True)

    assert candidates[0].display_title == "북부대공의 불면증 2부"
    assert candidates[0].range_start is None
    assert candidates[0].range_end is None
    assert groups == []


def test_duplicate_group_merges_overlapping_ranges(tmp_path):
    old = _touch(tmp_path / "[작가] 작품 이름 1-90 미완.txt", 10)
    new = _touch(tmp_path / "[작가] 작품 이름 1-100 완결.txt", 20)

    groups = build_duplicate_groups([old, new], keep_per_extension=True)

    assert len(groups) == 1
    assert groups[0].keeper.name == new.name
    assert [item.name for item in groups[0].removable] == [old.name]


def test_fuzzy_match_is_opt_in_and_marks_low_confidence(tmp_path):
    old = _touch(tmp_path / "크툴루 세계관에 광기를 숨김 1-186.txt", 10)
    variant = _touch(tmp_path / "크툴루 세계관 광기를 숨김 1-200 완결.txt", 20)

    exact_groups = build_duplicate_groups([old, variant], keep_per_extension=True)
    fuzzy_groups = build_duplicate_groups([old, variant], keep_per_extension=True, fuzzy_match=True)

    assert exact_groups == []
    assert len(fuzzy_groups) == 1
    assert fuzzy_groups[0].confidence == "낮음"
    assert "유사 제목 확인 필요" in fuzzy_groups[0].warnings
    assert fuzzy_groups[0].keeper.name == variant.name
    assert [item.name for item in fuzzy_groups[0].removable] == [old.name]


def test_scan_duplicate_folder_can_enable_fuzzy_match(tmp_path):
    _touch(tmp_path / "재벌집 막내아들 1-100.txt", 10)
    _touch(tmp_path / "재벌가 막내아들 1-120 완결.txt", 20)

    exact_groups = scan_duplicate_folder(tmp_path, extensions="txt", fuzzy_match=False)
    fuzzy_groups = scan_duplicate_folder(tmp_path, extensions="txt", fuzzy_match=True)

    assert exact_groups == []
    assert len(fuzzy_groups) == 1
    assert fuzzy_groups[0].confidence == "낮음"


def test_hash_verification_marks_same_hash(tmp_path):
    left = tmp_path / "같은 작품 1-100.txt"
    right = tmp_path / "같은 작품 1-100 완결.txt"
    left.write_bytes(b"same content")
    right.write_bytes(b"same content")

    groups = scan_duplicate_folder(tmp_path, extensions="txt", verify_hash=True)

    assert len(groups) == 1
    assert groups[0].confidence == "중간"
    assert "해시 일치" in groups[0].warnings


def test_partial_hash_verification_does_not_mark_same_hash(tmp_path):
    left = _touch(tmp_path / "같은 작품 1-100.txt", 10)
    right = _touch(tmp_path / "같은 작품 1-100 완결.txt", 20)
    content_hashes = {
        str(left.resolve()): "hash-left",
    }

    groups = build_duplicate_groups([left, right], keep_per_extension=True, content_hashes=content_hashes)

    assert len(groups) == 1
    assert groups[0].confidence == "낮음"
    assert "해시 일부 미확인" in groups[0].warnings
    assert "해시 일치" not in groups[0].warnings


def test_hash_verification_marks_different_hash_as_low_confidence(tmp_path):
    left = tmp_path / "같은 작품 1-100.txt"
    right = tmp_path / "같은 작품 1-100 완결.txt"
    left.write_bytes(b"left content")
    right.write_bytes(b"right content")

    groups = scan_duplicate_folder(tmp_path, extensions="txt", verify_hash=True)

    assert len(groups) == 1
    assert groups[0].confidence == "낮음"
    assert "해시 다름 확인 필요" in groups[0].warnings


def test_hash_verification_skips_different_ranges(tmp_path):
    left = tmp_path / "같은 작품 1-90 미완.txt"
    right = tmp_path / "같은 작품 1-100 완결.txt"
    left.write_bytes(b"left content")
    right.write_bytes(b"right content")

    groups = scan_duplicate_folder(tmp_path, extensions="txt", verify_hash=True)

    assert len(groups) == 1
    assert groups[0].keeper.name == right.name
    assert "해시 다름 확인 필요" not in groups[0].warnings
    assert "해시 일부 미확인" not in groups[0].warnings


def test_verify_duplicate_groups_hashes_updates_selected_groups_only(tmp_path):
    same_left = tmp_path / "같은 범위 작품 1-100.txt"
    same_right = tmp_path / "같은 범위 작품 1-100 완결.txt"
    diff_left = tmp_path / "다른 범위 작품 1-90 미완.txt"
    diff_right = tmp_path / "다른 범위 작품 1-100 완결.txt"
    same_left.write_bytes(b"same content")
    same_right.write_bytes(b"same content")
    diff_left.write_bytes(b"left content")
    diff_right.write_bytes(b"right content")

    groups = scan_duplicate_folder(tmp_path, extensions="txt", verify_hash=False)
    selected = [group for group in groups if group.display_title == "같은 범위 작품"]

    refreshed = verify_duplicate_groups_hashes(selected)

    assert len(refreshed) == 1
    assert "해시 일치" in refreshed[0].warnings
    assert all("다른 범위 작품" not in decision.candidate.name for decision in refreshed[0].decisions)


def test_scan_duplicate_folder_ignores_dedupe_trash_folder(tmp_path):
    trash = tmp_path / "_dedupe_trash_20260521_120000"
    trash.mkdir()
    _touch(trash / "같은 작품 1-100.txt", 10)
    _touch(trash / "같은 작품 1-100 완결.txt", 20)

    groups = scan_duplicate_folder(tmp_path, extensions="txt", recursive=True)

    assert groups == []


def test_move_refuses_when_candidate_changed_after_scan(tmp_path):
    keep = _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100)
    remove = _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300)
    groups = scan_duplicate_folder(tmp_path, extensions="txt", keep_per_extension=True)
    selected = {str(Path(item.path).resolve()) for group in groups for item in group.removable}
    remove.write_bytes(b"changed")

    try:
        move_duplicate_candidates_to_trash(groups, selected, root_folder=tmp_path)
    except RuntimeError as exc:
        assert "다시 스캔" in str(exc)
    else:
        raise AssertionError("changed candidate should not be moved")

    assert keep.exists()
    assert remove.exists()


def test_scan_and_move_duplicate_candidates_to_trash(tmp_path):
    keep = _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100)
    remove = _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300)
    _touch(tmp_path / "[다른] 다른 작품 1-10 완결.txt", 10)

    groups = scan_duplicate_folder(tmp_path, extensions="txt", keep_per_extension=True)
    selected = {str(Path(item.path).resolve()) for group in groups for item in group.removable}

    result = move_duplicate_candidates_to_trash(groups, selected, root_folder=tmp_path)

    assert keep.exists()
    assert not remove.exists()
    assert len(result.moved) == 1
    assert Path(result.moved[0].keeper_path).resolve() == keep.resolve()
    assert Path(result.moved[0].trash_path).exists()
    assert Path(result.log_path).exists()


def test_restore_latest_dedupe_trash_restores_moved_files(tmp_path):
    keep = _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100)
    remove = _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300)
    groups = scan_duplicate_folder(tmp_path, extensions="txt", keep_per_extension=True)
    selected = {str(Path(item.path).resolve()) for group in groups for item in group.removable}
    move_result = move_duplicate_candidates_to_trash(groups, selected, root_folder=tmp_path)

    restore_result = restore_latest_dedupe_trash(tmp_path)

    assert keep.exists()
    assert remove.exists()
    assert len(restore_result.restored) == 1
    assert restore_result.conflicts == ()
    assert restore_result.missing == ()
    assert not Path(move_result.moved[0].trash_path).exists()


def test_restore_latest_dedupe_trash_skips_existing_destination(tmp_path):
    remove = _touch(tmp_path / "[작가] 작품 이름 1-175 미완.txt", 300)
    keep = _touch(tmp_path / "[작가] 작품 이름 1-210 완결.txt", 100)
    groups = scan_duplicate_folder(tmp_path, extensions="txt", keep_per_extension=True)
    selected = {str(Path(item.path).resolve()) for group in groups for item in group.removable}
    move_duplicate_candidates_to_trash(groups, selected, root_folder=tmp_path)
    remove.write_bytes(b"new file")

    restore_result = restore_latest_dedupe_trash(tmp_path)

    assert remove.read_bytes() == b"new file"
    assert keep.exists()
    assert restore_result.restored == ()
    assert len(restore_result.conflicts) == 1
