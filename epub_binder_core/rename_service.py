from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import re

from .grouping import normalize_group_key
from .title_parser import format_rename_name, parse_epub_name, series_zip_key_from_filename


GuessName = Callable[[str, str], str]
SeriesKey = Callable[[str], str]


@dataclass(frozen=True)
class RenamePreviewRow:
    path: str
    original_name: str
    new_name: str


def _canonical_author(valid: list[str], authors: list[str]) -> str:
    counts = Counter(valid)
    max_count = max(counts.values())
    candidates = [author for author, count in counts.items() if count == max_count]
    for author in candidates:
        if any(other != author and other.startswith(author) for other in candidates):
            continue
        if any(author.startswith(other) and other != author for other in candidates):
            return author
    last_pos = {author: pos for pos, author in enumerate(authors) if author}
    return max(candidates, key=lambda author: (-len(author), last_pos.get(author, -1)))


def build_rename_preview_rows(
    rename_files: Iterable[tuple],
    *,
    existing_names: Mapping[str, str] | None = None,
    guess_name: GuessName | None = None,
    series_key_func: SeriesKey | None = None,
) -> tuple[RenamePreviewRow, ...]:
    """Build rename preview rows and normalize series labels across a batch."""

    existing = dict(existing_names or {})
    guess = guess_name or (lambda _path, original_name: original_name)
    series_key = series_key_func or (lambda name: series_zip_key_from_filename(name, keep_author=True))

    rows: list[tuple[str, str, str]] = []
    for item in rename_files:
        if len(item) < 2:
            continue
        path = str(item[0])
        original_name = str(item[1])
        new_name = existing.get(path) or guess(path, original_name)
        rows.append((path, original_name, str(new_name or original_name)))

    norm_to_rows: dict[str, list[int]] = {}
    for index, (_path, _original_name, new_name) in enumerate(rows):
        key = series_key(new_name) or ""
        norm_key = normalize_group_key(key)
        norm_to_rows.setdefault(norm_key, []).append(index)

    corrected = [row[2] for row in rows]
    for _norm_key, indexes in norm_to_rows.items():
        if len(indexes) < 2:
            continue
        keys = [series_key(rows[index][2]) or "" for index in indexes]
        canonical = Counter(keys).most_common(1)[0][0]
        if not canonical:
            continue
        for index, old_key in zip(indexes, keys):
            if old_key and old_key != canonical:
                corrected[index] = corrected[index].replace(old_key, canonical, 1)

    for _norm_key, indexes in norm_to_rows.items():
        if len(indexes) < 2:
            continue
        authors: list[str] = []
        for index in indexes:
            match = re.match(r"^\[([^\]]+)\]", corrected[index])
            authors.append(match.group(1) if match else "")
        valid = [author for author in authors if author]
        if not valid or len(set(valid)) <= 1:
            continue
        canonical_author = _canonical_author(valid, authors)
        for index in indexes:
            match = re.match(r"^\[([^\]]+)\]", corrected[index])
            if match and match.group(1) != canonical_author:
                corrected[index] = f"[{canonical_author}]" + corrected[index][match.end():]

    # 작가명 다수결은 authorless 시리즈 키 기준으로 한 번 더 수행
    authorless_groups: dict[str, list[int]] = {}
    for index, name in enumerate(corrected):
        parsed = parse_epub_name(original_name=name)
        bare = re.sub(r'^\[[^\]]+\]\s*', '', parsed.series or '')
        key = normalize_group_key(bare)
        if key:
            authorless_groups.setdefault(key, []).append(index)
    for _key, indexes in authorless_groups.items():
        if len(indexes) < 2:
            continue
        authors: list[str] = []
        for index in indexes:
            match = re.match(r"^\[([^\]]+)\]", corrected[index])
            authors.append(match.group(1) if match else "")
        valid = [author for author in authors if author]
        if not valid or len(set(valid)) <= 1:
            continue
        canonical_author = _canonical_author(valid, authors)
        for index in indexes:
            match = re.match(r"^\[([^\]]+)\]", corrected[index])
            if match and match.group(1) != canonical_author:
                corrected[index] = f"[{canonical_author}]" + corrected[index][match.end():]

    # 같은 시리즈 내 권/화 표기가 섞인 경우 다수 단위로 통일
    for _norm_key, indexes in norm_to_rows.items():
        if len(indexes) < 2:
            continue
        parsed_rows = [parse_epub_name(original_name=corrected[index]) for index in indexes]
        volume_count = sum(1 for parsed in parsed_rows if parsed.volume)
        episode_count = sum(1 for parsed in parsed_rows if parsed.episode and not parsed.volume)
        if not volume_count or not episode_count:
            continue
        target_unit = "volume" if volume_count >= episode_count else "episode"
        for idx, parsed in zip(indexes, parsed_rows):
            if target_unit == "volume" and parsed.episode and not parsed.volume and not parsed.part:
                updated = type(parsed)(
                    author=parsed.author,
                    series=parsed.series,
                    volume=f"{int(parsed.episode)}권",
                    part=parsed.part,
                    episode="",
                    suffix=parsed.suffix,
                    filename=parsed.filename,
                    completed=parsed.completed,
                )
                corrected[idx] = format_rename_name(updated)
            elif target_unit == "episode" and parsed.volume and not parsed.part:
                vol_m = re.search(r"(\d+)", parsed.volume)
                if not vol_m:
                    continue
                updated = type(parsed)(
                    author=parsed.author,
                    series=parsed.series,
                    volume="",
                    part=parsed.part,
                    episode=str(int(vol_m.group(1))),
                    suffix=parsed.suffix,
                    filename=parsed.filename,
                    completed=parsed.completed,
                )
                corrected[idx] = format_rename_name(updated)

    return tuple(
        RenamePreviewRow(path, original_name, new_name)
        for (path, original_name, _old_name), new_name in zip(rows, corrected)
    )
