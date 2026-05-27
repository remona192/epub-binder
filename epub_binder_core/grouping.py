from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re

from .title_parser import series_zip_key_from_filename


@dataclass(frozen=True)
class SeriesGroup:
    norm_key: str
    key: str
    items: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SeriesGroupingResult:
    groups: tuple[SeriesGroup, ...]
    single_file_count: int
    all_group_count: int
    single_items: tuple[tuple[str, str], ...] = ()  # (path, display_name) 낱개 파일들


def normalize_group_key(key: str) -> str:
    return re.sub(r"[\s._\-]+", "", key or "").lower()


def _split_author_key(key: str) -> tuple[str, str]:
    m = re.match(r"^\[([^\]]+)\]\s*(.+)$", key or "")
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", (key or "").strip()


def build_series_groups(
    sources: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    *,
    keep_author: bool = True,
    min_items: int = 2,
) -> SeriesGroupingResult:
    """Group display filenames by normalized series key for ZIP/7z bundling.

    ``sources`` contains ``(path, display_name)`` pairs. The return value keeps
    the first display form as the canonical archive label, matching the legacy
    GUI behavior.
    """
    grouped: dict[str, list[tuple[str, str]]] = {}
    canonical: dict[str, str] = {}

    for path, display_name in sources:
        key = series_zip_key_from_filename(display_name, keep_author=keep_author)
        norm_key = normalize_group_key(key)
        if not norm_key:
            continue
        canonical.setdefault(norm_key, key)
        grouped.setdefault(norm_key, []).append((path, display_name))

    # 오탈자/표기차(예: 포효하다 vs 포효한다)로 분리된 그룹을 보수적으로 병합
    norm_keys = list(grouped.keys())
    for i, left in enumerate(norm_keys):
        if left not in grouped:
            continue
        left_key = canonical.get(left, "")
        left_author, left_title = _split_author_key(left_key)
        for right in norm_keys[i + 1:]:
            if right not in grouped:
                continue
            right_key = canonical.get(right, "")
            right_author, right_title = _split_author_key(right_key)
            if left_author != right_author:
                continue
            if not left_title or not right_title:
                continue
            ratio = SequenceMatcher(None, left_title, right_title).ratio()
            if ratio < 0.88:
                continue
            if len(grouped[left]) >= len(grouped[right]):
                grouped[left].extend(grouped[right])
                grouped.pop(right, None)
                canonical.pop(right, None)
            else:
                grouped[right].extend(grouped[left])
                grouped.pop(left, None)
                canonical.pop(left, None)
                break

    single_file_count = sum(1 for items in grouped.values() if len(items) < min_items)
    single_items = tuple(
        item
        for items in grouped.values()
        if len(items) < min_items
        for item in items
    )
    groups = tuple(
        SeriesGroup(
            norm_key=norm_key,
            key=canonical[norm_key],
            items=tuple(items),
        )
        for norm_key, items in grouped.items()
        if len(items) >= min_items
    )
    return SeriesGroupingResult(
        groups=groups,
        single_file_count=single_file_count,
        all_group_count=len(grouped),
        single_items=single_items,
    )
