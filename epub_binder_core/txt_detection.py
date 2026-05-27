from __future__ import annotations

from html import escape
import re

from .txt_chapters import normalize_title


Chapter = tuple[str, list[str]]

# Strength-specific chapter patterns. Earlier entries have higher priority.
CHAPTER_PATTERN_SETS = {
    "weak": [
        ("KOR_특수확장", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b"),
        ("KOR_꺾쇠N화", r"^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$"),
        ("KOR_꺾쇠N부", r"^[<＜]\s*\d{1,5}\s*부\s*[>＞〉]\s*\S+.*$"),
        ("KOR_제N화", r"^제\s?\d+\s?[화장편권부회]"),
        ("KOR_N화", r"^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)"),
        ("KOR_외전N화", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)"),
        ("KOR_외전N점", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]"),
        ("KOR_장외전", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b"),
        ("NUM_HASH_DOT", r"^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+"),
        ("NUM_샵", r"^[#＃]\s?\d+"),
    ],
    "normal": [
        ("KOR_특수확장", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b"),
        ("KOR_꺾쇠N화", r"^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$"),
        ("KOR_꺾쇠N부", r"^[<＜]\s*\d{1,5}\s*부\s*[>＞〉]\s*\S+.*$"),
        ("KOR_제N화", r"^제\s?\d+\s?[화장편권부회]"),
        ("KOR_N화", r"^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)"),
        ("KOR_외전N화", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)"),
        ("KOR_외전N점", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]"),
        ("KOR_장외전", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b"),
        ("KOR_외전N", r"^(?:외전|번외|특전)\s*\d+\b"),
        ("KOR_N외전", r"^\d+\s*(?:외전|번외|특전)\b"),
        ("KOR_끝N화", r"^.{2,80}?\s+\d+\s?[화장편](?:\s*[\(（][^\)）]{0,60}[\)（])?\s*$"),
        ("KOR_끝N점", r"^.{2,120}?\s+\d+\s*\.\s*\S.+$"),
        ("KOR_꺾쇠N점", r"^.{0,120}?[<＜]\s*#?\s*\d+\s*[.,，:：]\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$"),
        ("KOR_N회차", r"^\d+\s?회차\b"),
        ("KOR_특수", r"^(?:서장|종장|프롤로그|에필로그|외전)\b"),
        ("ENG_Chapter", r"^(?:Chapter|CHAPTER|chapter)\s+\d+"),
        ("ENG_Ch", r"^Ch\.?\s*\d+\b"),
        ("ENG_Part", r"^(?:Part|PART|Volume|VOLUME)\s+\d+"),
        ("ENG_특수", r"^(?:Prologue|Epilogue|Interlude)\b"),
        ("NUM_점", r"^\d+\s*(?:[\:\)](?:\s|$)|[.](?:\s|$|(?!\d)\S))"),
        ("NUM_HASH_DOT", r"^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+"),
        ("NUM_샵", r"^[#＃]\s?\d+"),
    ],
    "strong": [
        ("KOR_특수확장", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:(?:제\s*)?\d+\s*[화장권부]\s*)?(?:특별\s*)?(?:외전|번외|특전|에필로그|프롤로그|서장|종장)\b"),
        ("KOR_꺾쇠N화", r"^.{0,120}?[<＜]\s*\d+\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$"),
        ("KOR_꺾쇠N부", r"^[<＜]\s*\d{1,5}\s*부\s*[>＞〉]\s*\S+.*$"),
        ("KOR_제N화", r"^제\s?\d+\s?[화장편권부회]"),
        ("KOR_N화", r"^\d+\s?[화장편권부회](?=\s|[.\:：\)）]|$)"),
        ("KOR_외전N화", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*화(?=\s|[.,，!！?？\:：\)）\-–—]|$)"),
        ("KOR_외전N점", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:[가-힣A-Za-z]{1,3}\s+)?(?:외전|번외|특전)\s*\d+\s*[.\．]"),
        ("KOR_장외전", r"^[\s\-\–\—\·\•\[\(＜<]*?(?:제\s*)?\d+\s*장\s*(?:외전|번외|특전)(?:\s*\d+\s*화)?\b"),
        ("KOR_외전N", r"^(?:외전|번외|특전)\s*\d+\b"),
        ("KOR_N외전", r"^\d+\s*(?:외전|번외|특전)\b"),
        ("KOR_끝N화", r"^.{2,80}?\s+\d+\s?[화장편](?:\s*[\(（][^\)）]{0,60}[\)）])?\s*$"),
        ("KOR_끝N점", r"^.{2,120}?\s+\d+\s*\.\s*\S.+$"),
        ("KOR_꺾쇠N점", r"^.{0,120}?[<＜]\s*#?\s*\d+\s*[.,，:：]\s*[^<>＜＞〈〉]+?\s*[>＞〉]\s*$"),
        ("KOR_N회차", r"^\d+\s?회차\b"),
        ("KOR_특수", r"^(?:서장|종장|프롤로그|에필로그|외전)\b"),
        ("ENG_Chapter", r"^(?:Chapter|CHAPTER|chapter)\s+\d+"),
        ("ENG_Ch", r"^Ch\.?\s*\d+\b"),
        ("ENG_Part", r"^(?:Part|PART|Volume|VOLUME)\s+\d+"),
        ("ENG_특수", r"^(?:Prologue|Epilogue|Interlude)\b"),
        ("NUM_분할", r"^\d+\s?-\s?\d+\b"),
        ("NUM_소수", r"^\d+\.\d+\b"),
        ("NUM_점", r"^\d+\s*(?:[\:\)](?:\s|$)|[.](?:\s|$|(?!\d)\S))"),
        ("NUM_HASH_DOT", r"^\s*[#＃]\s*\d{1,5}\s*[.)．:：]\s*\S+"),
        ("NUM_샵", r"^[#＃]\s?\d+"),
        ("MD_헤더", r"^#{1,3}\s+\S"),
    ],
}


def compile_patterns(strength: str, custom_regex: str = ""):
    """Return compiled ``(name, regex)`` pairs. Priority: custom > built-in."""
    sets = CHAPTER_PATTERN_SETS.get(strength, CHAPTER_PATTERN_SETS["normal"])
    compiled = []
    if custom_regex:
        try:
            compiled.append(("CUSTOM", re.compile(custom_regex)))
        except re.error:
            pass
    for name, pattern in sets:
        try:
            compiled.append((name, re.compile(pattern)))
        except re.error:
            continue
    return compiled


_CHAP_MARKER_RE = re.compile(
    r"(?:제\s?\d+\s?[화장편권부회]"
    r"|(?:외전|번외|특전)\s*\d+(?=\s*[.：:])"
    r"|(?:외전|번외|특전)\s*\d+\s*화"
    r"|\d+\s?[화장편권부회]"
    r"|\d+\s?회차"
    r"|(?:Chapter|CHAPTER|chapter)\s+\d+"
    r"|Ch\.?\s*\d+"
    r"|(?:Part|PART|Volume|VOLUME)\s+\d+"
    r"|(?:Prologue|Epilogue|Interlude)"
    r"|(?:서장|종장|프롤로그|에필로그|외전))",
    re.IGNORECASE,
)


def _is_angle_part_title(title: str) -> bool:
    return bool(re.match(r"^[<\uFF1C]\s*\d{1,5}\s*부\s*[>\uFF1E\u3009]\s*\S", title or ""))


def strip_book_prefix(title: str) -> str:
    """Remove a book-title prefix from a matched chapter header."""
    direct_part_angle = re.match(
        r"^[<\uFF1C]\s*(\d{1,5}\s*부)\s*[>\uFF1E\u3009]\s*(\S.*)$",
        title,
    )
    if direct_part_angle:
        return f"{direct_part_angle.group(1)} {direct_part_angle.group(2)}".strip()

    direct_angle = re.match(
        r"^[<\uFF1C]\s*((?:#\s*)?\d{1,5}\s*[.,\uFF0C:：]\s*.*?)\s*[>\uFF1E\u3009]\s*$",
        title,
    )
    if direct_angle:
        return direct_angle.group(1).strip()

    direct_colon = re.match(r"^\s*(\d{1,5}\s*[:：]\s*.+)$", title)
    if direct_colon:
        return direct_colon.group(1).strip()

    match_angle = re.search(
        r"[<＜]\s*((?:\d{1,4}\s*화\s*[.\:：]?\s*[^<>＜＞〈〉]+)|(?:\d{1,4}\s*[.,，]\s*[^<>＜＞〈〉]+?))\s*[>＞〉]",
        title,
    )
    if match_angle:
        return match_angle.group(1).strip()

    match_tail = re.search(r"(^|[\s\]\)])(\d{1,4}\s*\.\s*.+)$", title)
    if match_tail:
        tail = match_tail.group(2).strip()
        if not re.match(r"^\d{1,4}\s*\.\s*\d", tail):
            return tail

    masked = re.sub(r"[\(（][^\)）]*[\)）]", lambda match: "." * len(match.group(0)), title)
    matches = list(_CHAP_MARKER_RE.finditer(masked))
    if not matches:
        return title
    if matches[0].start() == 0:
        return title

    numbered = []
    for match in matches:
        try:
            segment = masked[match.start() : match.end()]
        except Exception:
            segment = ""
        if re.search(r"\d", segment):
            numbered.append(match)
    match = numbered[-1] if numbered else matches[-1]
    return title[match.start() :].strip() or title


def prettify_marker(title: str) -> str:
    """Format markers for display, e.g. ``N화(주석)`` -> ``N화 (주석)``."""
    return re.sub(r"(\d+\s?[화장편권부])([\(（])", r"\1 \2", title)


_KR_UNITS_RE = "(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)"


def clean_chapter_marker_title(title: str) -> str:
    """Normalize noisy TXT chapter labels while preserving useful numbering."""
    text = normalize_title(title or "")
    text = re.sub(r"^[\[\(【『「]\s*(.*?)\s*[\]\)】』」]$", r"\1", text).strip()
    text = re.sub(
        r"^((?:에필로그|프롤로그|외전|번외|특전|서장|종장)\b.*?)[\]\)】』」]\s*$",
        r"\1",
        text,
    ).strip()
    text = re.sub(r"^(?:\u2502|\||\u2503|\u2506|\u250A)\s*", "", text).strip()
    text = re.sub(r"^#\s*(?=(?:\uC81C\s*)?\d+\s*" + _KR_UNITS_RE + r"\b)", "", text).strip()
    text = re.sub(
        r"^\uC2DC\uC791\s+(?=(?:#\s*)?(?:\uC81C\s*)?\d+\s*" + _KR_UNITS_RE + r"\b)",
        "",
        text,
    ).strip()
    text = re.sub(
        r"^\uC2DC\uC791\s+(?=(?:#\s*)?\d{1,5}\s*[.)\uFF1A:])",
        "",
        text,
    ).strip()
    text = re.sub(r"^(?:#\s*)?(\d{1,5})\s*\uD654\s*$", lambda m: m.group(1) + "\uD654", text)
    angle = re.match(r"^((?:\d{1,5}\s*[.)]\s*)?)[<\u3008]\s*(.*?)\s*[>\u3009]\s*$", text)
    if angle:
        prefix = angle.group(1).strip()
        inner = re.sub(r"^#\s*(?=\d)", "", angle.group(2).strip())
        return f"{prefix} {inner}".strip() if prefix else inner
    return re.sub(r"^[<\u3008]\s*(.*?)\s*[>\u3009]\s*$", r"\1", text).strip()


def detect_chapters(
    text: str,
    strength: str = "normal",
    custom_regex: str = "",
    enforce_consistency: bool = True,
    force_subtitle_style: bool | None = None,
):
    """Split plain text into ``[(title, escaped_body_lines), ...]`` chapters."""
    patterns = compile_patterns(strength, custom_regex)
    raw_lines = text.splitlines()
    if not patterns:
        return [("본문", [escape(line.strip()) for line in raw_lines if line.strip()])], False

    first_nonempty = next((line.strip() for line in raw_lines if line.strip()), "")
    drop_intro = bool(re.match(r"^[^@\n]{1,80}?@[^\s@][^\n]{0,60}$", first_nonempty))

    zero_width_re = re.compile(r"[\u200B-\u200F\u2060\uFEFF]")
    lines = [line.strip() for line in raw_lines if line.strip()]
    normalized_lines = [
        re.sub(r"\s+", " ", zero_width_re.sub("", line).replace("\u00A0", " ")).strip()
        for line in lines
    ]

    def numdot_ascending_fallback(scan_lines):
        heads = []
        pattern = re.compile(r"^\s*(\d{1,5})\s*(?:[.\)．。]\s*|\s+)(\S.+)$")
        for index, line in enumerate(scan_lines):
            match = pattern.match(line)
            if not match:
                continue
            try:
                number = int(match.group(1))
            except Exception:
                continue
            title_tail = normalize_title(match.group(2) or "")
            if not title_tail or len(title_tail) > 90:
                continue
            if re.match(r"^(?:\uCC28\s|\uC0DD\s|\uC774|\uC740|\uB294|\uC744|\uB97C|\uC5D0|\uC758|\uAC00|\uC774)\b", title_tail):
                continue
            if len(title_tail) >= 35 and re.search(r"(?:\uB2E4|\uC694|\uB2C8|\uB370|\uAE4C|[.!?])\s*$", title_tail):
                continue
            heads.append((index, number, line))
        if len(heads) < 5:
            return None
        asc = sum(1 for index in range(1, len(heads)) if heads[index][1] > heads[index - 1][1])
        asc_ratio = asc / max(len(heads) - 1, 1)
        unique = len({number for _index, number, _line in heads})
        if asc_ratio < 0.8 or unique < 5:
            return None

        out = []
        for chapter_index, (line_index, _number, title_line) in enumerate(heads):
            start = line_index + 1
            end = heads[chapter_index + 1][0] if chapter_index + 1 < len(heads) else len(scan_lines)
            body = [escape(line) for line in scan_lines[start:end] if line.strip()]
            out.append((title_line.strip(), body))
        return out if len(out) >= 3 else None

    def looks_like_prose_not_heading(value: str) -> bool:
        if not value:
            return False
        title = normalize_title(value)
        if len(title) >= 40 and re.search(r"[,.!?…“”\"'‘’]", title):
            return True
        if len(title.split()) >= 8:
            return True
        return False

    def looks_like_inline_hwa_prose(value: str) -> bool:
        title = normalize_title(value or "").strip()
        match = re.match(r"^(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*[\uD654\uC7A5\uD68C]\s+(.+)$", title)
        if not match:
            return False
        if re.match(r"^(?:#\s*)?(?:\uC81C\s*)?\d{1,5}\s*[\uD654\uC7A5\uD68C]\s*[.)\uFF1A:\-]", title):
            return False
        rest = match.group(1).strip()
        if len(rest) >= 18 and re.search(r"(?:\uB2E4|\uC694|\uB2C8|\uB370|\uAE4C|[.!?])\s*$", rest):
            return True
        if len(rest.split()) >= 5:
            return True
        return False

    def looks_like_split_or_decimal_body_number(value: str, pattern_name: str | None) -> bool:
        title = normalize_title(value or "").strip()
        if pattern_name == "NUM_소수":
            return bool(re.match(r"^\d+\.\d+\s*%", title) or re.match(r"^\d+\.\d+%", title))
        if pattern_name != "NUM_분할":
            return False
        if re.match(r"^\d{4}\s*-\s*\d{4}\s+시즌\b", title, re.IGNORECASE):
            return True
        if re.match(r"^\d+(?:\s*-\s*\d+){2,}\s*[가-힣]", title):
            return True
        if re.match(r"^\d+\s*-\s*\d+\)\s+\S+", title):
            return True
        if re.match(r"^\d+\s*-\s*\d+\s*[은는이가을를의에와과도만]\b", title):
            return True
        return False

    total_stripped = 0
    plausible_count = 0
    for index, line in enumerate(lines):
        normalized_line = normalized_lines[index] if index < len(normalized_lines) else line
        if not any(regex.match(normalized_line) for _name, regex in patterns):
            continue
        if _is_angle_part_title(line):
            continue
        if strip_book_prefix(line) == line:
            continue
        total_stripped += 1
        if index + 1 < len(lines):
            next_line = lines[index + 1]
            next_normalized = normalized_lines[index + 1] if index + 1 < len(normalized_lines) else next_line
            if (
                1 <= len(next_line) <= 30
                and not any(regex.match(next_normalized) for _name, regex in patterns)
            ):
                plausible_count += 1
    subtitle_style = (
        force_subtitle_style
        if force_subtitle_style is not None
        else (total_stripped >= 3 and plausible_count / total_stripped >= 0.5)
    )

    temp = []
    found = []
    current_title, current_lines = "시작", []
    skip = 0
    for index, line in enumerate(lines):
        if skip > 0:
            skip -= 1
            continue
        normalized_line = normalized_lines[index] if index < len(normalized_lines) else line
        matched = None
        for name, regex in patterns:
            if regex.match(normalized_line):
                matched = name
                break
        if matched and re.search(r"\b\d+\.\d+\s*%", normalized_line):
            matched = None
        if matched == "KOR_끝N점" and strip_book_prefix(line) == line:
            matched = None
        # Split-number, decimal-like, and number-dot patterns are noisy in prose;
        # reject sentence-shaped lines such as "0805. 숫자 네 개를 ... 지나갔다."
        if matched in {"NUM_분할", "NUM_소수", "NUM_점"} and looks_like_prose_not_heading(normalized_line):
            matched = None
        if matched in {"NUM_분할", "NUM_소수"} and looks_like_split_or_decimal_body_number(normalized_line, matched):
            matched = None
        if matched == "NUM_점" and re.match(r"^0\d{3,}\s*[.．]\s*\S+", normalized_line):
            matched = None
        if matched and looks_like_inline_hwa_prose(normalized_line):
            matched = None
        if matched:
            marker_title = strip_book_prefix(line)
            if re.match(r"^\d{1,5}\.\d", normalize_title(marker_title or "").strip()):
                current_lines.append(escape(line))
                continue
            stripped_book_prefix = marker_title != line and not _is_angle_part_title(line)
            if stripped_book_prefix and subtitle_style and index + 1 < len(lines):
                next_line = lines[index + 1]
                next_normalized = normalized_lines[index + 1] if index + 1 < len(normalized_lines) else next_line
                is_next_chapter = any(regex.match(next_normalized) for _name, regex in patterns)
                can_absorb = (
                    not is_next_chapter
                    and 1 <= len(next_line) <= 30
                    and not next_line.startswith(("(", "[", '"', "“", "「"))
                )
                if can_absorb:
                    marker_title = f"{marker_title} {next_line}".strip()
                    skip = 1
            elif index + 1 < len(lines) and re.fullmatch(
                r"(?:\uC81C\s*)?\d{1,5}\s*" + _KR_UNITS_RE + r"\s*[.)\uFF1A:]?",
                normalize_title(marker_title),
            ):
                next_line = lines[index + 1]
                next_normalized = normalized_lines[index + 1] if index + 1 < len(normalized_lines) else next_line
                is_next_chapter = any(regex.match(next_normalized) for _name, regex in patterns)
                can_absorb = (
                    not is_next_chapter
                    and 2 <= len(next_line) <= 60
                    and not next_line.startswith(("(", "[", '"', "\u201c", "\u300c"))
                    and not re.search(r"(?:\uB2E4|\uC694|\uC8E0|\uAE4C|\uB2C8|\uB370)[.!?\u3002]?\s*$", next_line)
                    and not (len(next_line) >= 14 and len(next_line.split()) >= 3)
                    and not re.search(r"(?:\uB2E4|\uC694|\uC8E0|\uAE4C|\uB2C8|\uB370)[.!?\u3002]?\s*$", next_line)
                    and re.search(r"(?:[-\u2013\u2014]\s*\d+|[\(\uFF08]\d+[\)\uFF09]|\+\d+)\s*$", next_line)
                )
                if can_absorb:
                    marker_title = f"{marker_title} {next_line}".strip()
                    skip = 1
            marker_title = clean_chapter_marker_title(prettify_marker(marker_title))
            if current_lines or current_title != "시작":
                temp.append(
                    {
                        "title": current_title,
                        "lines": current_lines,
                        "pattern": found[-1] if found else "START",
                    }
                )
            current_title, current_lines = marker_title, []
            found.append(matched)
        else:
            current_lines.append(escape(line))
    if current_lines or current_title != "시작":
        temp.append(
            {
                "title": current_title,
                "lines": current_lines,
                "pattern": found[-1] if found else "START",
            }
        )

    if not temp:
        return [("본문", [])], subtitle_style

    if drop_intro and temp and temp[0]["title"] == "시작":
        temp = temp[1:]
        if not temp:
            return [("본문", [])], subtitle_style

    if len(temp) > 1 and temp[0]["title"] == "시작":
        intro_len = sum(len(re.sub(r"<[^>]+>", "", line).strip()) for line in temp[0]["lines"])
        if len(temp[0]["lines"]) <= 1 and intro_len <= 120:
            temp[1]["lines"] = list(temp[0]["lines"]) + list(temp[1]["lines"])
            temp = temp[1:]

    def leading_num(value: str) -> int | None:
        match = re.match(r"^(?:#\s*)?(?:\uC81C\s*)?0*(\d{1,5})\s*(?:[\uD654\uC7A5\uD3B8\uAD8C\uBD80\uD68C]\b|[.)\uFF1A:])", normalize_title(value or "").strip())
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    if len(temp) >= 4:
        cleaned = []
        index = 0
        while index < len(temp):
            item = temp[index]
            if not cleaned:
                cleaned.append(item)
                index += 1
                continue
            if not str(item.get("pattern", "")).startswith("NUM_"):
                cleaned.append(item)
                index += 1
                continue
            run = []
            end = index
            prev = None
            while end < len(temp) and str(temp[end].get("pattern", "")).startswith("NUM_"):
                num = leading_num(temp[end]["title"])
                if num is None or (prev is not None and num != prev + 1):
                    break
                run.append(temp[end])
                prev = num
                end += 1
            prev_title_num = leading_num(cleaned[-1]["title"])
            run_first_num = leading_num(run[0]["title"]) if run else None
            run_last_num = leading_num(run[-1]["title"]) if run else None
            next_num = leading_num(temp[end]["title"]) if end < len(temp) else None
            if (
                len(run) >= 2
                and next_num is not None
                and prev_title_num is not None
                and run_first_num is not None
                and run_last_num is not None
                and run_first_num == 1
                and next_num <= run_last_num
            ):
                for run_item in run:
                    cleaned[-1]["lines"].append(f"<b>{escape(run_item['title'])}</b>")
                    cleaned[-1]["lines"].extend(run_item["lines"])
                index = end
                continue
            cleaned.append(item)
            index += 1
        temp = cleaned

    if len(found) <= 2:
        fallback = numdot_ascending_fallback(lines)
        if fallback:
            return fallback, subtitle_style

    if enforce_consistency and len(found) > 1:
        from collections import Counter

        primary = Counter(found).most_common(1)[0][0]
        exempt_patterns = {
            "KOR_특수",
            "KOR_특수확장",
            "ENG_특수",
            "KOR_장외전",
            "KOR_외전N",
            "KOR_N외전",
            "KOR_외전N화",
            "KOR_꺾쇠N점",
            "NUM_점",
        }
        merged = []
        current_title = temp[0]["title"]
        current_lines = list(temp[0]["lines"])
        for index in range(1, len(temp)):
            if temp[index]["pattern"] == primary or temp[index]["pattern"] in exempt_patterns:
                merged.append((current_title, current_lines))
                current_title = temp[index]["title"]
                current_lines = list(temp[index]["lines"])
            else:
                current_lines.append(f"<b>{temp[index]['title']}</b>")
                current_lines.extend(temp[index]["lines"])
        merged.append((current_title, current_lines))
        return merged, subtitle_style
    return [(chapter["title"], chapter["lines"]) for chapter in temp], subtitle_style


__all__ = [
    "CHAPTER_PATTERN_SETS",
    "compile_patterns",
    "clean_chapter_marker_title",
    "detect_chapters",
    "prettify_marker",
    "strip_book_prefix",
]
