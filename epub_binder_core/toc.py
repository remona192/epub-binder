from __future__ import annotations

from html import unescape
from pathlib import Path
import re

from epub_binder_core.title_metadata import (
    is_chapterish_title as _is_chapterish_title,
    is_generic_ncx_label as _is_generic_ncx_label,
    normalize_title as _normalize_title,
    safe_title as _safe_title,
    strip_filename_parse_noise as _strip_filename_parse_noise,
)


_TAG_RE = re.compile(r"<[^>]+>")


def decode_markup_bytes(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def html_to_plain_text(raw_html: str) -> str:
    text = _TAG_RE.sub("", raw_html)
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()

# Legacy-parity page skipping and chapter heading helpers.
_decode_markup_bytes = decode_markup_bytes

_CR_FILENAME = re.compile(
    r'copyright|colophon|publication.?right|rights?|imprint',
    re.IGNORECASE)


_CR_FILENAME_KO = re.compile(
    r'판권|저작권|크레딧|credit',
    re.IGNORECASE)


_CR_FILENAME_WEAK = re.compile(
    r'^(p?_?info|book_?info|pub_?info|last_?page?|page_?last|'
    r'end_?page?|back|tail|notice|credit|closing|afterword)$',
    re.IGNORECASE)


_CR_CLASS = re.compile(
    r'xnmManagedNote|(?<![_\-\w])copyright(?![_\-\w])|colophon|publication.?right',
    re.IGNORECASE)


_CR_TEXT_STRONG = re.compile(
    r'초판\s*발행|ISBN[\s\-:：]|발행일\s*[:：]|출판등록\s*번호|'
    r'무단\s*전재\s*및\s*복제|무단\s*복제\s*금지|저작권법|독점\s*계약|'
    r'all\s+rights?\s+reserved|©\s*20\d\d|©[^\n]{0,30}20\d\d|'
    r'출판신고|무단\s*전재[,\s]',   # | 구분자형 판권 (출판신고, 쉼표형 무단전재)
    re.IGNORECASE)


_CR_TEXT_WEAK = [
    re.compile(r'펴낸곳\s*[:：|]',        re.IGNORECASE),
    re.compile(r'펴낸이\s*[:：|]',        re.IGNORECASE),
    re.compile(r'지은이\s*[:：|]',        re.IGNORECASE),
    re.compile(r'저\s*자\s*[:：|]',       re.IGNORECASE),   # "저 자 | 르뮈" 형태
    re.compile(r'발\s*행\s*처\s*[:：|]',  re.IGNORECASE),   # "발 행 처 | 블리뉴" 형태
    re.compile(r'출판사\s*[:：]',         re.IGNORECASE),
    re.compile(r'전자책\s*발행',      re.IGNORECASE),
    re.compile(r'e-?book\s*(발행|출판|edition)', re.IGNORECASE),
    re.compile(r'뷰컴즈|텐북|카카오페이지|리디북스|네이버시리즈|'
               r'문피아|조아라|로크미디어|대원씨아이|황금가지', re.IGNORECASE),
    re.compile(r'본\s*(도서|책|전자책)는?\s*(저작권|무단)', re.IGNORECASE),
]


def is_skip_page(filename: str, content_bytes: bytes) -> str:
    """판권/목차 페이지면 사유 문자열 반환, 아니면 None.

    판권 감지 전략:
    1. 파일명 강한 패턴 → 즉시 판권
    2. CSS class 패턴 → 즉시 판권
    3. 텍스트 강한 패턴 → 즉시 판권
    4. 파일명 약한 패턴 + 텍스트 약한 패턴 1개 → 판권
    5. 텍스트 약한 패턴 2개 이상 + 짧은 페이지(2000자 미만) → 판권
    목차: 짧고 목차 + 장/화 번호 목록 포함
    """
    name = Path(filename).stem.lower()
    raw  = _decode_markup_bytes(content_bytes)
    import html as _html_mod
    text = re.sub(r'<[^>]+>', '', raw)
    text = _html_mod.unescape(text)          # &lt;목차&gt; → <목차> 등 엔티티 디코딩
    text = text.replace('│', '|').replace('┃', '|')  # 박스문자 파이프 정규화
    text = text.replace('ⓒ', '©')           # 원문자 ⓒ → © 정규화
    text = re.sub(r'\s+', ' ', text).strip()
    head = text[:800]   # 판권은 앞부분에 몰려 있음

    # 1. 파일명 강한 패턴
    if _CR_FILENAME.search(name) or _CR_FILENAME_KO.search(name):
        return 'copyright'

    # 2. CSS class 패턴
    for cls in re.findall(r'class=["\']([^"\']+)["\']', raw):
        if _CR_CLASS.search(cls):
            return 'copyright'

    # 3. 텍스트 강한 패턴 (본문이 긴 경우 복합 파일 → 유지)
    if _CR_TEXT_STRONG.search(head) and len(text) < 2000:
        return 'copyright'

    # 4. 파일명 약한 패턴 + 텍스트 약한 패턴 1개 (본문 긴 경우 유지)
    weak_name = bool(_CR_FILENAME_WEAK.search(name))
    weak_hits = sum(1 for p in _CR_TEXT_WEAK if p.search(head))
    if weak_name and weak_hits >= 1 and len(text) < 2000:
        return 'copyright'

    # 5. 짧은 페이지 + 텍스트 약한 패턴 2개 이상
    if len(text) < 2000 and weak_hits >= 2:
        return 'copyright'

    # 카카오페이지 chapter_0: 파일명이 정확히 chapter_0이고 이미지만 있는 화 표지 반복 페이지
    if name == 'chapter_0':
        has_img = bool(re.search(r'<img\b', raw, re.IGNORECASE))
        if has_img and len(text) < 100:
            return 'cover'

    # cover 페이지: 파일명에 cover 포함 + 실질 텍스트 없음 → 제거
    # map/삽화 이미지 페이지는 유지 (챕터 구분 삽화, 지도 등 의미있는 콘텐츠)
    # (<style> 블록 제거 후 텍스트로 판단 — CSS 인라인 텍스트 오탐 방지)
    if 'cover' in name or re.search(r'<img\b', raw, re.IGNORECASE):
        raw_no_style = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL|re.IGNORECASE)
        text_no_style = re.sub(r'<[^>]+>', '', raw_no_style)
        text_no_style = _html_mod.unescape(text_no_style)  # &#xc218; 등 엔티티 디코딩 후 길이 측정
        text_no_style = re.sub(r'\s+', ' ', text_no_style).strip()
        # cover 파일명 + img 태그 있음 + 텍스트 60자 미만 → 표지로 제거
        # img src 파일명에 cover가 포함된 경우도 표지로 감지
        # (bastian_cover.jpg 참조하는 bastian_000.xhtml 같은 케이스 대응)
        has_img = bool(re.search(r'<img\b', raw, re.IGNORECASE))
        if has_img and len(text_no_style) < 60:
            _img_src_m = re.search(r'<img\b[^>]+src=["\']([^"\']+)["\']', raw, re.IGNORECASE)
            _img_is_cover = bool(_img_src_m and 'cover' in Path(_img_src_m.group(1)).name.lower())
            if 'cover' in name or _img_is_cover:
                return 'cover'

    # 목차 페이지: 파일명에 toc / table / contents / index / book_table 포함
    if re.search(r'\btoc\b|^table$|^contents?$|^index$|^book_table$', name):
        return 'index'

    _chap_num_pat = re.compile(
        r'\d+[장화부]|\d+-\d+[.\s]|Episode\s*\d+|Ch(apter)?\s*\d+', re.IGNORECASE)

    # 목차 페이지: 짧고 "목차"/"차례"/"<목차>"/"Contents" + 장/화 번호 나열
    if len(text) < 1200 and re.search(r'목차|차례|<목차>|Contents', text, re.IGNORECASE) \
            and _chap_num_pat.search(text):
        return 'index'

    # 목차 페이지: 매우 짧고(200자 미만) 장/화 번호가 각각 다른 블록 요소(<p>/<li> 등)에 나열
    # "3부 2장 - 제목" 처럼 단일 요소 안에 숫자 2개가 있는 챕터 제목은 오탐 방지
    if len(text) < 200:
        _block_texts = re.findall(
            r'<(?:p|li|div|td|dd|h[1-6])\b[^>]*>(.*?)</(?:p|li|div|td|dd|h[1-6])>',
            raw, re.IGNORECASE | re.DOTALL)
        _blocks_with_num = sum(
            1 for _b in _block_texts
            if _chap_num_pat.search(re.sub(r'<[^>]+>', '', _b)))
        if _blocks_with_num >= 2:
            return 'index'

    return None


_TITLE_PATS = [
    # 0. sigil_toc_id: NCX 연결 포인트 (가장 정확한 챕터 헤딩)
    (re.compile(r'<[^>]+\bid="sigil_toc_id[^"]*"[^>]*>(.*?)</[a-z0-9]+>', re.IGNORECASE | re.DOTALL), 1),
    # 1. h1~h6 태그 (sigil_not_in_toc 제외)
    (re.compile(r'<h[1-6](?![^>]*sigil_not_in_toc)[^>]*>(.*?)</h[1-6]>', re.IGNORECASE | re.DOTALL), 1),
    # 1.5. box-line 계열 챕터 (알에스미디어/신규 양식)
    # 예) <p class="font3"><span class="box-line1">프롤로그</span></p>
    # 예) <p class="font3"><span class="box-line1">#001화. ███(이)가 ███을(를) 숨김 (1)</span></p>
    # 같은 파일에 <span class="t-num2">책 제목</span>이 같이 있어도
    # box-line 클래스가 붙은 것만 챕터 제목으로 채택된다.
    (re.compile(
        r'<p[^>]*>\s*<span[^>]*\bclass=["\'][^"\']*\bbox-line\d*\b[^"\']*["\'][^>]*>(.*?)</span>\s*</p>',
        re.IGNORECASE | re.DOTALL), 1),
    # 1.6. id="id_top" 챕터 (Calibre/탈옥한 천재마법사 등)
    # 예) <p id="id_top" class="block_">#001화. 입소 (1)</p>
    (re.compile(
        r'<p[^>]*\bid=["\']id_top["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL), 1),
    # 2. 챕터/제목 관련 class
    (re.compile(
        r'<[^>]+class=["\'][^"\']*(?:chapter|chap|Title|title|header|heading|'
        r'part_header_title|section_title|np|toc\b)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
        re.IGNORECASE | re.DOTALL), 1),
    # 3. p태그: 숫자+화/장/권/부/절/막/편 (단독 or 부제 포함)
    # 긴 부제(예: 221화. ... (1)) 대응을 위해 허용 길이를 40→120으로 확장
    (re.compile(
        r'<p[^>]*>\s*((?:\d+[-−~]\d+|\d+)\s*[화장권부절막편]\s*[.\s)）]?.{0,120}?)\s*</p>',
        re.IGNORECASE), 1),
    # 3.2. p태그 내부 span 화수 제목
    # 예) <p class="center"><span class="...">248화</span></p>
    # 예) <p><span>262화</span><span>&#160;</span></p>
    (re.compile(
        r'<p[^>]*>\s*<span\b[^>]*>\s*((?:\d+[-−~]\d+|\d+)\s*[화장권부절막편]\s*[.\s)）]?.{0,120}?)\s*</span>'
        r'(?:\s*<span\b[^>]*>\s*(?:&nbsp;|&#160;|\xa0)?\s*</span>)*\s*</p>',
        re.IGNORECASE | re.DOTALL), 1),
    # 3.5. p태그: #N 형식 챕터 제목
    # 예) <p>#101 전쟁의 결과</p>       — 공백 구분
    # 예) <p>#1. 집행자 (1)</p>         — 마침표 바로 붙음
    # 예) <p>#001화. 입소 (1)</p>       — 숫자 뒤에 '화' 바로 붙음
    # 예) <p>#12: 부제목</p>            — 콜론 구분
    # 예) <p>#1</p>                    — 숫자만
    (re.compile(
        r'<p[^>]*>\s*([#＃]\s*\d+[^<]{0,80})\s*</p>',
        re.IGNORECASE), 1),
    # 4. p태그: X.X 형식 제목 (e.g. 1.1 서론, 2부 3장)
    (re.compile(
        r'<p[^>]*>\s*(\d+[부권]?\s*[-\.]\s*\d*\s*.{2,40}?)\s*</p>',
        re.IGNORECASE), 1),
    # 5. p태그: "1부. 부제", "제1장", "서막" 등 선두 키워드
    (re.compile(
        r'<p[^>]*>\s*((?:제?\d+\s*[부장절막편권화]\s*[.\.。·]?\s*.{1,40}|'
        r'프롤로그|에필로그|서막|종막|막간|외전|번외|특전))\s*</p>',
        re.IGNORECASE), 1),
    # 6. p/div 내부 b/strong 단독
    # 예) <p><b>제목</b></p>
    # 예) <div><b>#147화_마경으로(4)</b></div>
    # 예) <div><b>#167화_임모탈(5)</b><br/></div>  — 끝에 <br/> 오는 경우
    (re.compile(
        r'<(?:p|div)[^>]*>\s*<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>\s*(?:<br\s*/?>\s*)*</(?:p|div)>',
        re.IGNORECASE | re.DOTALL), 1),
    # 3.6. p태그 내부 span 인라인 bold — 예: <p><span style="font-weight: bold;">#1화_용병단 키우기</span><br/></p>
    (re.compile(
        r'<p[^>]*>\s*<span\b[^>]+font-weight\s*:\s*bold[^>]*>(.*?)</span>\s*(?:<br\s*/?>\s*)*</p>',
        re.IGNORECASE | re.DOTALL), 1),
]


_CENTER_BOLD_PAT = re.compile(
    r'<p\b[^>]*text-align\s*:\s*center[^>]*>(.*?)</p>',
    re.IGNORECASE | re.DOTALL)


_CHAP_NUM_TITLE  = re.compile(
    r'^(?:\d+[-−~]\d+|\d+)[.\-\s].{1,60}$')


_SUBNAV_HEAD_PAT = re.compile(
    r'^(?:prologue|epilogue|chapter\s*\d+|ch\.?\s*\d+|part\s*\d+'
    r'|프롤로그|에필로그|서장|종장|외전|번외|특전)$',
    re.IGNORECASE)

_QUOTE_BULLET_PAT = re.compile(r'^[≫▶▷▸▹►»]+')
_PLAIN_NUM_BULLET_PAT = re.compile(r'^\d+\s*[.)]\s*$')
_PLAIN_NUM_ONLY_PAT = re.compile(r'^\d+\s*$')
_MULTI_NUM_LIST_PAT = re.compile(r'\d+\s*[.)]\s*.+\d+\s*[.)]\s*.+')
_SINGLE_NUM_LIST_PAT = re.compile(r'^\d+\s*[.)]\s*\S+')
_PRIMARY_CHAPTER_PAT = re.compile(
    r'(?:(?<![가-힣])제?\s*\d+\s*[화장권부편절막회]'
    r'|^[#＃]\s*\d+'
    r'|^chapter\s*\d+'
    r'|^ch\.?\s*\d+)',
    re.IGNORECASE,
)


def _is_noise_heading_candidate(s: str) -> bool:
    t = _normalize_title(s or "")
    if not t:
        return True
    if t.startswith("\u226B"):
        return True
    if re.match(r"^\[[^\]]+\]\s*.+\d+\s*(?:\uAD8C|\uD654|\uC7A5|\uBD80|\uD3B8)\s*$", t):
        return True
    if _QUOTE_BULLET_PAT.match(t):
        return True
    if _PLAIN_NUM_BULLET_PAT.match(t) or _PLAIN_NUM_ONLY_PAT.match(t):
        return True
    # 본문 번호 목록(예: "1. 이정찬 ... 2. 차 변호사 ...")은 제목 후보에서 제외
    if _MULTI_NUM_LIST_PAT.search(t):
        return True
    return False


def _is_single_numbered_list_text(s: str) -> bool:
    """?? ?? ?? ? ?(?: '1. ?? ??')?? ??."""
    t = _normalize_title(s or "")
    if not t:
        return False
    if not _SINGLE_NUM_LIST_PAT.match(t):
        return False
    if re.search(r'(?:\d+\s*[??????]|chapter\s*\d+|ch\.?\s*\d+|part\s*\d+)', t, re.IGNORECASE):
        return False
    return True


def _is_primary_chapter_heading(s: str) -> bool:
    t = _normalize_title(s or "")
    if not t:
        return False
    return bool(_PRIMARY_CHAPTER_PAT.search(t))


def _is_probable_plain_number_sentence(s: str) -> bool:
    t = _normalize_title(s or "")
    if not t:
        return False
    # 연/날짜/소수 등: 6.25, 3.3% ...
    if re.match(r"^\d+\.\d+(?:\s|$|%)", t):
        return True
    # 번호 매기기 문장형: "1. ...한다." / "2) ...였다."
    if re.match(r"^\d+\s*[\.\)]\s*\S+", t):
        if re.search(r"(?:다|요|니다|였다|한다|했다)[.!?]?$", t):
            return True
        if len(t) >= 16 and not _is_chapterish_title(t):
            return True
    return False


def _looks_like_body_sentence(s: str) -> bool:
    t = _normalize_title(s or "")
    if not t:
        return False
    if _is_chapterish_title(t):
        return False
    if _is_probable_plain_number_sentence(t):
        return True
    if re.match(r"^\[[^\]]+\]\s*.+\d+\s*권\s*$", t):
        return True
    if len(t) < 25:
        return False
    if not re.search(r'[.!?…]$', t):
        return False
    return len(t.split()) >= 5


def _is_subnav_heading_candidate(s: str) -> bool:
    """한 xhtml 내 분할용(sub-navPoint) 헤딩으로 쓸 수 있는지 판정."""
    t = _normalize_title(s or '')
    if not t or not (2 <= len(t) <= 70):
        return False
    if _is_noise_heading_candidate(t):
        return False
    if re.fullmatch(
        r"(?:prologue|epilogue|interlude|\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5)",
        t,
        re.IGNORECASE,
    ):
        return True
    if _is_single_numbered_list_text(t):
        return False
    if _is_probable_plain_number_sentence(t):
        return False
    if re.match(r"^\[[^\]]+\]\s*.+\d+\s*권\s*$", t):
        return False
    # 본문 문장 종결형은 제외
    if re.search(r'[.!?…]$', t):
        return False
    # 챕터/화수형 제목은 허용
    if _is_chapterish_title(t):
        return True
    # 명시적 헤딩 키워드 허용
    if _SUBNAV_HEAD_PAT.match(t):
        return True
    # 숫자형 챕터(예: 1.1 제목, 2-3 제목)
    if re.match(r'^\d+(?:[.\-]\d+)?\s+\S+', t):
        return True
    # 너무 긴 일반 문장은 제외
    if len(t.split()) >= 6:
        return False
    return False


def extract_all_subheadings(raw_str: str):
    """xhtml 본문 내 모든 굵은 헤딩(p>b/strong, h1~h6)을 문서 순서대로 반환.
    538356_1.epub처럼 한 파일에 여러 챕터 제목이 있는 경우를 위함.

    Returns:
        list of (title_text, full_match_html, match_start_offset)
        — 위치는 raw_str 내 시작 인덱스.
    """
    found = []
    seen_offsets = set()
    # 1) <p ...><b/strong>...</b/strong></p>  또는  <div><b>...</b></div>
    p_b_pat = re.compile(
        r'<(?P<wrap>p|div)\b[^>]*>\s*<(b|strong)\b[^>]*>(.*?)</\2>\s*(?:<br\s*/?>\s*)*</(?P=wrap)>',
        re.IGNORECASE | re.DOTALL)
    for m in p_b_pat.finditer(raw_str):
        inner = m.group(3)
        # <br/> → 공백, 나머지 태그 제거
        text = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = _normalize_title(text)
        text = _safe_title(text)
        if 1 < len(text) < 80 and not _is_noise_heading_candidate(text) and m.start() not in seen_offsets:
            found.append((text, m.group(0), m.start()))
            seen_offsets.add(m.start())
    # 2) h1~h6 (sigil_not_in_toc 제외)
    h_pat = re.compile(
        r'<(h[1-6])(?![^>]*sigil_not_in_toc)[^>]*>(.*?)</\1>',
        re.IGNORECASE | re.DOTALL)
    for m in h_pat.finditer(raw_str):
        inner = m.group(2)
        text = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = _normalize_title(text)
        text = _safe_title(text)
        if 1 < len(text) < 80 and not _is_noise_heading_candidate(text) and m.start() not in seen_offsets:
            found.append((text, m.group(0), m.start()))
            seen_offsets.add(m.start())
    # 3) center 정렬 + bold span 패턴
    for m in _CENTER_BOLD_PAT.finditer(raw_str):
        if m.start() in seen_offsets:
            continue
        inner = m.group(1)
        # bold가 실제로 있는지 확인 (단순 center 정렬 텍스트는 제외)
        if not re.search(r'(font-weight\s*:\s*bold|<(?:b|strong)\b)',
                         inner, re.IGNORECASE):
            continue
        inner_no_br = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', inner_no_br)
        text = _normalize_title(text)
        text = _safe_title(text)
        if 1 < len(text) < 80 and not _is_noise_heading_candidate(text):
            found.append((text, m.group(0), m.start()))
            seen_offsets.add(m.start())
    # 4) p 내부 span 인라인 bold — <p><span style="font-weight: bold;">제목</span></p>
    p_span_bold_pat = re.compile(
        r'<p\b[^>]*>\s*<span\b[^>]+font-weight\s*:\s*bold[^>]*>(.*?)</span>\s*(?:<br\s*/?>\s*)*</p>',
        re.IGNORECASE | re.DOTALL)
    for m in p_span_bold_pat.finditer(raw_str):
        if m.start() in seen_offsets:
            continue
        inner = m.group(1)
        text = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = _normalize_title(text)
        text = _safe_title(text)
        if 1 < len(text) < 80 and not _is_noise_heading_candidate(text):
            found.append((text, m.group(0), m.start()))
            seen_offsets.add(m.start())
    # 위치 순으로 정렬
    found.sort(key=lambda x: x[2])
    merged = []
    skip_next = False
    for idx, item in enumerate(found):
        if skip_next:
            skip_next = False
            continue
        title, full, start = item
        if idx + 1 < len(found) and re.match(r'^(?:프롤로그|에필로그|prologue|epilogue)$', title, re.IGNORECASE):
            next_title, next_full, _next_start = found[idx + 1]
            if next_title and not _is_primary_chapter_heading(next_title) and not _is_noise_heading_candidate(next_title):
                merged.append((f"{title} - {next_title}", full + next_full, start))
                skip_next = True
                continue
        merged.append(item)
    found = merged
    # 화/장 계열의 정규 챕터 헤딩이 하나라도 있으면
    # 그 외 보조/하위호환 헤딩은 제외해 목차 오염을 줄인다.
    if found and any(_is_primary_chapter_heading(_t) for _t, _, _ in found):
        found = [
            it for it in found
            if _is_primary_chapter_heading(it[0])
            or re.fullmatch(
                r"(?:prologue|epilogue|interlude|\uD504\uB864\uB85C\uADF8|\uC5D0\uD544\uB85C\uADF8|\uC11C\uC7A5|\uC885\uC7A5)",
                _normalize_title(it[0] or ""),
                re.IGNORECASE,
            )
        ]
    return found


def inject_subheading_anchors(raw_str: str, subheadings: list, id_prefix: str = "sub"):
    """subheadings 리스트의 각 매치 직전에 <a id="..."/> 앵커 삽입.
    각 항목은 (title, full_match_html, start_offset).

    Returns:
        (new_raw_str, [(anchor_id, title), ...]) — 앵커 id와 제목 매핑 (문서 순서 유지)
    """
    if not subheadings:
        return raw_str, []
    # 뒤에서부터 삽입해야 앞쪽 offset이 깨지지 않음
    out = raw_str
    anchor_map = []
    for i, (title, _full, start) in enumerate(subheadings):
        anchor_id = f'{id_prefix}_{i+1:03d}'
        anchor_map.append((anchor_id, title))
    # 정방향으로 anchor_map 만들고, 역방향으로 삽입
    for i in range(len(subheadings) - 1, -1, -1):
        title, _full, start = subheadings[i]
        anchor_id = anchor_map[i][0]
        anchor_tag = f'<a id="{anchor_id}"></a>'
        out = out[:start] + anchor_tag + out[start:]
    return out, anchor_map


_MARKER_ONLY_PAT = re.compile(
    r'^(?:제\s?)?\d+\s*[화장권부절막편회]$'
    r'|^[#＃]\s*\d+(?:\s*[화])?$'
    r'|^(?:프롤로그|에필로그|서장|종장|외전|번외|막간|특전)$')


def _find_marker_subtitle_pair(raw: str):
    """연속한 두 <p>: 첫 번째가 챕터 마커, 두 번째가 부제인 경우 결합 반환.
    예)
        <p class="a" style="text-align: center;">1화</p>
        <p class="a" style="text-align: center;">종남의 사파 천하제일 검수</p>
        → "1화. 종남의 사파 천하제일 검수"

    오탐 방지:
    - 두 <p> 모두 center 정렬이거나 같은 class 를 가져야 함
    - 마커는 12자 이하
    - 부제는 2~60자, 또 다른 챕터 마커가 아니어야 함
    - 부제가 본문 문장처럼 마침표/따옴표로 끝나면 제외
    """
    def _clean(html_inner: str) -> str:
        t = re.sub(r'<br\s*/?>', ' ', html_inner, flags=re.IGNORECASE)
        t = re.sub(r'<[^>]+>', '', t)
        t = _normalize_title(t)
        t = _safe_title(t)
        return re.sub(r'\s+', ' ', t).strip()

    def _is_centered(open_tag: str) -> bool:
        return bool(re.search(
            r'text-align\s*:\s*center|align\s*=\s*["\']?center',
            open_tag, re.IGNORECASE))

    def _class_attr(open_tag: str) -> str:
        m = re.search(r'\bclass\s*=\s*["\']([^"\']+)["\']', open_tag, re.IGNORECASE)
        return m.group(1).strip().lower() if m else ''

    # (start, open_tag_str, text) 수집
    p_blocks = []
    for m in re.finditer(r'(<p\b[^>]*>)(.*?)</p>', raw, re.IGNORECASE | re.DOTALL):
        p_blocks.append((m.start(), m.group(1), _clean(m.group(2))))

    for i, (_s, otag1, text1) in enumerate(p_blocks):
        if not text1 or len(text1) > 12:
            continue
        if not _MARKER_ONLY_PAT.match(text1):
            continue

        # 다음 비어있지 않은 <p> 찾기 (최대 3개 앞만 검사)
        for j in range(i + 1, min(i + 4, len(p_blocks))):
            _s2, otag2, text2 = p_blocks[j]
            if not text2:
                continue   # 빈 <p><br/></p> 건너뜀
            # 부제 검증
            if len(text2) < 2 or len(text2) > 60:
                break
            if _MARKER_ONLY_PAT.match(text2):
                break    # 또 다른 마커면 부제 아님
            # 본문 문장 가능성 (마침표·물음표·큰따옴표 종결)
            if re.search(r'[.!?"”’]$', text2):
                break
            # 스타일 매치 확인: 둘 다 center 정렬 이거나 같은 class
            cls1, cls2 = _class_attr(otag1), _class_attr(otag2)
            ctr1, ctr2 = _is_centered(otag1), _is_centered(otag2)
            style_ok = (ctr1 and ctr2) or (cls1 and cls1 == cls2)
            if not style_ok:
                break
            return f'{text1}. {text2}'
        # 첫 비어있지 않은 다음 p에서 부제 못 찾으면 다음 마커 후보로 진행
    return None


def _find_prologue_epilogue_bold_pair(raw: str):
    """연속 bold 문단의 에필로그/프롤로그 + 소제목 조합을 결합해 반환."""
    pair_pat = re.compile(
        r'<p\b[^>]*>\s*<(?:b|strong)\b[^>]*>(.*?)</(?:b|strong)>\s*</p>\s*'
        r'<p\b[^>]*>\s*<(?:b|strong)\b[^>]*>(.*?)</(?:b|strong)>\s*(?:<br\s*/?>\s*)*</p>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in pair_pat.finditer(raw):
        head = _safe_title(_normalize_title(re.sub(r'<[^>]+>', '', m.group(1))))
        sub = _safe_title(_normalize_title(re.sub(r'<[^>]+>', '', m.group(2))))
        if not head or not sub:
            continue
        if len(sub) > 60:
            continue
        if re.match(r'^(?:epilogue|prologue|에필로그|프롤로그)$', head, re.IGNORECASE):
            if _normalize_title(sub).lower() == _normalize_title(head).lower():
                return head
            return f"{head} - {sub}"
    return None


def extract_chapter_title(content_bytes: bytes):
    """xhtml 본문에서 챕터 제목 추출. 없으면 None"""
    raw = content_bytes.decode('utf-8', 'replace')

    # ── 0순위: 연속한 두 <p> — 마커 + 부제 결합 ──────────
    # 예) <p>1화</p><p>종남의 사파 천하제일 검수</p> → "1화. 종남의 사파 천하제일 검수"
    combined = _find_marker_subtitle_pair(raw)
    if combined and 2 < len(combined) < 80 and not _is_single_numbered_list_text(combined):
        return combined

    ep_pair = _find_prologue_epilogue_bold_pair(raw)
    if ep_pair and 2 < len(ep_pair) < 90 and not _is_single_numbered_list_text(ep_pair):
        return ep_pair

    # ── 0.5순위: 다중 서브헤딩에서 화수/챕터 마커 우선 ───────
    # 예) 한 파일에 "작품명 / Prologue / 1화..."가 함께 있을 때 1화를 우선
    try:
        _subs = extract_all_subheadings(raw)
        for _t, _tag, _pos in _subs:
            if (re.search(r'\d+\s*[화권부]', _t)
                    or re.match(r'^[#＃]\s*\d+', _t)
                    or _CHAP_NUM_TITLE.match(_t)) and not _looks_like_body_sentence(_t) and not _is_single_numbered_list_text(_t):
                return _t
    except Exception:
        pass

    # ── center 정렬 + bold span 우선 처리 ─────────────────
    # e.g. <p style="text-align: center;"><span style="font-weight: bold;">5-8. 엘렌의 결투 대회</span><br/></p>
    # e.g. <p class="normal" style="text-align: center;"><b>후회남은 사절입니다<br />3권</b></p>
    for m in _CENTER_BOLD_PAT.finditer(raw):
        inner = m.group(1)
        # <br /> 태그를 공백으로 치환 후 나머지 태그 제거 (br로 나뉜 텍스트 합치기)
        inner_no_br = re.sub(r'<br\s*/?>', ' ', inner, flags=re.IGNORECASE)
        text  = re.sub(r'<[^>]+>', '', inner_no_br)   # 태그 전부 제거
        text  = re.sub(r'\s+', ' ', text).strip()
        text  = _normalize_title(text)
        text  = _safe_title(text)
        if _CHAP_NUM_TITLE.match(text) and 2 < len(text) < 80 and not _looks_like_body_sentence(text) and not _is_single_numbered_list_text(text):
            return text
        # 권/화 번호 포함 텍스트도 유효한 챕터 제목으로 처리
        if re.search(r'\d+\s*[권화부]', text) and 2 < len(text) < 80 and not _looks_like_body_sentence(text):
            return text
        # #N 형식 챕터 제목 (예: #101 전쟁의 결과)
        if re.match(r'^[#＃]\s*\d+', text) and 2 < len(text) < 80 and not _looks_like_body_sentence(text):
            return text

    # ── p/div 내부 b/strong 다중 헤딩 보정 ──────────────────
    # 한 파일에 "작품명 / Prologue / 1화..."가 함께 있는 경우
    # 첫 번째(작품명) 대신 화수 헤딩을 우선 선택한다.
    _bold_candidates = []
    for _m in re.finditer(
            r'<(?:p|div)[^>]*>\s*<(?:b|strong)[^>]*>(.*?)</(?:b|strong)>\s*(?:<br\s*/?>\s*)*</(?:p|div)>',
            raw, re.IGNORECASE | re.DOTALL):
        _t = re.sub(r'<br\s*/?>', ' ', _m.group(1), flags=re.IGNORECASE)
        _t = re.sub(r'<[^>]+>', '', _t)
        _t = _normalize_title(re.sub(r'\s+', ' ', _t).strip())
        _t = _safe_title(_t)
        if 1 < len(_t) < 80 and not _is_noise_heading_candidate(_t):
            _bold_candidates.append(_t)
    if len(_bold_candidates) >= 2:
        for _t in _bold_candidates:
            if (re.search(r'\d+\s*[화권부]', _t)
                    or re.match(r'^[#＃]\s*\d+', _t)
                    or _CHAP_NUM_TITLE.match(_t)) and not _looks_like_body_sentence(_t) and not _is_single_numbered_list_text(_t):
                return _t
        if not _looks_like_body_sentence(_bold_candidates[0]) and not _is_single_numbered_list_text(_bold_candidates[0]):
            return _bold_candidates[0]

    # ── 일반 패턴 ──────────────────────────────────────────
    for pat, grp in _TITLE_PATS:
        m = pat.search(raw)
        if m:
            g = m.group(grp)
            title = re.sub(r'<[^>]+>', '', g).strip()
            title = _normalize_title(title)
            title = _safe_title(title)
            if title.startswith('<') and title.endswith('>'):
                continue
            if (_is_noise_heading_candidate(title)):
                continue
            if 1 < len(title) < 80 and not _looks_like_body_sentence(title) and not _is_single_numbered_list_text(title):
                return title

    # ── fallback: 파일 전체가 짧은 제목인 경우 ────────────
    raw_no_style = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL|re.IGNORECASE)
    full_text = re.sub(r'<[^>]+>', '', raw_no_style)
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    full_text = _normalize_title(full_text)
    full_text = _safe_title(full_text)
    if 1 < len(full_text) < 60 and not _is_noise_heading_candidate(full_text) and not _is_single_numbered_list_text(full_text):
        return full_text

    return None


SUBNAV_HEAD_PAT = _SUBNAV_HEAD_PAT
is_subnav_heading_candidate = _is_subnav_heading_candidate




# Filename-based TOC title helpers moved from the legacy facade.
def _toc_label_from_filename(filename: str) -> str:
    """파일명에서 목차 상위노드용 라벨 생성.
    [작가명] 접두어는 유지, _작가__ 형식만 제거, 정상/수정 메타 제거, 언더스코어→공백.
    권/화/부 정보가 없으면 숫자에 접미어를 붙이지 않음.
    예) [유인] 외과의사 엘리제 4권.epub    → [유인] 외과의사 엘리제 4권
    예) [설아] 여장군과 대공의 계약 1.epub → [설아] 여장군과 대공의 계약 1
    예) _장스리__불건전_오피스__삽화본__1권.epub → 불건전 오피스 삽화본 1권
    예) _도희채__가이드를_함부로_줍지_마세요__정상_.epub → 가이드를 함부로 줍지 마세요
    예) 7.epub → 7  (권/화 정보 없으면 그대로)
    """
    name = _strip_filename_parse_noise(Path(filename).stem)
    # 언더스코어 → 공백
    name = name.replace('_', ' ')
    # [0034] 같은 순번 접두어는 제거, [작가명] 접두어는 유지
    name = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', name)
    if re.match(r'^\s*\[', name):
        # 앞에 [작가명] 괄호가 있는 경우: 끝부분 잡음 태그만 정리
        pass
    else:
        # _작가__ 형식 제거
        name = re.sub(r'^\s*\S{1,6}\s{2,}', '', name)
        # 중간에 있는 짧은 노이즈 괄호 [정상] [수정] 등 제거 (4글자 이하)
        name = re.sub(r'\s*\[[^\]]{1,4}\]\s*', ' ', name)
    # 끝부분 정상/수정/epub/txt 메타 태그 제거
    name = re.sub(r'\s+(정상|수정|epub|txt)\s*$', '', name, flags=re.IGNORECASE)
    # 끝 공백/마침표 정리
    name = re.sub(r'[\s.]+$', '', name)
    # 연속 공백 정리
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _toc_episode_no(s: str):
    """목차 문자열에서 선두/본문의 N화 번호를 정수로 추출."""
    if not s:
        return None
    t = _normalize_title(str(s))
    t = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', t)
    m = re.search(r'(?<!\d)(\d{1,5})\s*화', t)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _toc_subtitle_score(s: str) -> int:
    """화수 뒤 소제목 정보량. 별/특수문자 한 글자 제목도 정보로 인정한다."""
    if not s:
        return 0
    t = _normalize_title(str(s))
    t = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', t)
    m = re.search(r'(?<!\d)\d{1,5}\s*화', t)
    if m:
        t = t[m.end():]
    else:
        t = re.sub(r'^(?:(?<![가-힣])제)?\s*\d{1,5}\s*화\s*', '', t)
    t = re.sub(r'^[\s._·:：\-–—]+', '', t)
    t = re.sub(r'\s+', '', t)
    return len(t)


def _has_episode_subtitle(s: str) -> bool:
    """'N화' 뒤에 실제 소제목이 붙어있는지 판정."""
    if not s:
        return False
    t = _normalize_title(str(s))
    t = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', t)
    m = re.search(r'(?<!\d)(?:#\s*)?(?:제\s*)?\d{1,5}\s*화\b', t, re.IGNORECASE)
    if not m:
        return False
    tail = t[m.end():]
    tail = re.sub(r'^[\s._·:：\-–—~\)\]＞>]+', '', tail)
    tail = re.sub(r'\s+', '', tail)
    return bool(tail)


def _is_episode_only_label(s: str) -> bool:
    """라벨이 실질적으로 'N화'만 있는 generic 형태인지 판정."""
    if not s:
        return False
    t = _normalize_title(str(s))
    t = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', t)
    # 선두의 N화 마커 제거
    t = re.sub(r'^(?:#\s*)?(?:제\s*)?\d{1,5}\s*화', '', t, flags=re.IGNORECASE)
    # 구분자/공백만 남으면 episode-only
    t = re.sub(r'[\s._·:：,\-–—~!！?？\)\]\(＞><]+', '', t)
    return t == ''


def _is_reliable_filename_toc_label(label: str) -> bool:
    """파일명 기반 라벨을 목차 제목 소스로 신뢰할 수 있는지 판정."""
    if not label:
        return False
    t = _normalize_title(str(label)).strip()
    if not t or len(t) < 2:
        return False
    # 숫자/권호만 있는 라벨은 정보량이 낮아 신뢰도 낮음
    if re.match(r'^\d+\s*(?:권|화|부)?$', t):
        return False
    # 회차 정보가 있거나, 회차+소제목이면 신뢰
    if re.search(r'(?<!\d)\d{1,5}\s*화\b', t):
        return True
    if re.search(r'(?<!\d)\d{1,5}\s*[\.\)]\s*\S+', t):
        return True
    # 일반 텍스트 라벨도 최소 정보량이 있으면 허용
    return bool(re.search(r'[A-Za-z가-힣]', t))


def _is_structured_episode_filename_label(label: str) -> bool:
    """파일명이 'N화 + 구분자 + 소제목' 구조인지 판정."""
    if not label:
        return False
    t = _normalize_title(str(label)).strip()
    t = re.sub(r'^\s*\[\s*\d{1,5}\s*\]\s*', '', t)
    return bool(re.search(r'(?<!\d)\d{1,5}\s*화\s*[.\:：,，\-–—]\s*\S', t))


def _is_consistent_filename_label_set(labels: list[str]) -> bool:
    """전체 파일명 라벨이 정상 화수형인지(세트 일관성) 판정."""
    arr = [x for x in labels if x and str(x).strip()]
    if len(arr) < 5:
        return False
    structured = sum(1 for x in arr if _is_structured_episode_filename_label(x))
    episode_any = sum(1 for x in arr if _toc_episode_no(x) is not None)
    return structured >= max(3, int(len(arr) * 0.6)) and episode_any >= max(4, int(len(arr) * 0.75))


def _prefer_filename_toc_title(filename_label: str, extracted_title: str, force_filename: bool = False) -> str:
    """낱펍 목차는 파일명 화수/소제목이 내부 NCX보다 정확한 경우가 많다.

    - 내부 제목이 비어있거나 "34화"처럼 generic이면 파일명 라벨 사용
    - 내부 제목의 화수가 파일명과 다르면 파일명 라벨 사용
    - 같은 화수라도 파일명에 소제목이 더 있으면 파일명 라벨 사용
    """
    fl = _toc_label_from_filename(filename_label or '')
    et = _normalize_title(extracted_title or '').strip()
    if not fl:
        return et
    if force_filename and _is_reliable_filename_toc_label(fl):
        return fl
    fname_reliable = _is_reliable_filename_toc_label(fl)
    if not fname_reliable:
        return et or fl
    fn = _toc_episode_no(fl)
    # 정상 파일명 패턴: "N화. 소제목" / "N화: 소제목" / "N화, 소제목"
    _fn_structured = _is_structured_episode_filename_label(fl)
    if fn is None:
        return fl if not et or _is_generic_ncx_label(et) else et
    if not et:
        return fl
    en = _toc_episode_no(et)
    # 구조화된 파일명 + 화수 일치(또는 추출 제목 화수 없음)면 파일명 강제 우선
    if _fn_structured and (en is None or en == fn):
        return fl
    if en is not None and en != fn:
        return fl
    if en == fn:
        if _is_generic_ncx_label(et):
            return fl
        if _is_episode_only_label(et):
            return fl
        # 같은 화수 + 파일명만 소제목 보유 → 파일명 우선
        if _has_episode_subtitle(fl) and not _has_episode_subtitle(et):
            return fl
        # 같은 화수 + 파일명 소제목이 더 구체적(특수문자 제목 포함)하면 파일명 우선
        if _has_episode_subtitle(fl) and _toc_subtitle_score(fl) > _toc_subtitle_score(et):
            return fl
        if _toc_subtitle_score(fl) >= _toc_subtitle_score(et):
            return fl
    # 추출 제목에 화수가 없고 파일명엔 화수가 있으면 파일명 우선
    if en is None and fn is not None:
        return fl
    return et


def clean_chapter_display_title(title: str, series_title: str = "") -> str:
    """Normalize a chapter title for merged TOC display."""
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return ""
    text = re.sub(r"^#\s*(\d+)\s*[.)]?\s*$", r"\1화", text)
    text = re.sub(r"^(?:제\s*)?(\d+)\s*화\s*#\s*\1\s*[.)]?\s*", r"\1화 ", text)
    text = re.sub(r"^(?:제\s*)?(\d+)\s*화\b", r"\1화", text)
    text = re.sub(r"^#\s*(\d+)\s*[.)]?\s*", r"\1화 ", text)

    series = re.sub(r"\.epub$", "", str(series_title or ""), flags=re.IGNORECASE).strip()
    series = re.sub(r"^\[[^\]]+\]\s*", "", series).strip()
    series = re.sub(r"\s+\d+(?:[-~]\d+)?\s*(?:권|화|장|부)?(?:\+.*)?$", "", series).strip()
    if series and len(series) >= 3:
        text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
        text = re.sub(r"^" + re.escape(series) + r"\s*", "", text).strip()

    repeated = re.search(r"((?:제\s*)?\d+\s*(?:화|장|권|부)\b.*)$", text)
    if repeated and (text.startswith("[") or series and series in text[:repeated.start()]):
        text = repeated.group(1).strip()
    text = re.sub(r"^(\d+화)\s+\1\b", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def toc_duplicate_key(title: str) -> str:
    """Return a loose key for consecutive duplicate merged TOC labels."""
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    if not text:
        return ""
    text = re.sub(r"^#\s*", "", text)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text).strip()
    text = re.sub(r"[.。．]\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def merge_page_title_from_sources(
    raw_content,
    *,
    out_filename: str,
    ncx_labels: dict[str, str] | None = None,
    ncx_doc_title: str = "",
    series_title: str = "",
    override_title: str = "",
    has_override: bool = False,
) -> str:
    """Choose one merged page title from override, NCX, and XHTML content.

    This centralizes the title decision used by merge previews/workers so
    filename rename behavior and merged TOC behavior do not drift apart.
    """
    if isinstance(raw_content, bytes):
        raw_bytes = raw_content
    else:
        raw_bytes = str(raw_content or "").encode("utf-8", errors="replace")

    if has_override:
        page_title = str(override_title or "").strip()
    else:
        html_title = extract_chapter_title(raw_bytes) or ""
        page_title = ""
        labels = ncx_labels or {}
        if labels:
            ncx_label = str(labels.get(Path(out_filename).name.lower(), "") or "").strip()
            if ncx_label:
                if _is_generic_ncx_label(ncx_label):
                    if (
                        ncx_doc_title
                        and not _is_generic_ncx_label(ncx_doc_title)
                        and _is_chapterish_title(ncx_doc_title)
                    ):
                        page_title = ncx_doc_title
                    elif html_title:
                        page_title = html_title
                    elif _is_chapterish_title(ncx_label):
                        page_title = ncx_label
                    else:
                        page_title = ""
                elif not _is_chapterish_title(ncx_label) and html_title and _is_chapterish_title(html_title):
                    page_title = html_title
                else:
                    page_title = ncx_label
            else:
                # NCX exists, but this page is not registered. Leave it empty so
                # continuation pages do not become duplicate TOC entries.
                page_title = ""
        else:
            page_title = html_title

    if page_title:
        page_title = re.sub(r"\s*\(연재중?\)\s*", "", page_title).strip()
        page_title = clean_chapter_display_title(page_title, series_title)
    return page_title


toc_label_from_filename = _toc_label_from_filename
toc_episode_no = _toc_episode_no
toc_subtitle_score = _toc_subtitle_score
has_episode_subtitle = _has_episode_subtitle
is_episode_only_label = _is_episode_only_label
is_reliable_filename_toc_label = _is_reliable_filename_toc_label
is_structured_episode_filename_label = _is_structured_episode_filename_label
is_consistent_filename_label_set = _is_consistent_filename_label_set
prefer_filename_toc_title = _prefer_filename_toc_title
clean_merge_chapter_title = clean_chapter_display_title
merge_page_title = merge_page_title_from_sources

