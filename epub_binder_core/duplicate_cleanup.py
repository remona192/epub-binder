from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re


DEFAULT_EXT_PRIORITY = (".epub", ".txt", ".zip", ".7z", ".rar", ".pdf")
_HASH_MISSING = "__HASH_MISSING__"


@dataclass(frozen=True)
class DuplicateCandidate:
    path: str
    name: str
    ext: str
    size: int
    mtime: float
    author: str
    title_key: str
    display_title: str
    complete: bool
    incomplete: bool
    range_start: int | None
    range_end: int | None
    side_story: bool
    risky: tuple[str, ...] = ()
    content_hash: str = ""


@dataclass(frozen=True)
class DuplicateDecision:
    candidate: DuplicateCandidate
    keep: bool
    reason: str


@dataclass(frozen=True)
class DuplicateGroup:
    key: str
    display_title: str
    decisions: tuple[DuplicateDecision, ...]
    confidence: str
    warnings: tuple[str, ...] = ()

    @property
    def keeper(self) -> DuplicateCandidate:
        return next(decision.candidate for decision in self.decisions if decision.keep)

    @property
    def removable(self) -> tuple[DuplicateCandidate, ...]:
        return tuple(decision.candidate for decision in self.decisions if not decision.keep)


_COMPLETE_RE = re.compile(
    r"(?:\[\s*(?:완|完|완결)\s*\]|\(\s*(?:완|完|완결)\s*\)|\{\s*(?:완|完|완결)\s*\}|"
    r"(?<!미)완결|(?<!미)完|(?<!미)\bfin\b)",
    re.IGNORECASE,
)
_INCOMPLETE_RE = re.compile(r"(?:미완|미완결|연중|중단|incomplete)", re.IGNORECASE)
_SIDE_RE = re.compile(r"(?:본편\+외전|외전|번외|특전|특별\s*외전|합본)", re.IGNORECASE)
_DANGER_RE = re.compile(r"(?:구버전|old|backup|백업|깨짐|임시|중복|복사본)", re.IGNORECASE)
_AUTHOR_RE = re.compile(r"^\s*\[([^\]]{1,80})\]\s*(.+)$")
_AT_AUTHOR_RE = re.compile(r"(?:^|[\s_])@([^@\[\]\(\)\{\},]{1,80})\s*$")
_RANGE_RE = re.compile(r"(?<![0-9A-Za-z가-힣])(\d{1,5})\s*[-~_]\s*(\d{1,5})(?:\s*[화권부장회])?")


def _norm_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("_", " ")).strip()


def _sortable_text(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", value).lower()


def _parse_range(stem: str) -> tuple[int | None, int | None]:
    ranges: list[tuple[int, int]] = []
    for match in _RANGE_RE.finditer(stem):
        left, right = int(match.group(1)), int(match.group(2))
        ranges.append((min(left, right), max(left, right)))
    if ranges:
        return min(start for start, _end in ranges), max(end for _start, end in ranges)
    return None, None


def _strip_noise_for_title(stem: str) -> str:
    text = _AT_AUTHOR_RE.sub(" ", stem)
    text = _RANGE_RE.sub(" ", text)
    text = _norm_spaces(text)
    text = _AUTHOR_RE.sub(r"\2", text)
    text = re.sub(r"[\[\(\{（][^\]\)\}）]*(?:미완|미완결|완결|완|完|연중|중단|incomplete|fin)[^\]\)\}）]*[\]\)\}）]", " ", text, flags=re.IGNORECASE)
    text = _RANGE_RE.sub(" ", text)
    text = re.sub(r"(?:미완결?|완결|完|연중|중단|incomplete|\bfin\b|후기\s*포함)", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:txt|epub|zip|pdf|rar|7z)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*[,，]\s*$", " ", text)
    return _norm_spaces(text)


def parse_duplicate_candidate(path: str | Path) -> DuplicateCandidate:
    file_path = Path(path)
    stem = file_path.stem
    author = ""
    body_raw = stem
    match = _AUTHOR_RE.match(stem)
    if match:
        author = _norm_spaces(match.group(1))
        body_raw = match.group(2)
    at_match = _AT_AUTHOR_RE.search(body_raw)
    if at_match:
        if not author:
            author = _norm_spaces(at_match.group(1))
        body_raw = body_raw[:at_match.start()].rstrip(" _-.,，")
    body = _norm_spaces(body_raw)
    title_text = _strip_noise_for_title(body_raw)
    side_story = bool(_SIDE_RE.search(body))
    side_key = "side" if side_story else "main"
    title_key = _sortable_text(title_text)
    range_start, range_end = _parse_range(body_raw)
    complete = bool(_COMPLETE_RE.search(body)) and not bool(_INCOMPLETE_RE.search(body))
    incomplete = bool(_INCOMPLETE_RE.search(body))
    risky: list[str] = []
    if side_story:
        risky.append("외전/합본")
    if range_end is None:
        risky.append("범위 없음")
    if _DANGER_RE.search(body):
        risky.append("위험 태그")

    try:
        stat = file_path.stat()
        size = int(stat.st_size)
        mtime = float(stat.st_mtime)
    except OSError:
        size = 0
        mtime = 0.0

    return DuplicateCandidate(
        path=str(file_path),
        name=file_path.name,
        ext=file_path.suffix.lower(),
        size=size,
        mtime=mtime,
        author=author,
        title_key=f"{title_key}|{side_key}",
        display_title=title_text or _norm_spaces(stem),
        complete=complete,
        incomplete=incomplete,
        range_start=range_start,
        range_end=range_end,
        side_story=side_story,
        risky=tuple(risky),
    )


def _ext_rank(ext: str, ext_priority: tuple[str, ...]) -> int:
    normalized = tuple(item.lower() if item.startswith(".") else f".{item.lower()}" for item in ext_priority)
    try:
        return normalized.index(ext.lower())
    except ValueError:
        return len(normalized) + 10


def candidate_score(candidate: DuplicateCandidate, ext_priority: tuple[str, ...] = DEFAULT_EXT_PRIORITY) -> tuple:
    range_end = candidate.range_end or 0
    range_span = (candidate.range_end or 0) - (candidate.range_start or 0)
    risky_penalty = len(candidate.risky)
    return (
        1 if candidate.complete else 0,
        0 if candidate.incomplete else 1,
        range_end,
        range_span,
        -_ext_rank(candidate.ext, ext_priority),
        candidate.size,
        candidate.mtime,
        -risky_penalty,
    )


def build_duplicate_groups(
    paths: list[str | Path],
    *,
    keep_per_extension: bool = True,
    ext_priority: tuple[str, ...] = DEFAULT_EXT_PRIORITY,
    fuzzy_match: bool = False,
    fuzzy_threshold: float = 0.72,
    content_hashes: dict[str, str] | None = None,
    content_hash_paths: set[str] | None = None,
) -> list[DuplicateGroup]:
    candidates: list[DuplicateCandidate] = []
    for path in paths:
        candidate = parse_duplicate_candidate(path)
        if not candidate.title_key.split("|")[0]:
            continue
        if content_hashes is not None:
            resolved_path = str(Path(candidate.path).resolve())
            if content_hash_paths is None or resolved_path in content_hash_paths:
                hash_value = content_hashes.get(resolved_path, "")
                candidate = replace(candidate, content_hash=hash_value or _HASH_MISSING)
        candidates.append(candidate)

    candidates = _protect_dash_number_sequences(candidates, keep_per_extension)

    if fuzzy_match:
        buckets = _build_fuzzy_buckets(candidates, keep_per_extension, fuzzy_threshold)
    else:
        buckets = _build_exact_buckets(candidates, keep_per_extension)

    groups: list[DuplicateGroup] = []
    for key, candidates in buckets.items():
        for index, candidate_group in enumerate(_split_non_overlapping_ranges(candidates)):
            if len(candidate_group) < 2:
                continue
            group_key = key if index == 0 else f"{key}|range_group_{index}"
            groups.append(_build_group(group_key, candidate_group, ext_priority))
    return sorted(groups, key=lambda group: _sortable_text(group.display_title))


def apply_content_hashes_to_groups(
    groups: list[DuplicateGroup],
    content_hashes: dict[str, str],
    content_hash_paths: set[str],
    *,
    ext_priority: tuple[str, ...] = DEFAULT_EXT_PRIORITY,
) -> list[DuplicateGroup]:
    refreshed: list[DuplicateGroup] = []
    for group in groups:
        candidates: list[DuplicateCandidate] = []
        for decision in group.decisions:
            candidate = decision.candidate
            resolved_path = str(Path(candidate.path).resolve())
            if resolved_path in content_hash_paths:
                hash_value = content_hashes.get(resolved_path, "")
                candidate = replace(candidate, content_hash=hash_value or _HASH_MISSING)
            candidates.append(candidate)
        refreshed.append(_build_group(group.key, candidates, ext_priority))
    return refreshed


def _build_exact_buckets(
    candidates: list[DuplicateCandidate],
    keep_per_extension: bool,
) -> dict[str, list[DuplicateCandidate]]:
    buckets: dict[str, list[DuplicateCandidate]] = {}
    for candidate in candidates:
        key = _dedupe_bucket_key(candidate, keep_per_extension)
        buckets.setdefault(key, []).append(candidate)
    return buckets


def _build_fuzzy_buckets(
    candidates: list[DuplicateCandidate],
    keep_per_extension: bool,
    threshold: float,
) -> dict[str, list[DuplicateCandidate]]:
    if not candidates:
        return {}

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    compare_buckets: dict[str, list[int]] = {}
    for index, candidate in enumerate(candidates):
        title = _candidate_title_part(candidate)
        if not title:
            continue
        first = title[0]
        side = _candidate_side_part(candidate)
        key = f"{side}|{first}"
        if keep_per_extension:
            key = f"{key}|{candidate.ext}"
        compare_buckets.setdefault(key, []).append(index)

    for indexes in compare_buckets.values():
        for offset, left_index in enumerate(indexes):
            left = candidates[left_index]
            left_title = _candidate_title_part(left)
            for right_index in indexes[offset + 1:]:
                right = candidates[right_index]
                right_title = _candidate_title_part(right)
                if left_title == right_title or _title_similarity(left_title, right_title) >= threshold:
                    union(left_index, right_index)

    grouped: dict[int, list[DuplicateCandidate]] = {}
    for index, candidate in enumerate(candidates):
        grouped.setdefault(find(index), []).append(candidate)

    buckets: dict[str, list[DuplicateCandidate]] = {}
    for index, items in grouped.items():
        if len(items) < 2:
            continue
        first = items[0]
        key = f"fuzzy|{index}|{_dedupe_bucket_key(first, keep_per_extension)}"
        buckets[key] = items
    return buckets


def _dash_number_pair(name: str) -> tuple[int, int] | None:
    stem = Path(name).stem
    matches = list(re.finditer(r"(?<!\d)(\d{1,4})\s*[-_]\s*(\d{1,4})(?!\d)", stem))
    if not matches:
        return None
    match = matches[-1]
    return int(match.group(1)), int(match.group(2))


def _protect_dash_number_sequences(
    candidates: list[DuplicateCandidate],
    keep_per_extension: bool,
) -> list[DuplicateCandidate]:
    grouped_pairs: dict[tuple[str, str, int], set[tuple[int, int]]] = {}
    candidate_pairs: dict[str, tuple[int, int]] = {}
    for candidate in candidates:
        pair = _dash_number_pair(candidate.name)
        if pair is None:
            continue
        left, right = pair
        key = (
            _candidate_title_part(candidate),
            candidate.ext if keep_per_extension else "",
            left,
        )
        grouped_pairs.setdefault(key, set()).add((left, right))
        candidate_pairs[candidate.path] = pair

    if not grouped_pairs:
        return candidates

    out: list[DuplicateCandidate] = []
    for candidate in candidates:
        pair = candidate_pairs.get(candidate.path)
        if pair is None:
            out.append(candidate)
            continue
        left, right = pair
        key = (
            _candidate_title_part(candidate),
            candidate.ext if keep_per_extension else "",
            left,
        )
        protected = len(grouped_pairs.get(key, set())) > 1
        if protected:
            out.append(replace(candidate, title_key=f"{candidate.title_key}|dashseq:{left}-{right}"))
        else:
            out.append(candidate)
    return out


def _build_group(
    key: str,
    candidates: list[DuplicateCandidate],
    ext_priority: tuple[str, ...],
) -> DuplicateGroup:
    ordered = sorted(
        candidates,
        key=lambda item: (candidate_score(item, ext_priority), item.name.lower()),
        reverse=True,
    )
    keeper = ordered[0]
    authors = {candidate.author for candidate in candidates if candidate.author}
    warnings: list[str] = []
    if len(authors) > 1:
        warnings.append("작가 충돌")
    if any(candidate.side_story for candidate in candidates):
        warnings.append("외전/합본 포함")
    if any("범위 없음" in candidate.risky for candidate in candidates):
        warnings.append("범위 없는 파일 포함")
    if len({_candidate_title_part(candidate) for candidate in candidates}) > 1:
        warnings.append("유사 제목 확인 필요")
    hash_values = [candidate.content_hash for candidate in candidates if candidate.content_hash]
    missing_hash = any(value == _HASH_MISSING for value in hash_values)
    real_hashes = {value for value in hash_values if value and value != _HASH_MISSING}
    if missing_hash:
        warnings.append("해시 일부 미확인")
    elif len(real_hashes) == 1 and real_hashes and len(hash_values) == len(candidates):
        warnings.append("해시 일치")
    elif len(real_hashes) > 1:
        warnings.append("해시 다름 확인 필요")
    confidence = "높음"
    if warnings:
        if warnings == ["해시 일치"]:
            confidence = "중간"
        else:
            confidence = "낮음"

    decisions = []
    for candidate in ordered:
        keep = candidate.path == keeper.path
        if keep:
            reason = _keep_reason(candidate, ext_priority)
        else:
            reason = f"정리 후보: {keeper.name} 우선"
        decisions.append(DuplicateDecision(candidate, keep, reason))

    return DuplicateGroup(
        key=key,
        display_title=keeper.display_title,
        decisions=tuple(decisions),
        confidence=confidence,
        warnings=tuple(warnings),
    )


def _dedupe_bucket_key(candidate: DuplicateCandidate, keep_per_extension: bool) -> str:
    key = candidate.title_key
    if keep_per_extension:
        key = f"{key}|{candidate.ext}"
    return key


def _split_non_overlapping_ranges(candidates: list[DuplicateCandidate]) -> list[list[DuplicateCandidate]]:
    if len(candidates) < 2:
        return [candidates]

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(candidates):
        for right_index in range(left_index + 1, len(candidates)):
            if _ranges_can_be_same_file(left, candidates[right_index]):
                union(left_index, right_index)

    groups: dict[int, list[DuplicateCandidate]] = {}
    for index, candidate in enumerate(candidates):
        groups.setdefault(find(index), []).append(candidate)
    return list(groups.values())


def _ranges_can_be_same_file(left: DuplicateCandidate, right: DuplicateCandidate) -> bool:
    if left.range_start is None or left.range_end is None:
        return True
    if right.range_start is None or right.range_end is None:
        return True
    return max(left.range_start, right.range_start) <= min(left.range_end, right.range_end)


def _candidate_title_part(candidate: DuplicateCandidate) -> str:
    return candidate.title_key.split("|", 1)[0]


def _candidate_side_part(candidate: DuplicateCandidate) -> str:
    parts = candidate.title_key.split("|", 1)
    return parts[1] if len(parts) > 1 else ""


def _title_similarity(left: str, right: str) -> float:
    if not left and not right:
        return 1.0
    longest = max(len(left), len(right))
    if longest == 0:
        return 0.0
    if min(len(left), len(right)) / longest < 0.65:
        return 0.0
    distance = _edit_distance(left, right)
    return (longest - distance) / longest


def _edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            cost = 0 if left_char == right_char else 1
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + cost,
                )
            )
        previous = current
    return previous[-1]


def _keep_reason(candidate: DuplicateCandidate, ext_priority: tuple[str, ...]) -> str:
    parts = ["남김"]
    if candidate.complete:
        parts.append("완결")
    if candidate.range_end:
        parts.append(f"{candidate.range_start}-{candidate.range_end}")
    parts.append(candidate.ext.lstrip(".").upper() or "파일")
    if candidate.size:
        parts.append(f"{candidate.size:,} bytes")
    return " / ".join(parts)
