from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import unicodedata

from .name_cleanup import humanize_series_title


_EXT_RE = re.compile(r"\.(epub|zip|7z|txt)$", re.IGNORECASE)
_SPACES_RE = re.compile(r"\s+")
_AUTHOR_RE = re.compile(r"^\[(?P<author>[^\]]+)\]\s*(?P<body>.+)$")
_VOLUME_PART_RE = re.compile(
    r"^(?P<series>.+?)\s*(?P<volume>\d+)\s*권\s*[-–—_ ]+\s*(?P<part>\d+)\s*$"
)
_VOLUME_RE = re.compile(r"^(?P<series>.+?)\s*(?P<volume>\d+)\s*권\s*$")
_VOLUME_TRAILING_MARKER_RE = re.compile(
    r"^(?P<series>.+?)\s*(?P<volume>\d+)\s*권\s*"
    r"(?P<trailing>(?:[\(\[（【]\s*)?"
    r"(?:\d+\s*부|외전|번외|특전|특별\s*외전|완결|완|完)"
    r"(?:\s*[\)\]）】])?)\s*$",
    re.IGNORECASE,
)
# "시리즈 N-M" 형식 - 권 없이 볼륨-파트 구분 (예: 비포 더 던 1-1)
_VOLUME_PART_DASH_RE = re.compile(
    r"^(?P<series>.+?)\s+(?P<volume>\d{1,3})\s*[-–—]\s*(?P<part>\d{1,3})\s*$"
)
# "시리즈 N : 부제목" 형식 (예: 치우천왕기 1 : 형제)
_VOLUME_SUBTITLE_RE = re.compile(
    r"^(?P<series>.+?)\s+(?P<volume>\d{1,3})\s*[：:]\s*(?P<subtitle>.+)$"
)
# "시리즈N본문/본편" 붙여쓰기 형식 (예: 헤븐스톤1본문)
_CONCAT_VOLUME_SUFFIX_RE = re.compile(
    r"^(?P<series>[가-힣A-Za-z]{2,}?)(?P<volume>\d{1,3})(?:본문|본편)$"
)
# "시리즈 N" 형식 — 권 suffix 없이 숫자만 끝에 오는 경우 (예: 반 리로디드 1, 상계무적 7)
# 다른 패턴 모두 실패한 뒤 마지막 폴백으로 사용
_PLAIN_VOLUME_RE = re.compile(r"^(?P<series>.+?)\s+(?P<volume>\d{1,3})\s*$")
_EPISODE_RE = re.compile(r"(?P<episode>\d+)\s*(?:화|장|회)\b")
_EPISODE_RANGE_RE = re.compile(
    r"^(?P<series>.+?)\s+(?P<start>\d{1,5})\s*[-~]\s*(?P<end>\d{1,5})\s*(?:\uD654|\uD68C|\uC7A5)?\s*(?P<done>\((?:\uC644|\uC644\uACB0)\))?\s*$"
)
_TRAILING_MULTI_NUMBER_RE = re.compile(r"\s+\d+(?:\s*[-_.]\s*\d+)+(?:\s*[.。．])?\s*$")
_TRAILING_SINGLE_NUMBER_RE = re.compile(r"\s+\d+\s*$")
_SIDE_STORY_RE = re.compile(
    r"\s*\(?(?:외전|번외|특전|특별편|후일담)(?:\s*\d+)?\)?\s*$",
    re.IGNORECASE,
)
_TRAILING_PAREN_NUM_RE = re.compile(r"(?:\s*\(\d{1,3}\))+\s*$")
_EDITION_TOKEN_RE = re.compile(r"(?:개정판|신장판|증보판|개정증보판|완전판|외전증보판)")
# 챕터 번호 형식 heading 감지: "7. 제목", "第N章", "第N節", 한국어 장/화/회/절/편/막 등
_CHAPTER_HEADING_RE = re.compile(
    r"(?:^\d+(?:\.\d+)*\s*[.。．]\s*\S|第\s*\d+\s*[章節篇]|^\d+\s*[장화회절편막](?:\s|$)|^제\s*\d+\s*[장화회절편막](?:\s|$))",
    re.IGNORECASE,
)
# 완결 표시 감지: "완결", "完", "(완)", "[완]" 등
_COMPLETED_DETECT_RE = re.compile(r"완결|完|\(\s*완\s*\)|\[\s*완\s*\]", re.IGNORECASE)
_GENERIC_BOOK_HEADING_RE = re.compile(
    r"^(?:책의\s*시작|책의\s*끝|목차|차례|저자\s*소개|작가의\s*말|판권"
    r"|copyright|contents?|table\s*of\s*contents|start|begin(?:ning)?|end)$",
    re.IGNORECASE,
)


_UNICODE_CHAPTER_HEADING_RE = re.compile(
    r"^\s*(?:\uC2DC\uC791\s+)?(?:\uC81C\s*)?\d{1,5}\s*(?:\uD654|\uC7A5|\uD3B8|\uAD8C|\uBD80|\uD68C)\b"
    r"|^\s*#?\s*\d{1,5}\s*[.)]\s*\S+"
    r"|^\s*(?:Prologue|Epilogue|Interlude|Chapter|CHAPTER|chapter|Ch\.?)\s*\d*\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedName:
    author: str = ""
    series: str = ""
    volume: str = ""
    part: str = ""
    episode: str = ""
    suffix: str = ""
    filename: str = ""
    completed: bool = False


@dataclass(frozen=True)
class EpubNameMeta:
    title: str = ""
    creator: str = ""


def clean_text(value) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace("​", "").replace("﻿", "")
    text = _SPACES_RE.sub(" ", text).strip()
    return text


def _clean_creator_name(value: str) -> str:
    text = clean_text(value)
    # "홍길동 저/역/글" 같은 역할 접미사는 제거
    text = re.sub(r"\s*(?:저|역|글|지음|지은이)\s*$", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def _strip_leading_author(text: str, author: str) -> str:
    text = clean_text(text)
    author = clean_text(author)
    if not text or not author:
        return text
    author_pattern = r"[\s_]*".join(re.escape(ch) for ch in author if not ch.isspace())
    stripped = re.sub(rf"^\s*{author_pattern}[\s_\-–—―]+", "", text, flags=re.IGNORECASE)
    return clean_text(stripped)


def _filename_marker_title(text: str) -> str:
    body = clean_text(text).replace("_", " ")
    match = re.search(
        r"(?:^|\s)(?:머리말|서문|프롤로그|prologue|preface)\s*[-–—―:：]\s*(?P<title>.+)$",
        body,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    title = clean_text(match.group("title"))
    return title if 2 < len(title) < 100 else ""


def stem_from_name(path=None, original_name: str = "") -> str:
    name = original_name or (Path(path).name if path else "")
    return clean_text(_EXT_RE.sub("", Path(name).name))


def split_author_prefix(stem: str):
    match = _AUTHOR_RE.match(stem)
    if not match:
        return "", stem
    return clean_text(match.group("author")), clean_text(match.group("body"))


def _strip_title_noise(stem: str) -> str:
    text = clean_text(stem)
    # 업로드 소스 표식 "(N)"은 제목 파싱에서 무시
    text = re.sub(r"\s*\(N\)\s*$", "", text, flags=re.IGNORECASE)
    # (완) or (完) with anything before closing paren
    text = re.sub(r"\s*\(.*?完\)\s*$", "", text)
    # [완결...] square bracket form
    text = re.sub(r"\s*\[.*?완결.*?\]\s*$", "", text, flags=re.IGNORECASE)
    # (완결), (완), [완], [완결] 등 다양한 괄호 형태
    text = re.sub(r"\s*[(\[]\s*(?:완결|완|完)\s*[)\]]\s*$", "", text, flags=re.IGNORECASE)
    # 끝에 붙은 단독 완결 (예: "상계무적 7 완결", "반 리로디드 13 완결")
    text = re.sub(r"\s+완결\s*$", "", text)
    return clean_text(text)


def _normalize_series_for_volume(series: str) -> str:
    series = clean_text(series)
    series = re.sub(r"\s+\d+\s*$", "", series)
    # 한글 문자 사이의 하이픈(공백 포함) → 공백으로 정규화 (예: 아이들-윈터러 → 아이들 윈터러)
    series = re.sub(r"(?<=[가-힣])\s*[-–—]\s*(?=[가-힣])", " ", series)
    return clean_text(series)


def _extract_edition_markers(text: str) -> list[str]:
    s = clean_text(text)
    if not s:
        return []
    found: list[str] = []
    for m in re.finditer(r"[\(\[（【]([^)\]）】]{1,20})[\)\]）】]", s):
        inner = clean_text(m.group(1))
        if _EDITION_TOKEN_RE.search(inner):
            found.append(f"[{inner}]")
    for m in re.finditer(_EDITION_TOKEN_RE, s):
        token = clean_text(m.group(0))
        if token:
            found.append(f"[{token}]")
    out: list[str] = []
    seen: set[str] = set()
    for x in found:
        k = x.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(x)
    return out


def _preserve_edition_markers(original_body: str, replaced_body: str) -> str:
    src = clean_text(original_body)
    dst = clean_text(replaced_body)
    markers = _extract_edition_markers(src)
    if not markers:
        return dst
    result = dst
    for marker in markers:
        plain = marker.strip("[]")
        if re.search(re.escape(plain), result, re.IGNORECASE):
            continue
        result = f"{result} {marker}".strip()
    return clean_text(result)


def _best_heading(html_headings) -> str:
    """첫 번째 유효한 heading 반환. 챕터 번호 형식("7. 제목", "第N章")은 건너뜀."""
    if not html_headings:
        return ""
    for heading in html_headings:
        text = clean_text(heading)
        if not text:
            continue
        if re.fullmatch(r"[\W_]+", text):
            continue
        if _GENERIC_BOOK_HEADING_RE.match(text):
            continue
        if _CHAPTER_HEADING_RE.search(text) or _UNICODE_CHAPTER_HEADING_RE.search(text):
            continue
        if text:
            return text
    return ""


def _looks_like_chapter_heading(value: str) -> bool:
    text = clean_text(value)
    return bool(text and (_CHAPTER_HEADING_RE.search(text) or _UNICODE_CHAPTER_HEADING_RE.search(text)))


def _side_marker_from_volume_match(match) -> str:
    trailing = clean_text(match.groupdict().get("trailing", "") if match else "")
    if not trailing:
        return ""
    trailing = trailing.strip("()[]（）【】 ")
    trailing = clean_text(trailing)
    if re.search(r"특별\s*외전", trailing, re.IGNORECASE):
        return "특별외전"
    if re.fullmatch(r"외전|번외|특전", trailing, re.IGNORECASE):
        return trailing
    return ""


def parse_epub_name(
    path=None,
    original_name: str = "",
    opf_meta=None,
    html_headings=None,
) -> ParsedName:
    _raw_stem = stem_from_name(path, original_name)
    stem = _strip_title_noise(_raw_stem)
    author, body = split_author_prefix(stem)

    meta_title = ""
    meta_creator = ""
    if isinstance(opf_meta, EpubNameMeta):
        meta_title = opf_meta.title
        meta_creator = opf_meta.creator
    elif isinstance(opf_meta, dict):
        meta_title = opf_meta.get("title", "")
        meta_creator = opf_meta.get("creator", "")

    # 완결 여부: 파일명 또는 OPF 제목에서 감지 (노이즈 제거 전 raw 값 기준)
    _completed = bool(
        _COMPLETED_DETECT_RE.search(_raw_stem)
        or (meta_title and _COMPLETED_DETECT_RE.search(meta_title))
    )

    if not author:
        author = _clean_creator_name(meta_creator)
    elif meta_creator:
        # [X], [A] 등 단일 알파벳/숫자 placeholder -> OPF creator 우선
        _mc = _clean_creator_name(meta_creator)
        if _mc and re.fullmatch(r"[A-Za-z0-9]", author):
            author = _mc

    _meta_title_clean = clean_text(meta_title)
    # 단편집/작품집 류는 제목 선두 인명을 작가로 우선 보정 (메타 creator 오염 대응)
    if _meta_title_clean and re.search(r"(?:단편집|단편선|작품집)", _meta_title_clean):
        _lead = re.match(r"^\s*([가-힣A-Za-z]{2,12})\s*(?:단편집|단편선|작품집)", _meta_title_clean)
        if _lead:
            author = _lead.group(1)

    # 파일명이 이미 권 패턴을 가지면(정상 파일) 파일명 시리즈명 우선 — OPF 덮어쓰기 건너뜀
    _filename_body_clean = _strip_title_noise(split_author_prefix(stem)[1])
    if author:
        _filename_body_clean = _strip_leading_author(_filename_body_clean, author)
    _filename_marker_source = _filename_marker_title(_filename_body_clean)
    _filename_has_vol = bool(
        _VOLUME_PART_RE.match(_filename_body_clean)
        or _VOLUME_RE.match(_filename_body_clean)
    )

    if _filename_has_vol:
        # 파일명에 N권 패턴 있음 → 파일명 body 그대로 사용 (시리즈명 보존)
        body = _filename_body_clean
    else:
        heading = _best_heading(html_headings)
        meta_title_reliable = bool(
            meta_title
            and not _looks_like_chapter_heading(meta_title)
            and not _GENERIC_BOOK_HEADING_RE.match(clean_text(meta_title))
        )
        if heading and meta_title_reliable:
            # A normal OPF/copyright title is more reliable than a front-spine
            # section heading such as a preface or first essay/chapter title.
            if not re.search(r"\d+\s*(?:\uAD8C|\uD654|\uC7A5|\uBD80|\uD3B8)\b", clean_text(heading)):
                heading = ""
        # meta_title에 숫자(볼륨 정보)가 있으면 heading 대신 meta_title 우선
        if heading and meta_title and re.search(r"\d", clean_text(meta_title)):
            if not re.search(r"\d+\s*(?:\uAD8C|\uD654|\uC7A5|\uBD80|\uD3B8)\b", clean_text(heading)):
                heading = ""
        if heading and meta_title and _looks_like_chapter_heading(heading) and not _looks_like_chapter_heading(meta_title):
            heading = ""
        heading_has_volume_marker = bool(
            heading and re.search(r"\d+\s*(?:\uAD8C|\uD654|\uC7A5|\uBD80|\uD3B8)\b", clean_text(heading))
        )
        filename_is_generic_section = bool(
            re.match(r"^(?:section|chapter|content|body|front|text|xhtml|page)[\s_-]*0*\d{1,6}$", _raw_stem, re.IGNORECASE)
        )
        if meta_title_reliable and not (heading_has_volume_marker and filename_is_generic_section):
            source = clean_text(meta_title or body)
        else:
            source = clean_text(_filename_marker_source or heading or meta_title or body)
        if source:
            _, source_without_author = split_author_prefix(source)
            new_body = source_without_author or body
            new_body = _preserve_edition_markers(body, new_body)
            # 파일명에 외전/번외 등 표시가 있고 소스에 없으면 파일명 body 유지
            _filename_has_side = bool(_SIDE_STORY_RE.search(body))
            _source_has_side = bool(_SIDE_STORY_RE.search(new_body))
            if not (_filename_has_side and not _source_has_side):
                body = new_body

    body = _strip_title_noise(body)
    if author:
        body = _strip_leading_author(body, author)
    body = humanize_series_title(body, author)

    match = _VOLUME_PART_RE.match(body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            part=str(int(match.group("part"))),
            completed=_completed,
            filename=stem,
        )

    match = _VOLUME_TRAILING_MARKER_RE.match(body) or _VOLUME_RE.match(body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            suffix=_side_marker_from_volume_match(match),
            completed=_completed,
            filename=stem,
        )

    # Filename forms such as "쾌도무적 1권 - 3" are more reliable than OPF
    # titles that omit the "권" suffix or duplicate the volume number.
    filename_body = split_author_prefix(stem)[1]
    match = _VOLUME_PART_RE.match(filename_body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            part=str(int(match.group("part"))),
            completed=_completed,
            filename=stem,
        )

    match = _VOLUME_TRAILING_MARKER_RE.match(filename_body) or _VOLUME_RE.match(filename_body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            suffix=_side_marker_from_volume_match(match),
            completed=_completed,
            filename=stem,
        )

    # -- 추가 패턴: 권 suffix 없는 형식들 --
    # "시리즈 N : 부제목" 형식 (예: 치우천왕기 1 : 형제)
    for _src in (body, filename_body):
        match = _VOLUME_SUBTITLE_RE.match(_src)
        if match:
            return ParsedName(
                author=author,
                series=_normalize_series_for_volume(match.group("series")),
                volume=str(int(match.group("volume"))) + "권",
                suffix=clean_text(match.group("subtitle")),
                completed=_completed,
                filename=stem,
            )

    # "시리즈 N-M" 형식 (예: 비포 더 던 1-1)
    for _src in (body, filename_body):
        range_match = _EPISODE_RANGE_RE.match(_src)
        if range_match:
            start = int(range_match.group("start"))
            end = int(range_match.group("end"))
            if end > start and end - start >= 10:
                return ParsedName(
                    author=author,
                    series=clean_text(range_match.group("series")),
                    episode=f"{start}-{end}",
                    completed=_completed or bool(range_match.group("done")),
                    filename=stem,
                )
        match = _VOLUME_PART_DASH_RE.match(_src)
        if match:
            return ParsedName(
                author=author,
                series=_normalize_series_for_volume(match.group("series")),
                volume=str(int(match.group("volume"))) + "권",
                part=str(int(match.group("part"))),
                completed=_completed,
                filename=stem,
            )

    # "시리즈N본문/본편" 붙여쓰기 형식 (예: 헤븐스톤1본문)
    for _src in (body, filename_body):
        match = _CONCAT_VOLUME_SUFFIX_RE.match(_src)
        if match:
            return ParsedName(
                author=author,
                series=clean_text(match.group("series")),
                volume=str(int(match.group("volume"))) + "권",
                completed=_completed,
                filename=stem,
            )

    # "시리즈 N" 형식 — 권 없이 숫자만 끝에 (예: 반 리로디드 1, 상계무적 7)
    # body(OPF/heading 소스)에만 적용 — 파일명 폴백은 제외
    match = _PLAIN_VOLUME_RE.match(body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            completed=_completed,
            filename=stem,
        )
    match = _PLAIN_VOLUME_RE.match(filename_body)
    if match:
        return ParsedName(
            author=author,
            series=_normalize_series_for_volume(match.group("series")),
            volume=str(int(match.group("volume"))) + "권",
            completed=_completed,
            filename=stem,
        )

    episode = ""
    ep_match = _EPISODE_RE.search(body)
    if ep_match:
        episode = str(int(ep_match.group("episode")))
    if not episode:
        file_episode = re.search(r"(?:^|_)(\d{1,5})$", _raw_stem)
        if file_episode and "_" in _raw_stem:
            episode = str(int(file_episode.group(1)))

    series_text = clean_text(body or stem)
    if episode:
        # 시리즈 키 분할 방지: "... 1화" 같은 회차 접미사는 시리즈명에서 제거
        series_text = clean_text(
            re.sub(
                rf"(?<!\d){re.escape(episode)}\s*(?:화|장|회)\b\s*$",
                "",
                series_text,
                flags=re.IGNORECASE,
            )
        ) or series_text

    return ParsedName(
        author=author,
        series=series_text,
        episode=episode,
        completed=_completed,
        filename=stem,
    )


def safe_filename(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r'[\\/:*?"<>|]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or "untitled"


def format_rename_name(parsed: ParsedName) -> str:
    pieces = [parsed.series]
    if parsed.volume:
        pieces.append(parsed.volume)
    name = " ".join(p for p in pieces if p)
    if parsed.part:
        name = name + " - " + parsed.part
    elif parsed.suffix:
        if parsed.volume and re.fullmatch(r"특별외전|외전|번외|특전", parsed.suffix, re.IGNORECASE):
            name = name + " (" + parsed.suffix + ")"
        else:
            name = name + " - " + parsed.suffix
    elif parsed.episode and not parsed.volume:
        ep_no = parsed.episode
        # Avoid duplicate episode suffix when the title already contains the same episode marker.
        if "-" not in ep_no:
            ep_no = str(int(ep_no))
        if not re.search(rf"(?<!\d){re.escape(ep_no)}\s*\uD654\b", clean_text(name), re.IGNORECASE):
            name = name + " " + ep_no + "\uD654"
    if parsed.completed:
        name = name + " (완결)"
    if parsed.author and parsed.author != parsed.series:
        name = "[" + parsed.author + "] " + name
    return safe_filename(name) + ".epub"


def format_toc_label(parsed: ParsedName) -> str:
    pieces = [parsed.series]
    if parsed.volume:
        pieces.append(parsed.volume)
    if parsed.part:
        pieces.append("- " + parsed.part)
    return clean_text(" ".join(p for p in pieces if p)) or parsed.filename


def series_zip_key(parsed: ParsedName, keep_author: bool = True) -> str:
    key = parsed.series
    key = re.sub(r"\s+\d+\s*부\s*$", "", key).strip()
    if keep_author and parsed.author and parsed.author != parsed.series:
        key = "[" + parsed.author + "] " + key
    return safe_filename(key)


def series_zip_key_from_filename(filename: str, keep_author: bool = True) -> str:
    parsed = parse_epub_name(original_name=filename)
    if parsed.volume or parsed.part or parsed.episode:
        key = series_zip_key(parsed, keep_author=keep_author)
        key = re.sub(r"\s+\d+\s*부\s*$", "", key).strip()
        # 파서가 회차를 series로 남긴 경우에도 묶음 키는 동일 시리즈로 정규화
        key = re.sub(r'\s+(?:제\s*)?\d+\s*(?:화|장|회)\s*$', '', key, flags=re.IGNORECASE).strip()
        key = re.sub(r'(?<=[가-힣A-Za-z])(?:제\s*)?\d+\s*(?:화|장|회)\s*$', '', key, flags=re.IGNORECASE).strip()
        return safe_filename(key)

    author, body = split_author_prefix(stem_from_name(original_name=filename))
    key = _strip_title_noise(body)
    key = re.sub(r'\s+(?:제\s*)?\d+\s*(?:화|장|회)\s*$', '', key, flags=re.IGNORECASE)
    key = re.sub(r'(?<=[가-힣A-Za-z])(?:제\s*)?\d+\s*(?:화|장|회)\s*$', '', key, flags=re.IGNORECASE)
    key = _SIDE_STORY_RE.sub("", key)
    key = _TRAILING_PAREN_NUM_RE.sub("", key)
    # 완결/완/完 suffix 먼저 제거 (뒤에 붙으면 TRAILING 숫자 패턴이 안 잡힘)
    key = re.sub(r"\s+(?:완결|완|完)\s*$", "", key)
    key = re.sub(r"\s+\d{1,4}\s*\.\s*\d{1,4}\s*$", "", key)
    key = _TRAILING_MULTI_NUMBER_RE.sub("", key)
    key = _TRAILING_SINGLE_NUMBER_RE.sub("", key)
    key = _normalize_series_for_volume(key)
    if keep_author and author and author != key:
        key = "[" + author + "] " + key
    return safe_filename(key or parsed.series or parsed.filename)
