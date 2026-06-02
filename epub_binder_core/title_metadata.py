from __future__ import annotations

from pathlib import Path
import re

_CDATA_PAT = re.compile(r'<!\[CDATA\[(.*?)\]\]>', re.DOTALL)

def _read_dc_tag(opf_text: str, tag: str) -> str:
    """OPF에서 <dc:tag> 값 추출. CDATA 감싸기 대응."""
    m = re.search(f'<{tag}[^>]*>(.*?)</{tag}>', opf_text, re.IGNORECASE | re.DOTALL)
    if not m:
        return ''
    inner = m.group(1)
    cd = _CDATA_PAT.search(inner)
    return (cd.group(1) if cd else inner).strip()

_CR_AUTHOR_PATS = [
    re.compile(r'지은이\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'글쓴이\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'저\s*자\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'작\s*가\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
    re.compile(r'Author\s*[:：|｜]\s*([^\n<\|｜]{1,30})',  re.IGNORECASE),
]

_CR_AUTHOR_NOISE = re.compile(
    r'발행|출판|주소|전화|E-?mail|ISBN|http|\d{2,}[-\d]+', re.IGNORECASE)

def _extract_creator_from_html(raw_html: str) -> str:
    """HTML에서 판권 페이지의 작가명 추출.
    예) <p class="block_6">지은이 : 얼음커피</p>  →  '얼음커피'
    ※ 블록 경계(</p>, </div>, <br>)를 줄바꿈으로 치환해 각 단락을 독립적으로 검사한다.
       그렇지 않으면 `지은이｜진설우</p><p>편집부｜유서영` 같이 인접 단락이 한 줄로 합쳐져
       `진설우 편집부` 처럼 과잉 매칭되는 버그가 생긴다.
    """
    import html as _hm
    # 블록/개행 태그를 실제 개행으로 변환
    tmp = re.sub(r'<\s*br\s*/?\s*>', '\n', raw_html, flags=re.IGNORECASE)
    tmp = re.sub(r'</\s*(?:p|div|li|h[1-6]|tr|td|th)\s*>', '\n', tmp, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', tmp)
    text = _hm.unescape(text)
    # 개행은 보존, 다른 공백만 축약
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    # 1차: 라인 단위 라벨 기반 파싱 (지은이｜진설우 / Author: Name)
    _label_pat = re.compile(
        r'(?:\uC9C0\uC740\uC774|\uAE00\uC4F4\uC774|\uC800\uC790|\uC791\uAC00|\uC6D0\uC791|author)'
        r'\s*[:\|\uFF1A\uFF5C\uFFE8]\s*([^\n\r\|\uFF5C:：]{1,30})',
        re.IGNORECASE)
    _copy_pat = re.compile(
        r'[©\u24D2]\s*([A-Za-z\uAC00-\uD7A3][A-Za-z\uAC00-\uD7A30-9.\s\u00B7]{1,24})\s*,?\s*\d{4}',
        re.IGNORECASE)
    for ln in text.split('\n'):
        line = re.sub(r'\s+', ' ', ln).strip()
        if not line:
            continue
        for pat in (_label_pat, _copy_pat):
            m = pat.search(line)
            if not m:
                continue
            name = m.group(1).strip().rstrip('.,;:|｜')
            if _CR_AUTHOR_NOISE.search(name):
                continue
            if 1 < len(name) <= 20 and re.search(r'[A-Za-z\uAC00-\uD7A3]', name):
                return name
    for pat in _CR_AUTHOR_PATS:
        m = pat.search(text)
        if m:
            name = m.group(1).strip().rstrip('.,;')
            if _CR_AUTHOR_NOISE.search(name):
                continue
            if 1 < len(name) <= 20:
                return name
    return ''

_CR_TITLE_HTML_PATS = [
    # <p class="font6"><span class="t-num2">제목</span></p>
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*font6[^"\']*["\'][^>]*>\s*'
        r'<span\b[^>]+class=["\'][^"\']*t-num2[^"\']*["\'][^>]*>(.*?)</span>',
        re.IGNORECASE | re.DOTALL),
    # <p class="block_4">제목</p>  (block_4 = 판권 페이지 대제목)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*block_4[^"\']*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <p class="titleE">제목<br/></p>  (하이스토리 등 판권 페이지 제목)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*titleE[^"\']*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <p class="title*">제목</p>  (title / title1 / titleA 등 일반형)
    re.compile(
        r'<p\b[^>]+class=["\'][^"\']*\btitle[A-Za-z0-9_\-]*["\'][^>]*>(.*?)</p>',
        re.IGNORECASE | re.DOTALL),
    # <h1/h2>제목</h1> 판권 페이지 상단 큰 제목
    re.compile(
        r'<h[1-3]\b[^>]*>(.*?)</h[1-3]>',
        re.IGNORECASE | re.DOTALL),
]

_CR_TITLE_NOISE = re.compile(
    r'발행|출판|지은이|저자|ISBN|http|E-?mail|주소|전화|무단|저작권'
    r'|\d{3,}|All\s+Rights',
    re.IGNORECASE)

def _extract_title_from_html(raw_html: str) -> str:
    """HTML 판권 페이지에서 책 제목 추출.
    예) <p class="block_4">탈옥한 천재마법사</p>  →  '탈옥한 천재마법사'
        <p class="font6"><span class="t-num2">환생자는 편하게 살고 싶다</span></p>
    """
    for pat in _CR_TITLE_HTML_PATS:
        for m in pat.finditer(raw_html):
            inner = re.sub(r'<br\s*/?>', ' ', m.group(1), flags=re.IGNORECASE)
            text  = re.sub(r'<[^>]+>', '', inner).strip()
            import html as _hm2
            text  = _hm2.unescape(text)
            text  = re.sub(r'\s+', ' ', text).strip()
            # 잡음(발행처·주소 등) 포함이거나 화수 패턴이면 스킵
            if _CR_TITLE_NOISE.search(text):
                continue
            if re.search(r'^\d+\s*[화권편]|^[#＃]\s*\d+', text):
                continue
            if 2 < len(text) < 60 and re.search(r'[가-힣]{2,}', text):
                return text
    return ''

def _normalize_title(s: str) -> str:
    """제목 문자열 후처리 (ridi_rename normalize_text 참고)
    NFKC 정규화, 제로폭 공백 제거, HTML 엔티티 디코딩, 연속 공백 정리
    ※ 전각 물음표 ？(U+FF1F)는 NFKC 변환 전 보호 (Windows 파일명 허용 문자)
    """
    import unicodedata, html as _html
    s = _html.unescape(s)
    s = _strip_filename_parse_noise(s)
    # 전각기호 보호: NFKC가 전각→반각으로 변환하면 _safe_title(_FORBIDDEN)이 제거하므로 임시 치환
    # Windows 금지문자(\ / : * ? " < > |)에 대응하는 전각 버전을 모두 보호
    _FW_MAP = [
        ('？', '\x00FW_QM\x00'),   # U+FF1F → ?
        ('：', '\x00FW_CL\x00'),   # U+FF1A → :
        ('＂', '\x00FW_DQ\x00'),   # U+FF02 → "
        ('｜', '\x00FW_PI\x00'),   # U+FF5C → |
        ('＊', '\x00FW_AS\x00'),   # U+FF0A → *
        ('＜', '\x00FW_LT\x00'),   # U+FF1C → <
        ('＞', '\x00FW_GT\x00'),   # U+FF1E → >
        ('／', '\x00FW_SL\x00'),   # U+FF0F → /
        ('＼', '\x00FW_BS\x00'),   # U+FF3C → \
    ]
    for _ch, _tok in _FW_MAP:
        s = s.replace(_ch, _tok)
    s = unicodedata.normalize('NFKC', s)
    for _ch, _tok in _FW_MAP:
        s = s.replace(_tok, _ch)
    for zw in ('​','‌','‍','⁠','﻿'):
        s = s.replace(zw, '')
    s = s.replace('_', ' ')   # OPF 제목 내 언더스코어 → 공백
    s = re.sub(r'[\s ]+', ' ', s).strip()
    return s

_FORBIDDEN = re.compile(r'[\\/:*?"<>|]')



def _safe_title(value: str) -> str:
    return _FORBIDDEN.sub(' ', str(value or '')).strip()

def _strip_filename_parse_noise(s: str) -> str:
    """파일명/제목 파싱 전에 변형 문자와 보이지 않는 문자를 제거한다.

    ᵘ 같은 modifier/superscript 문자는 NFKC 전에 제거해야 일반 문자(u)로
    치환되지 않고 완전히 사라진다.
    """
    import unicodedata
    if not s:
        return ''
    s = unicodedata.normalize('NFC', s)
    out = []
    for ch in s:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if cat == 'Cf':
            continue
        if cp in (0xFE0E, 0xFE0F):   # variation selectors
            continue
        if 0x02B0 <= cp <= 0x02FF:   # Spacing Modifier Letters
            continue
        if 0x1D2C <= cp <= 0x1D7F:   # phonetic/superscript modifier letters (ᵘ 포함)
            continue
        if 0x2070 <= cp <= 0x209F:   # superscripts and subscripts
            continue
        out.append(ch)
    return ''.join(out)

_CHAPTERISH_PAT = re.compile(
    r'(?:(?<![가-힣])제?\s*\d+\s*[화장권부식]|[#＃]\s*\d+|프롤로그|에필로그|(?:외전|번외|특전)\s*\d+\s*화)',
    re.IGNORECASE)

def _is_chapterish_title(s: str) -> bool:
    """제목이 챕터/화수 성격이면 True."""
    if not s:
        return False
    return bool(_CHAPTERISH_PAT.search(_normalize_title(s)))

def _is_series_volume_heading(s: str) -> bool:
    """'케이 18권'처럼 시리즈명+권수만 있는 권 제목인지 판정."""
    if not s:
        return False
    t = _normalize_title(s)
    t = re.sub(r'\s*\(연재중?\)\s*', '', t).strip()
    if re.search(r'(?:제\s*)?\d+\s*[화장편회식]|[#＃]\s*\d+|프롤로그|에필로그|서장|종장', t):
        return False
    return bool(re.match(r'^[가-힣A-Za-z][가-힣A-Za-z0-9 ._\-:：]{0,45}\s+\d{1,4}\s*권$', t))

def _series_volume_label_from_heading(s: str) -> str:
    """권 제목 후보를 '제목 N권' 라벨로 정규화."""
    t = _normalize_title(s or '')
    t = re.sub(r'\s*\(연재중?\)\s*', '', t).strip()
    m = re.search(r'(\d{1,4})\s*권\s*$', t)
    if not m:
        return t
    vol = f"{int(m.group(1))}권"
    title = re.sub(r'\s*\d{1,4}\s*권\s*$', '', t).strip()
    title = _safe_title(title)
    return f"{title} {vol}".strip() if title else vol

def _extract_series_volume_heading_from_html(raw_html: str) -> str:
    """본문 HTML에서 실제 권 제목(h1~h6/title 계열)을 추출."""
    import html as _html
    candidates: list[str] = []
    for pat in (
            r'<h[1-6][^>]*>(.*?)</h[1-6]>',
            r'<p[^>]*\bclass=["\'][^"\']*[Tt]itle[^"\']*["\'][^>]*>(.*?)</p>',
            r'<h[1-6][^>]+\btitle=["\']([^"\']+)["\']'):
        for m in re.finditer(pat, raw_html, re.IGNORECASE | re.DOTALL):
            raw = m.group(1)
            raw = re.sub(r'<br\s*/?>', ' ', raw, flags=re.IGNORECASE)
            raw = re.sub(r'<[^>]+>', '', raw)
            raw = _html.unescape(raw)
            raw = re.sub(r'\s+', ' ', raw).strip()
            if raw:
                candidates.append(raw)
    for cand in candidates:
        if _is_series_volume_heading(cand):
            return _series_volume_label_from_heading(cand)
    return ''

def _find_series_volume_heading_in_zip(zf, opf_raw: str, opf_dir: str, max_files: int = 5) -> str:
    """OPF spine 앞쪽에서 '제목 N권' 형태의 실제 권 제목을 찾는다."""
    try:
        manifest: dict[str, str] = {}
        for mm in re.finditer(r'<item\s([^>]*?)/?>', opf_raw, re.IGNORECASE):
            mid = re.search(r'\bid=["\']([^"\']+)["\']', mm.group(1))
            mh = re.search(r'\bhref=["\']([^"\']+)["\']', mm.group(1))
            if mid and mh:
                manifest[mid.group(1)] = mh.group(1)
        spine_ids = re.findall(r'<itemref\s[^>]*idref=["\']([^"\']+)["\']', opf_raw)
        for sid in spine_ids[:max_files]:
            href = manifest.get(sid, '')
            if not href:
                continue
            full = (opf_dir + '/' + href).lstrip('./') if opf_dir != '.' else href
            if full not in zf.namelist():
                full = href
            if full not in zf.namelist():
                continue
            heading = _extract_series_volume_heading_from_html(
                zf.read(full).decode('utf-8', 'replace'))
            if heading:
                return heading
    except Exception:
        pass
    return ''

def _clean_opf_series_title(raw: str, *,
                            strip_genre_tag: bool = False,
                            strip_interview: bool = False,
                            preserve_complete_paren: bool = False,
                            protect_edition_paren: bool = False) -> str:
    """OPF/판권에서 얻은 제목 문자열을 시리즈명 기준으로 정제."""
    t = _normalize_title(raw)
    if strip_genre_tag:
        t = re.sub(r'^\s*\[[A-Za-z가-힣0-9]{1,6}\]\s*', '', t)
    t = re.sub(r'^(?:(?<![가-힣])제)?\s*\d+\s*화\s*[._]?\s*', '', t)
    t = re.sub(r'^[#＃]\s*\d+\s*', '', t)
    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화]\s*', ' ', t)
    t = re.sub(r'(\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*부)(?!\s*[-–—―]|\s+[가-힣])', ' ', t)
    t = re.sub(r'\s+[-–—]?\s*([A-Za-z가-힣]*(?:외전\d*|번외\d*|특전\d*)|단행본|합본)\s*$', '', t)
    if strip_interview:
        t = re.sub(r'\s+(?:인터뷰집|인터뷰|작가노트)\s*$', '', t)
    _wk = ''
    if preserve_complete_paren:
        _wk_m = re.search(r'[\(（]\s*완결\s*[\)）]', t)
        _wk = (' ' + _wk_m.group(0).strip()) if _wk_m else ''
    if protect_edition_paren:
        _ED_KW = r'(?:19세\s*)?(?:개정증보판|증보판|개정판|완전판|외전증보판)'
        def _protect_edition(m):
            return '__EDSTART__' + m.group(0).strip('([（【)】）]').strip() + '__EDEND__'
        t = re.sub(r'[\(\[（【][^\)\]）】]*(?:' + _ED_KW + r')[^\)\]）】]*[\)\]）】]', _protect_edition, t)
        t = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*', ' ', t)
        t = re.sub(r'__EDSTART__([^_]*)__EDEND__', r'(\1)', t)
    else:
        t = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*', ' ', t)
    t = re.sub(r'\s+\d+/\d+\s*$', '', t)
    t = re.sub(r'\s+\d+\s*$', '', t)
    t = re.sub(r'^[\s.\-·]+|[\s.\-·]+$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if _wk:
        t = (t + _wk).strip()
    return t

def _series_from_parent_dir(path: str) -> str:
    """numeric-id 파일의 시리즈명 폴백: 부모 폴더명에서 제목만 추출."""
    try:
        parent = Path(path).resolve().parent.name
    except Exception:
        parent = Path(path).parent.name
    if not parent:
        return ''
    s = _normalize_title(parent)
    s = re.sub(r'[_\s-]\d{9,}$', '', s).strip()        # ..._1776657938080
    s = re.sub(r'\s+\d+\s*[-~]\s*\d+\s*$', '', s).strip()  # ... 1-444
    s = re.sub(r'\s*(?:완결|完)\s*$', '', s).strip()
    s = re.sub(r'\s*[\[\(（【].*?[\]\)）】]\s*$', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip(' _-')
    return s

def _strip_trailing_volume_suffix(title: str) -> str:
    """문자열 끝의 권/화/부 표기를 제거해 시리즈명만 남긴다."""
    t = _normalize_title(title or '')
    t = re.sub(r'\s*(?:(?<![가-힣])제)?\s*(?:\d+[-~]\d+|\d+)\s*[권화부]\s*$', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

_GENERIC_NCX_SET = {
    '시작', '본문', '내용', '내용 시작', '무제',
    '책의 시작', '표지', '목차', '차례',
    'start', 'begin', 'content', 'section', 'chapter', 'untitled',
}

_GENERIC_NCX_PAT = re.compile(
    r'^chapter\s*\d*$'              # Chapter N
    r'|^제?\s*\d+\s*화\s*[_.\-]?$'  # 1화_ / 제1화. / 1화
    r'|^제?\s*\d+\s*권\s*[_.\-]?$'  # 1권_ / 제1권
    r'|^\d+\s*[화권부]\s*$'          # 숫자+단위만
    r'|^\d+\s*[.)]\s*$'             # 1. / 2)
    r'|^\d+\s*$'                    # 1 / 2
    r'|^[#＃]\s*\d+\s*$',           # #101 단독
    re.IGNORECASE)

def _is_generic_ncx_label(label: str) -> bool:
    """NCX 라벨이 의미없는 generic 값이면 True (대소문자 무관)."""
    if not label:
        return False
    lo = label.strip().lower()
    return lo in _GENERIC_NCX_SET or bool(_GENERIC_NCX_PAT.match(lo))


read_dc_tag = _read_dc_tag
extract_creator_from_html = _extract_creator_from_html
extract_title_from_html = _extract_title_from_html
normalize_title = _normalize_title
strip_filename_parse_noise = _strip_filename_parse_noise
is_chapterish_title = _is_chapterish_title
is_series_volume_heading = _is_series_volume_heading
series_volume_label_from_heading = _series_volume_label_from_heading
extract_series_volume_heading_from_html = _extract_series_volume_heading_from_html
find_series_volume_heading_in_zip = _find_series_volume_heading_in_zip
clean_opf_series_title = _clean_opf_series_title
series_from_parent_dir = _series_from_parent_dir
strip_trailing_volume_suffix = _strip_trailing_volume_suffix
is_generic_ncx_label = _is_generic_ncx_label
safe_title = _safe_title


def _guess_tail_volume_unit_from_zip(zf, tail_num: int, numeric_id_hint: bool = False) -> str:
    """EPUB 본문을 보고 tail number의 단위를 권/화로 추정."""
    from epub_binder_core.toc import extract_chapter_title
    unit = '권'
    if not numeric_id_hint:
        try:
            for ncx_name in zf.namelist():
                if not ncx_name.lower().endswith('.ncx'):
                    continue
                ncx_raw = zf.read(ncx_name).decode('utf-8', 'replace')
                nav_labels = re.findall(
                    r'<navLabel[^>]*>\s*<text[^>]*>(.*?)</text>',
                    ncx_raw, re.DOTALL | re.IGNORECASE)
                chap_navs = 0
                for nav in nav_labels:
                    nt = re.sub(r'<[^>]+>', '', nav)
                    nt = _normalize_title(nt)
                    if re.search(r'\d+\s*[화장편회]', nt):
                        chap_navs += 1
                        if chap_navs >= 2:
                            return '권'
        except Exception:
            pass
    chapterish_pages = 0
    saw_serial_hint = False
    saw_tail_hwa = False
    for xn in zf.namelist():
        if not xn.lower().endswith(('.xhtml', '.html', '.htm')):
            continue
        xb = zf.read(xn)
        xc = xb.decode('utf-8', 'replace')
        plain = re.sub(r'<[^>]+>', '', xc)
        if re.search(r'연재', plain):
            saw_serial_hint = True
        if re.search(rf'{tail_num}\s*화', plain):
            saw_tail_hwa = True
        if not numeric_id_hint:
            try:
                xh_any = extract_chapter_title(xb)
            except Exception:
                xh_any = ''
            if xh_any and (re.search(r'\d+\s*[화장편회]', xh_any)
                           or re.search(r'프롤로그|에필로그|서장|종장', xh_any)):
                chapterish_pages += 1
                if chapterish_pages >= 2:
                    return '권'
        if numeric_id_hint:
            xh = extract_chapter_title(xb)
            if xh and (re.search(r'\d+\s*화', xh)
                       or re.match(r'^[#＃]\s*\d+', xh)
                       or re.search(r'프롤로그|에필로그', xh)):
                return '화'
    if saw_serial_hint or saw_tail_hwa:
        return '화'
    return unit

guess_tail_volume_unit_from_zip = _guess_tail_volume_unit_from_zip

__all__ = [
    'read_dc_tag',
    'extract_creator_from_html',
    'extract_title_from_html',
    'normalize_title',
    'strip_filename_parse_noise',
    'is_chapterish_title',
    'is_series_volume_heading',
    'series_volume_label_from_heading',
    'extract_series_volume_heading_from_html',
    'find_series_volume_heading_in_zip',
    'clean_opf_series_title',
    'series_from_parent_dir',
    'strip_trailing_volume_suffix',
    'is_generic_ncx_label',
    'safe_title',
    'guess_tail_volume_unit_from_zip',
]
