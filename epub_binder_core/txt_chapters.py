from __future__ import annotations

from html import escape, unescape
import re
import unicodedata


Chapter = tuple[str, list[str]]

_NUM_PREFIX_RE = re.compile(
    r"^(?:#\s*)?(?:제\s*)?(\d+)(?:\s*(?:[화장편권부회]\b|[\:\)]|[.](?!\d))|\s+\S)"
)
_STRUCTURED_CHAPTER_TITLE_RE = re.compile(
    r"^(?:"
    r"(?:제\s*)?\d{1,5}\s*[화장편권부절막회회차](?:\s|$|[.)．:：\-–—])"
    r"|"
    r"\d{1,5}\s*[.)．:：]\s*\S+"
    r"|"
    r"(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d{1,5}\b"
    r")",
    re.IGNORECASE,
)


def normalize_title(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_messy_toc_markers(text: str) -> str:
    """Normalize mixed one-line chapter markers into a consistent ``N화`` style."""
    if not text:
        return text

    lines = text.splitlines()
    if len(lines) < 3:
        return text

    numeric_only_re = re.compile(r"^[<\[\(【『「]?\s*0*(\d{1,4})\s*[>\]\)】』」]?$")
    hwa_like_re = re.compile(r"^(?:제\s*)?0*(\d{1,4})\s*(?:화|회)\s*$")
    protected_re = re.compile(r"^(?:prologue|epilogue|프롤로그|에필로그|외전)\b", re.IGNORECASE)

    candidates: list[tuple[int, int, str]] = []
    for idx, raw_line in enumerate(lines):
        line = normalize_title(raw_line)
        if not line or protected_re.match(line):
            continue
        match = hwa_like_re.match(line)
        if match:
            candidates.append((idx, int(match.group(1)), "hwa"))
            continue
        match = numeric_only_re.match(line)
        if match:
            candidates.append((idx, int(match.group(1)), "num"))

    if len(candidates) < 3:
        return text

    numbers = [num for _idx, num, _kind in candidates]
    asc = sum(1 for i in range(1, len(numbers)) if numbers[i] > numbers[i - 1])
    asc_ratio = asc / max(len(numbers) - 1, 1)
    unique_count = len(set(numbers))
    if asc_ratio < 0.6 or unique_count < 3:
        return text

    replace_map = {idx: f"{num}화" for idx, num, _kind in candidates}
    normalized_lines = [replace_map.get(i, line) for i, line in enumerate(lines)]
    return "\n".join(normalized_lines)


def extract_chapter_number(title: str) -> int | None:
    """Extract a leading chapter number."""
    match = _NUM_PREFIX_RE.match((title or "").strip())
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def filter_ascending_chapters(chapters):
    """Keep the longest ascending number sequence and absorb likely false positives."""
    if len(chapters) < 3:
        return chapters
    special_keep_re = re.compile(r"(?:외전|번외|특전|에필로그|프롤로그|서장|종장)", re.IGNORECASE)
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    keep_special = [bool(special_keep_re.search((title or "").strip())) for title, _lines in chapters]
    valid_idx = [index for index, num in enumerate(nums) if num is not None and not keep_special[index]]
    if len(valid_idx) < 3:
        return chapters

    length = len(valid_idx)
    dp = [1] * length
    parent = [-1] * length
    for i in range(length):
        for j in range(i):
            if nums[valid_idx[j]] < nums[valid_idx[i]] and dp[j] + 1 > dp[i]:
                dp[i] = dp[j] + 1
                parent[i] = j

    end = max(range(length), key=lambda item: dp[item])
    seq_idx: list[int] = []
    cur = end
    while cur >= 0:
        seq_idx.append(valid_idx[cur])
        cur = parent[cur]
    seq_idx.reverse()

    keep = set(seq_idx)
    repaired_titles: dict[int, str] = {}

    def neighbor_nums(pos: int):
        prev = None
        nxt = None
        for before in range(pos - 1, -1, -1):
            if before in keep and nums[before] is not None:
                prev = nums[before]
                break
        for after in range(pos + 1, len(nums)):
            if after in keep and nums[after] is not None:
                nxt = nums[after]
                break
        return prev, nxt

    def embedded_flow_title(title: str, prev_num, next_num) -> str:
        if prev_num is None or next_num is None or next_num <= prev_num:
            return ""
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        best = ""
        for match in re.finditer(r"(?<!\d)(\d{1,5})\s*(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)(?:\b|[.\s]).*$", text):
            try:
                number = int(match.group(1))
            except ValueError:
                continue
            if prev_num < number < next_num:
                best = text[match.start():].strip()
        return best

    def is_flow_noise(title: str, prev_num, next_num) -> bool:
        if prev_num is None or next_num is None:
            return False
        if next_num <= prev_num or next_num - prev_num > 6:
            return False
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        if not text:
            return True
        if re.search(r"^\d{1,3}[.,]\d+\s*%", text):
            return True
        if re.search(r"\d{1,5}\s*(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)\b", text):
            return True
        if len(text) >= 18 and re.search(r"[.!?\u3002,]", text):
            return True
        return False

    for index, num in enumerate(nums):
        if num is None:
            prev_num, next_num = neighbor_nums(index)
            embedded = embedded_flow_title(chapters[index][0], prev_num, next_num)
            if embedded:
                repaired_titles[index] = embedded
                keep.add(index)
            elif not is_flow_noise(chapters[index][0], prev_num, next_num):
                keep.add(index)
    for index, is_special in enumerate(keep_special):
        if is_special:
            keep.add(index)

    if len(keep) == len(chapters) and not repaired_titles:
        return chapters

    out: list[Chapter] = []
    for index, (title, lines) in enumerate(chapters):
        if index in keep:
            out.append((repaired_titles.get(index, title), list(lines)))
        elif out:
            prev_title, prev_lines = out[-1]
            prev_lines.append(f"<b>{escape(title)}</b>")
            prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
        else:
            out.append((title, list(lines)))
    return out


def fill_numeric_gaps(chapters):
    """Split missing numeric chapter headings that were absorbed into previous bodies."""
    if len(chapters) < 2:
        return chapters
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    valid_nums = [num for num in nums if num is not None]
    if len(valid_nums) < 3:
        return chapters
    asc = sum(1 for index in range(1, len(valid_nums)) if valid_nums[index] > valid_nums[index - 1])
    if asc < len(valid_nums) * 0.9 - 1:
        return chapters

    gap_pat = re.compile(r"^(?:#\s*)?(\d+)\s*[\.\:\)](?:\s|$|(?=[A-Za-z가-힣'\u2018\u201C]))")
    embedded_gap_pat = re.compile(
        r"(?<!\d)(\d{1,5})\s*(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)\b.*$"
    )

    def blocked_numbered_list_items(body_lines, wanted: set[int]) -> set[int]:
        candidates: list[tuple[int, int, str]] = []
        for line_index, body_line in enumerate(body_lines):
            plain_line = plain_body_heading(body_line)
            if plain_line.lstrip().startswith("#"):
                continue
            match = gap_pat.match(plain_line)
            if match:
                try:
                    number = int(match.group(1))
                except ValueError:
                    continue
                candidates.append((line_index, number, plain_line))
        blocked: set[int] = set()

        def should_block_run(run: list[tuple[int, int, str]]) -> bool:
            if len(run) < 2:
                return False
            # Consecutive list lines such as "1. item / 2. item / 3. item"
            # are usually body lists. Missing chapter headings normally have
            # body text between candidate lines, so keep those candidates alive.
            adjacent_lines = all(
                run[pos][0] == run[pos - 1][0] + 1
                for pos in range(1, len(run))
            )
            has_outside_wanted = any(number not in wanted for _line_index, number, _plain in run)
            return adjacent_lines or has_outside_wanted

        run: list[tuple[int, int, str]] = []
        for candidate in candidates:
            if run and candidate[1] == run[-1][1] + 1:
                run.append(candidate)
            else:
                if should_block_run(run):
                    blocked.update(number for _line_index, number, _plain in run if number in wanted)
                run = [candidate]
        if should_block_run(run):
            blocked.update(number for _line_index, number, _plain in run if number in wanted)
        return blocked

    def plain_body_heading(body_line: str) -> str:
        plain = unescape(str(body_line or "")).strip()
        plain = re.sub(r"^[<\u3008]\s*(.*?)\s*[>\u3009]$", r"\1", plain).strip()
        plain = re.sub(r"<[^>]+>", "", plain).strip()
        return plain

    out: list[Chapter] = []
    for index, (title, lines) in enumerate(chapters):
        cur_num = nums[index]
        next_num = None
        for next_index in range(index + 1, len(nums)):
            if nums[next_index] is not None:
                next_num = nums[next_index]
                break
        if cur_num is None or next_num is None or next_num - cur_num < 2:
            out.append((title, list(lines)))
            continue
        missing = set(range(cur_num + 1, next_num))
        blocked_list_numbers = blocked_numbered_list_items(lines, missing)
        chunks: list[Chapter] = [(title, [])]
        for line in lines:
            plain = plain_body_heading(line)
            match = gap_pat.match(plain)
            if match and int(match.group(1)) in missing and int(match.group(1)) not in blocked_list_numbers:
                missing.discard(int(match.group(1)))
                chunks.append((plain, []))
            else:
                embedded_match = None
                for candidate in embedded_gap_pat.finditer(plain):
                    try:
                        if int(candidate.group(1)) in missing:
                            embedded_match = candidate
                    except ValueError:
                        continue
                if embedded_match:
                    missing_num = int(embedded_match.group(1))
                    before = plain[: embedded_match.start()].strip()
                    embedded_title = plain[embedded_match.start() :].strip()
                    if before:
                        chunks[-1][1].append(escape(before))
                    missing.discard(missing_num)
                    chunks.append((embedded_title, []))
                else:
                    chunks[-1][1].append(line)
        out.extend(chunks)
    return out


def is_pure_chapter_marker(title: str) -> bool:
    """Return true when a title is only a bare chapter marker."""
    if not title:
        return True
    text = title.strip()
    pure_patterns = [
        r"^제?\s*\d+\s*[화장편권부절막회회차]\s*\.?$",
        r"^(?:Chapter|CHAPTER|chapter|Ch\.?)\s*\d+\s*\.?$",
        r"^(?:Part|PART|Volume|VOLUME)\s+\d+\s*\.?$",
        r"^(?:Prologue|Epilogue|Interlude|프롤로그|에필로그|서장|종장|외전)\s*\.?$",
        r"^[#＃]\s*\d+\s*\.?$",
        r"^\d+\s*[\.\:\)]\s*$",
    ]
    for pattern in pure_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    match = re.search(r"\b\d+\s*[화장편권부]\b", text)
    if match and match.end() >= len(text) - 1:
        if not text[match.end() :].strip(" ."):
            return True
    return False


def merge_short_chapters(chapters, min_chars: int = 0):
    """Merge empty or too-short chapters into adjacent chapters."""
    if not chapters:
        return chapters

    def merge_pending_title(prefix: str, title: str) -> str:
        prefix = (prefix or "").strip()
        title = (title or "").strip()
        if not prefix:
            return title
        if not title:
            return prefix
        prefix_num = extract_chapter_number(prefix)
        title_num = extract_chapter_number(title)
        if prefix_num is not None and prefix_num == title_num:
            prefix_norm = re.sub(r"\s+", " ", normalize_title(prefix)).strip()
            title_norm = re.sub(r"\s+", " ", normalize_title(title)).strip()
            if is_pure_chapter_marker(title) or prefix_norm == title_norm:
                return prefix
            if title_norm.startswith(prefix_norm):
                return title
            if prefix_norm.startswith(title_norm):
                return prefix
        return f"{prefix} {title}".strip()

    cleaned: list[Chapter] = []
    pending_prefix = ""
    for title, lines in chapters:
        body_len = sum(len(line) for line in lines)
        if body_len == 0:
            if is_pure_chapter_marker(title):
                continue
            if title and not is_pure_chapter_marker(title):
                pending_prefix = f"{pending_prefix} {title}".strip() if pending_prefix else title
            continue
        if pending_prefix:
            title = merge_pending_title(pending_prefix, title)
            pending_prefix = ""
        cleaned.append((title, list(lines)))

    if not cleaned:
        return chapters[:1] if chapters else []
    if min_chars <= 0:
        return cleaned

    out: list[Chapter] = []
    for title, lines in cleaned:
        body_len = sum(len(line) for line in lines)
        # 회차 제목이 분명한 챕터는 본문이 짧아도 이전 챕터와 합치지 않는다.
        # "87."처럼 순수 숫자 마커도 전체 흐름에서는 실제 챕터일 수 있다.
        is_structured_title = (
            bool(_STRUCTURED_CHAPTER_TITLE_RE.match((title or "").strip()))
            or extract_chapter_number(title) is not None
        )
        if out and body_len < min_chars and not is_structured_title:
            prev_title, prev_lines = out[-1]
            prev_lines.append(f"<b>{title}</b>")
            prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
        else:
            out.append((title, list(lines)))

    if len(out) >= 2:
        first_title, first_lines = out[0]
        first_structured = (
            bool(_STRUCTURED_CHAPTER_TITLE_RE.match((first_title or "").strip()))
            or extract_chapter_number(first_title) is not None
        )
        if sum(len(line) for line in first_lines) < min_chars and not first_structured:
            next_title, next_lines = out[1]
            new_lines = list(first_lines)
            new_lines.append(f"<b>{next_title}</b>")
            new_lines.extend(next_lines)
            if first_title and not is_pure_chapter_marker(first_title):
                out[1] = (f"{first_title} {next_title}".strip() if next_title else first_title, new_lines)
            else:
                out[1] = (next_title or first_title, new_lines)
            out.pop(0)
    return out


_KR_UNITS_RE = "(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)"


def preserve_unicode_chapter_subtitles(chapters):
    """Convert Unicode chapter markers before legacy mojibake regexes run."""
    normalized = []
    for title, lines in chapters:
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        text = re.sub(r"^\uC2DC\uC791\s+(?=(?:\uC81C\s*)?\d+\s*" + _KR_UNITS_RE + r"\b)", "", text).strip()
        text = re.sub(r"^\uC2DC\uC791\s+(?=(?:#\s*)?\d{1,5}\s*[.)\uFF1A:])", "", text).strip()
        match_lp = re.search(r"(?<!\d)(\d{1,5})\s*\uD654\b\s*$", text)
        if match_lp and re.search(r"\bLP\b", text, re.IGNORECASE):
            normalized.append((f"{int(match_lp.group(1))}\uD654", lines))
            continue
        text = re.sub(
            r"^[<\u3008]\s*#\s*(\d{1,5})\s*([.)\uFF1A:])?\s*(.*?)\s*[>\u3009]\s*$",
            lambda match: f"{int(match.group(1))}. {match.group(3).strip()}".rstrip(),
            text,
        )
        match = re.match(
            r"^(?:\uC81C\s*)?(\d{1,5})\s*" + _KR_UNITS_RE +
            r"\s*(?:[.)\uFF1A:\-]\s*)?(.*)$",
            text,
        )
        if match:
            rest = match.group(2).strip()
            new_title = f"{int(match.group(1))}. {rest}".rstrip() if rest else f"{int(match.group(1))}\uD654"
            normalized.append((new_title, lines))
            continue
        match = re.match(r"^(?:#\s*)?(\d{1,5})\s*[.)\uFF1A:]\s*(.*)$", text)
        if match:
            rest = match.group(2).strip()
            new_title = f"{int(match.group(1))}. {rest}".rstrip() if rest else f"{int(match.group(1))}."
            normalized.append((new_title, lines))
            continue
        normalized.append((title, lines))
    return normalized


def absorb_flow_subheadings(chapters):
    """Absorb short non-number headings inside an established numeric flow."""
    if len(chapters) < 3:
        return chapters
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    out: list[Chapter] = []
    for index, (title, lines) in enumerate(chapters):
        if nums[index] is not None:
            out.append((title, list(lines)))
            continue
        prev_num = next((nums[pos] for pos in range(index - 1, -1, -1) if nums[pos] is not None), None)
        next_num = next((nums[pos] for pos in range(index + 1, len(nums)) if nums[pos] is not None), None)
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        clean_text = re.sub(r"^[\s\-\u2013\u2014\u2022]+", "", text).strip()
        body_len = sum(len(line) for line in lines)
        is_mid_noise = (
            re.match(r"^#\s*\d+[A-Za-z]", text)
            or re.match(r"^\uC5D0\uD544\uB85C\uADF8\s+\uD574\uC11D\b", text)
            or re.match(r"^#\s*\S+", text)
            or re.match(r"^\uC5D0\uD544\uB85C\uADF8\s+(?:\uD574\uC11D|\uB54C\uBB38)", clean_text)
            or clean_text.startswith("\uD2B9\uC804")
        )
        is_mid_special_flow = bool(
            re.match(
                r"^(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|Prologue|Epilogue)\b",
                clean_text,
                re.IGNORECASE,
            )
        )
        should_absorb = (
            prev_num is not None
            and next_num is not None
            and next_num > prev_num
            and next_num - prev_num <= 3
            and len(text) <= 80
            and (
                body_len < 1200
                or is_mid_noise
                or is_mid_special_flow
                or clean_text.startswith("\uD2B9\uC804")
            )
            and (
                is_mid_noise
                or is_mid_special_flow
                or not re.search(
                    r"(?:\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC678\uC804|\uBC88\uC678|\uD2B9\uC804\s*\d)",
                    text,
                )
            )
        )
        if should_absorb and out:
            prev_title, prev_lines = out[-1]
            prev_lines.append(f"<b>{escape(title)}</b>")
            prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
        else:
            out.append((title, list(lines)))
    return out


def restore_unicode_chapter_subtitles(chapters, source_text: str):
    """Restore titles such as '2화. Subtitle' when only the inner '2.' marker was detected."""
    title_map = {}
    for line in str(source_text or "").splitlines():
        text = re.sub(r"\s+", " ", normalize_title(line or "")).strip()
        text = re.sub(r"^\uC2DC\uC791\s+(?=(?:#\s*)?(?:\uC81C\s*)?\d+\s*" + _KR_UNITS_RE + r"\b)", "", text).strip()
        text = re.sub(r"^\uC2DC\uC791\s+(?=(?:#\s*)?\d{1,5}\s*[.)\uFF1A:])", "", text).strip()
        match = re.match(
            r"^(?:\uC81C\s*)?(\d{1,5})\s*" + _KR_UNITS_RE +
            r"\s*(?:[.)\uFF1A:\-]\s*)?(.{1,120})$",
            text,
        )
        if not match:
            continue
        rest = match.group(2).strip()
        if not rest or len(rest) > 120:
            continue
        if rest[:1] in "\uC740\uB294\uC774\uAC00\uC744\uB97C\uC758\uC5D0\uC640\uACFC\uB3C4\uB9CC":
            continue
        if len(rest) >= 18 and re.search(r"(?:\uB2E4|\uC694|\uB2C8|\uB370|\uAE4C|[.!?])['\"\u2018\u2019\u201c\u201d]?\s*$", rest):
            continue
        if re.match(r"^\uCC28\b", rest):
            continue
        title_map.setdefault(int(match.group(1)), f"{int(match.group(1))}. {rest}".rstrip())

    restored = []
    for title, lines in chapters:
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        match = re.match(r"^(?:#\s*)?(\d{1,5})\s*[.)\uFF1A:]?\s*(.*)$", text)
        if match:
            replacement = title_map.get(int(match.group(1)))
            if replacement and replacement != text:
                restored.append((replacement, lines))
                continue
        restored.append((title, lines))
    return restored


def strip_angle_wrapped_chapter_titles(chapters):
    """Remove decorative outer angle brackets from final chapter titles."""
    normalized: list[Chapter] = []
    for title, lines in chapters:
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        text = re.sub(
            r"^((?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*(?:" + _KR_UNITS_RE + r"\b|[.)\uFF1A:])\s*)[<\u3008]\s*(.*?)\s*[>\u3009]\s*$",
            lambda match: (match.group(1) + match.group(2).strip()).strip(),
            text,
        )
        text = re.sub(
            r"^[<\u3008]\s*((?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*(?:" + _KR_UNITS_RE + r"\b|[.)\uFF1A:])\s*.*?)\s*[>\u3009]\s*$",
            lambda match: match.group(1).strip(),
            text,
        )
        normalized.append((text or title, lines))
    return normalized


def absorb_obvious_numeric_flow_noise(chapters):
    """Absorb numeric headings that clearly interrupt an otherwise ascending flow."""
    if len(chapters) < 3:
        return chapters
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    out: list[Chapter] = []
    for index, (title, lines) in enumerate(chapters):
        number = nums[index]
        if number is None or not out:
            out.append((title, list(lines)))
            continue
        prev_num = next((nums[pos] for pos in range(index - 1, -1, -1) if nums[pos] is not None), None)
        next_num = next((nums[pos] for pos in range(index + 1, len(nums)) if nums[pos] is not None), None)
        obvious_interrupt = (
            prev_num is not None
            and next_num is not None
            and next_num > prev_num
            and next_num - prev_num <= 3
            and not (prev_num < number < next_num)
        )
        if obvious_interrupt:
            prev_title, prev_lines = out[-1]
            prev_lines.append(f"<b>{escape(title)}</b>")
            prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
        else:
            out.append((title, list(lines)))
    return out


def absorb_low_number_runs_between_flow(chapters):
    """Absorb already-passed chapter numbers that interrupt a tight ascending flow."""
    if len(chapters) < 4:
        return chapters
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    out: list[Chapter] = []
    index = 0
    while index < len(chapters):
        if not out or nums[index] is None:
            out.append((chapters[index][0], list(chapters[index][1])))
            index += 1
            continue
        prev_num = extract_chapter_number(out[-1][0])
        if prev_num is None:
            out.append((chapters[index][0], list(chapters[index][1])))
            index += 1
            continue
        end = index
        while end < len(chapters) and nums[end] is not None and nums[end] <= prev_num:
            end += 1
        if end > index and end < len(chapters) and nums[end] == prev_num + 1:
            prev_title, prev_lines = out[-1]
            for pos in range(index, end):
                title, lines = chapters[pos]
                prev_lines.append(f"<b>{escape(title)}</b>")
                prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
            index = end
            continue
        out.append((chapters[index][0], list(chapters[index][1])))
        index += 1
    return out


def normalize_chapter_style(chapters):
    """Normalize chapter title style to the dominant numeric format."""
    if not chapters:
        return chapters

    def parse_title(title: str):
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        if not text:
            return None

        match = re.match(
            r"^(외전|번외|특전)\s*(\d{1,5})(?:\s*[화장편회])?\s*"
            r"(?:[.\:：\-–—]\s*)?(.*)$",
            text,
            re.IGNORECASE,
        )
        if match:
            rest = f"{match.group(1)} {match.group(3).strip()}".strip()
            return int(match.group(2)), rest, "unit"

        match = re.match(r"^(?:제\s*)?(\d{1,5})\s*[.)．]\s*(.*)$", text)
        if match:
            num = int(match.group(1))
            rest = match.group(2).strip()
            rest = re.sub(rf"^(?:제\s*)?{num}\s*[화장편회]\s*[.)．:：\-–—]?\s*", "", rest).strip()
            rest = re.sub(r"^(외전|번외|특전)(\d+)\b", r"\1 \2", rest)
            return num, rest, "dot"

        match = re.match(
            r"^(?:제\s*)?(\d{1,5})\s*([화장편회])\s*"
            r"(?:[.)．:：\-–—]\s*)?(.*)$",
            text,
        )
        if match:
            num = int(match.group(1))
            rest = match.group(3).strip()
            rest = re.sub(r"^(외전|번외|특전)(\d+)\b", r"\1 \2", rest)
            return num, rest, "unit"

        return None

    parsed = [parse_title(title) for title, _lines in chapters]
    hwa_like = sum(1 for item in parsed if item and item[2] == "unit")
    dot_like = sum(1 for item in parsed if item and item[2] == "dot")
    if hwa_like == 0 and dot_like == 0:
        return chapters
    dominant = "hwa" if hwa_like >= dot_like else "dot"

    normalized = list(chapters)
    for index, item in enumerate(parsed):
        if not item:
            continue
        num, rest, _style = item
        _old_title, lines = normalized[index]
        rest = re.sub(r"\s+", " ", rest).strip()
        if not rest and _style == "unit":
            continue
        if dominant == "hwa":
            new_title = f"{num}화 {rest}".rstrip() if rest else f"{num}화"
        else:
            new_title = f"{num}. {rest}".rstrip() if rest else f"{num}."
        normalized[index] = (new_title, lines)
    return normalized


def strip_chapter_subtitles(chapters):
    """Keep only the chapter marker when subtitle titles are disabled."""
    parsed = []
    unit_count = 0
    dot_count = 0
    for title, _lines in chapters:
        text = re.sub(r"\s+", " ", normalize_title(title or "")).strip()
        text = re.sub(r"^\uC2DC\uC791\s+", "", text)
        match = re.match(
            r"^(?:#\s*)?(?:\uC81C\s*)?0*(\d{1,5})\s*"
            r"([\uD654\uC7A5\uD3B8\uAD8C\uBD80\uD68C])(?:\b|[.)\s:\uFF1A-]|$)",
            text,
        )
        if match:
            parsed.append((int(match.group(1)), match.group(2), "unit"))
            unit_count += 1
            continue
        match = re.match(r"^(?:#\s*)?0*(\d{1,5})\s*([.)\uFF1A:])", text)
        if match:
            parsed.append((int(match.group(1)), ".", "dot"))
            dot_count += 1
            continue
        match = re.match(r"^#\s*0*(\d{1,5})\b", text)
        if match:
            parsed.append((int(match.group(1)), "#", "hash"))
            continue
        parsed.append(None)
    dominant = "unit" if unit_count > dot_count else "dot"
    stripped: list[Chapter] = []
    for (title, lines), item in zip(chapters, parsed):
        if item:
            num, unit, style = item
            if style == "hash" and unit_count == 0 and dot_count == 0:
                stripped.append((f"#{num}", lines))
            elif dominant == "unit":
                marker_unit = unit if style == "unit" else "\uD654"
                stripped.append((f"{num}{marker_unit}", lines))
            else:
                stripped.append((f"{num}.", lines))
            continue
        stripped.append((title, lines))
    return stripped


def analyze_chapter_suspects(chapters):
    """Return rows that deserve a visual review in the TXT chapter preview."""
    nums = [extract_chapter_number(title) for title, _lines in chapters]
    results: list[dict] = []

    def title_text(index: int) -> str:
        if not (0 <= index < len(chapters)):
            return ""
        return re.sub(r"\s+", " ", normalize_title(chapters[index][0] or "")).strip()

    def body_len(index: int) -> int:
        if not (0 <= index < len(chapters)):
            return 0
        return sum(len(line) for line in chapters[index][1])

    def prev_numeric(pos: int):
        for before in range(pos - 1, -1, -1):
            if nums[before] is not None:
                return before, nums[before]
        return None, None

    def next_numeric(pos: int):
        for after in range(pos + 1, len(nums)):
            if nums[after] is not None:
                return after, nums[after]
        return None, None

    for index, number in enumerate(nums):
        text = title_text(index)
        prev_index, prev_num = prev_numeric(index)
        next_index, next_num = next_numeric(index)
        clean_text = re.sub(r"^[\s\-\u2013\u2014\u2022]+", "", text).strip()
        inline_list_tail = re.sub(r"^(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*(?:[\uD654\uC7A5\uD3B8\uAD8C\uBD80\uD68C]|[.)\uFF1A:])\s*", "", clean_text)
        has_inline_numbered_list = bool(
            re.search(r"(?:^|[.!?\u3002]\s+)\d{1,3}\s*[.]\s+\S", inline_list_tail)
        )

        if number is None:
            if prev_num is None or next_num is None:
                continue
            tag_like = (
                text.startswith("#")
                or clean_text.startswith("\uD2B9\uC804")
                or re.match(r"^\uC5D0\uD544\uB85C\uADF8\s+(?:\uD574\uC11D|\uB54C\uBB38)", clean_text)
            )
            if tag_like or next_num - prev_num <= 3:
                results.append(
                    {
                        "row": index,
                        "kind": "flow",
                        "auto_merge": True,
                        "reason": "numeric flow interruption",
                    }
                )
            continue

        if prev_num is not None:
            if (
                has_inline_numbered_list
                and next_num is not None
                and prev_num < number < next_num
                and next_num - prev_num <= 3
            ):
                results.append(
                    {
                        "row": index,
                        "kind": "inline-list",
                        "auto_merge": True,
                        "reason": "inline numbered list inside chapter flow",
                    }
                )
                continue
            if number <= prev_num:
                results.append(
                    {
                        "row": index,
                        "kind": "order",
                        "auto_merge": True,
                        "reason": "duplicate or backward number",
                    }
                )
                continue
            if number > prev_num + 1:
                results.append(
                    {
                        "row": index,
                        "kind": "gap",
                        "auto_merge": False,
                        "reason": "missing number before this row",
                    }
                )

        if (
            prev_num is not None
            and next_num is not None
            and prev_num < number < next_num
            and next_num - prev_num <= 2
            and body_len(index) < 250
            and re.fullmatch(r"(?:#\s*)?\d{1,5}\s*(?:[.)\uFF1A:]|\uD654)?\s*", text)
            and not re.fullmatch(r"(?:#\s*)?\d{1,5}\s*\uD654\s*[.]?\s*", text)
        ):
            results.append(
                {
                    "row": index,
                    "kind": "short",
                    "auto_merge": False,
                    "reason": "very short bare chapter",
                }
            )

    # keep one entry per row, preferring auto-merge warnings
    by_row: dict[int, dict] = {}
    for item in results:
        previous = by_row.get(item["row"])
        if previous is None or item.get("auto_merge") and not previous.get("auto_merge"):
            by_row[item["row"]] = item
    return [by_row[row] for row in sorted(by_row)]


def merge_auto_suspect_chapters(chapters):
    """Merge only high-confidence suspect rows into the previous chapter."""
    auto_rows = {
        item["row"]
        for item in analyze_chapter_suspects(chapters)
        if item.get("auto_merge")
    }
    if not auto_rows:
        return chapters
    out: list[Chapter] = []
    for index, (title, lines) in enumerate(chapters):
        if index in auto_rows and out:
            prev_title, prev_lines = out[-1]
            prev_lines.append(f"<b>{escape(title)}</b>")
            prev_lines.extend(lines)
            out[-1] = (prev_title, prev_lines)
        else:
            out.append((title, list(lines)))
    return out
