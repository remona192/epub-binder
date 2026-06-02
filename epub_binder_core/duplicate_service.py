from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import shutil
import time

from .duplicate_cleanup import (
    DEFAULT_EXT_PRIORITY,
    DuplicateGroup,
    apply_content_hashes_to_groups,
    build_duplicate_groups,
)


@dataclass(frozen=True)
class MoveRecord:
    source_path: str
    trash_path: str
    keeper_path: str


@dataclass(frozen=True)
class CleanupRunResult:
    trash_dir: str
    moved: tuple[MoveRecord, ...]
    log_path: str


@dataclass(frozen=True)
class RestoreRecord:
    source_path: str
    restored_path: str


@dataclass(frozen=True)
class RestoreRunResult:
    trash_dir: str
    restored: tuple[RestoreRecord, ...]
    conflicts: tuple[MoveRecord, ...]
    missing: tuple[MoveRecord, ...]
    log_path: str


def normalize_extensions(value: str | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, str):
        raw = value.replace(";", ",").replace(" ", ",").split(",")
    else:
        raw = list(value)
    out: list[str] = []
    for item in raw:
        ext = str(item or "").strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        if ext not in out:
            out.append(ext)
    return tuple(out)


def scan_duplicate_folder(
    folder: str | Path,
    *,
    extensions: str | list[str] | tuple[str, ...] = DEFAULT_EXT_PRIORITY,
    recursive: bool = False,
    keep_per_extension: bool = True,
    ext_priority: tuple[str, ...] = DEFAULT_EXT_PRIORITY,
    fuzzy_match: bool = False,
    fuzzy_threshold: float = 0.72,
    verify_hash: bool = False,
) -> list[DuplicateGroup]:
    root = Path(folder)
    exts = set(normalize_extensions(extensions))
    iterator = root.rglob("*") if recursive else root.glob("*")
    paths = [
        path
        for path in iterator
        if path.is_file() and path.suffix.lower() in exts and not _is_in_dedupe_trash(path)
    ]
    groups = build_duplicate_groups(
        paths,
        keep_per_extension=keep_per_extension,
        ext_priority=ext_priority,
        fuzzy_match=fuzzy_match,
        fuzzy_threshold=fuzzy_threshold,
    )
    if not verify_hash:
        return groups

    hash_paths = _candidate_paths_requiring_hash(groups)
    if not hash_paths:
        return groups
    content_hashes = _build_content_hashes([Path(path) for path in sorted(hash_paths)])
    return build_duplicate_groups(
        paths,
        keep_per_extension=keep_per_extension,
        ext_priority=ext_priority,
        fuzzy_match=fuzzy_match,
        fuzzy_threshold=fuzzy_threshold,
        content_hashes=content_hashes,
        content_hash_paths=hash_paths,
    )


def _build_content_hashes(paths: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in paths:
        try:
            hashes[str(path.resolve())] = _sha256_file(path)
        except OSError:
            continue
    return hashes


def verify_duplicate_groups_hashes(
    groups: list[DuplicateGroup],
    *,
    ext_priority: tuple[str, ...] = DEFAULT_EXT_PRIORITY,
) -> list[DuplicateGroup]:
    hash_paths = _candidate_paths_requiring_hash(groups)
    if not hash_paths:
        return groups
    content_hashes = _build_content_hashes([Path(path) for path in sorted(hash_paths)])
    return apply_content_hashes_to_groups(
        groups,
        content_hashes,
        hash_paths,
        ext_priority=ext_priority,
    )


def _candidate_paths_requiring_hash(groups: list[DuplicateGroup]) -> set[str]:
    paths: set[str] = set()
    for group in groups:
        by_range: dict[tuple[int | None, int | None], list[str]] = {}
        for decision in group.decisions:
            candidate = decision.candidate
            key = (candidate.range_start, candidate.range_end)
            by_range.setdefault(key, []).append(str(Path(candidate.path).resolve()))
        for range_key, range_paths in by_range.items():
            if len(range_paths) < 2:
                continue
            # Exact same range is worth hashing. Different ranges are expected
            # to differ in content, so hashing them only adds noise and time.
            if range_key[0] is not None and range_key[1] is not None:
                paths.update(range_paths)
            elif len(by_range) == 1:
                paths.update(range_paths)
    return paths


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_in_dedupe_trash(path: Path) -> bool:
    return any(part.startswith("_dedupe_trash_") for part in path.parts)


def move_duplicate_candidates_to_trash(
    groups: list[DuplicateGroup],
    selected_paths: set[str],
    *,
    root_folder: str | Path,
) -> CleanupRunResult:
    root = Path(root_folder).resolve()
    trash_dir = root / f"_dedupe_trash_{time.strftime('%Y%m%d_%H%M%S')}"
    trash_dir.mkdir(parents=True, exist_ok=True)
    moved: list[MoveRecord] = []
    seen: set[str] = set()
    to_move: list[tuple[DuplicateGroup, object, Path, Path]] = []

    for group in groups:
        for candidate in group.removable:
            source = Path(candidate.path).resolve()
            source_key = str(source)
            if source_key in seen or source_key not in selected_paths:
                continue
            seen.add(source_key)
            try:
                rel = source.relative_to(root)
            except ValueError:
                raise ValueError(f"작업 폴더 밖 파일은 이동할 수 없습니다: {source}")
            if _is_in_dedupe_trash(source):
                raise ValueError(f"격리 폴더 안 파일은 다시 이동하지 않습니다: {source}")
            if not source.exists():
                raise FileNotFoundError(f"스캔 후 파일이 사라졌습니다: {source}")
            stat = source.stat()
            if int(stat.st_size) != candidate.size or abs(float(stat.st_mtime) - candidate.mtime) > 1.0:
                raise RuntimeError(f"스캔 후 파일이 변경되었습니다. 다시 스캔해 주세요: {source}")
            target = _unique_path(trash_dir / rel)
            to_move.append((group, candidate, source, target))

    for group, _candidate, source, target in to_move:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        moved.append(MoveRecord(str(source), str(target), str(Path(group.keeper.path).resolve())))

    log_path = trash_dir / "dedupe_move_log.json"
    log_path.write_text(
        json.dumps(
            {
                "root": str(root),
                "moved": [record.__dict__ for record in moved],
                "kept": [
                    {
                        "group": group.display_title,
                        "keeper_path": str(Path(group.keeper.path).resolve()),
                        "removable": [str(Path(candidate.path).resolve()) for candidate in group.removable],
                    }
                    for group in groups
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return CleanupRunResult(str(trash_dir), tuple(moved), str(log_path))


def restore_latest_dedupe_trash(root_folder: str | Path) -> RestoreRunResult:
    root = Path(root_folder).resolve()
    trash_dir = _latest_trash_dir(root)
    if trash_dir is None:
        raise FileNotFoundError("복구할 _dedupe_trash 폴더가 없습니다.")
    return restore_dedupe_trash(trash_dir, root_folder=root)


def restore_dedupe_trash(trash_dir: str | Path, *, root_folder: str | Path | None = None) -> RestoreRunResult:
    trash = Path(trash_dir).resolve()
    log_path = trash / "dedupe_move_log.json"
    if not log_path.exists():
        raise FileNotFoundError(f"이동 로그가 없습니다: {log_path}")
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    root = Path(root_folder or payload.get("root") or trash.parent).resolve()
    restored: list[RestoreRecord] = []
    conflicts: list[MoveRecord] = []
    missing: list[MoveRecord] = []

    for raw in payload.get("moved", []):
        record = MoveRecord(
            str(raw.get("source_path", "")),
            str(raw.get("trash_path", "")),
            str(raw.get("keeper_path", "")),
        )
        source = Path(record.source_path).resolve()
        trash_path = Path(record.trash_path).resolve()
        try:
            source.relative_to(root)
            trash_path.relative_to(trash)
        except ValueError:
            conflicts.append(record)
            continue
        if source.exists():
            conflicts.append(record)
            continue
        if not trash_path.exists():
            missing.append(record)
            continue
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(trash_path), str(source))
        restored.append(RestoreRecord(str(trash_path), str(source)))

    _remove_empty_dirs(trash)
    return RestoreRunResult(
        str(trash),
        tuple(restored),
        tuple(conflicts),
        tuple(missing),
        str(log_path),
    )


def _latest_trash_dir(root: Path) -> Path | None:
    candidates = [
        path
        for path in root.glob("_dedupe_trash_*")
        if path.is_dir() and (path / "dedupe_move_log.json").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _remove_empty_dirs(path: Path) -> None:
    for child in sorted((item for item in path.rglob("*") if item.is_dir()), key=lambda item: len(item.parts), reverse=True):
        try:
            child.rmdir()
        except OSError:
            pass
    try:
        path.rmdir()
    except OSError:
        pass


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1
