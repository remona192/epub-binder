from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


_TAG_RE = re.compile(r"<[^>]+>")
_PRODUCT_RE = re.compile(r"productNo=(\d+)")
_ORIGINAL_PRODUCT_PATTERNS = (
    re.compile(r'["\']originalProductId["\']\s*[:=]\s*["\']?(\d+)["\']?', re.IGNORECASE),
    re.compile(r"\boriginalProductId\b\s*[:=]\s*['\"]?(\d+)['\"]?", re.IGNORECASE),
    re.compile(r"\bdata-original-product-id\s*=\s*['\"]?(\d+)['\"]?", re.IGNORECASE),
)
_COVER_ATTRS = ("src", "data-src", "data-original", "data-lazy")
_RAW_PSTATIC_URL_RE = re.compile(
    r"https?://(?:[A-Za-z0-9.-]+\.)?pstatic\.net/[^\s\"'<>\\)\]]+",
    re.IGNORECASE,
)
_IMAGE_SUFFIX_RE = re.compile(r"\.(?:jpe?g|png|webp|gif)$", re.IGNORECASE)
_REJECTED_PSTATIC_RE = re.compile(
    r"favicon|/static/|placeholder|noimg|loading|thumb/no|thumb/19|gnb_",
    re.IGNORECASE,
)
_MISSING_EPISODE_NUMBER = 999999999


@dataclass(frozen=True)
class NaverCoverResult:
    cover_bytes: bytes
    ext: str
    title: str
    author: str
    source_url: str
    selected_episode: str


@dataclass(frozen=True)
class NaverSeriesCookies:
    nid_aut: str = ""
    nid_ses: str = ""

    def as_dict(self) -> dict[str, str]:
        cookies: dict[str, str] = {}
        if self.nid_aut:
            cookies["NID_AUT"] = self.nid_aut
        if self.nid_ses:
            cookies["NID_SES"] = self.nid_ses
        return cookies


@dataclass(frozen=True)
class NaverSeriesFetchResult:
    cover_bytes: bytes
    ext: str
    title: str
    author: str
    source_url: str
    selected_episode: str
    product_no: str
    category: str
    detail_url: str
    original_product_id: str | None = None
    ssl_fallback_used: bool = False

    def as_cover_result(self) -> NaverCoverResult:
        return NaverCoverResult(
            cover_bytes=self.cover_bytes,
            ext=self.ext,
            title=self.title,
            author=self.author,
            source_url=self.source_url,
            selected_episode=self.selected_episode,
        )


def clean_html_text(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub("", value)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_product_no(value: str) -> str:
    text = (value or "").strip()
    if text.isdigit():
        return text
    match = _PRODUCT_RE.search(text)
    if match:
        return match.group(1)
    raise ValueError("productNo를 찾을 수 없습니다.")


def extract_og_title(html: str) -> str:
    patterns = [
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html or "", re.IGNORECASE)
        if match:
            title = clean_html_text(match.group(1))
            return re.sub(r"\s*-\s*네이버\s*시리즈\s*$", "", title).strip()
    return ""


def extract_detail_author(html: str) -> str:
    """Extract the author from the work detail area, not recommendation cards."""
    if not html:
        return ""

    detail_chunks = []
    for pattern in (
        r'<[^>]+class=["\'][^"\']*end_info[^"\']*["\'][^>]*>(?P<body>.*?)</(?:div|ul)>',
        r'<[^>]+id=["\'][^"\']*endInfo[^"\']*["\'][^>]*>(?P<body>.*?)</(?:div|ul)>',
        r'<[^>]+class=["\'][^"\']*detail_info[^"\']*["\'][^>]*>(?P<body>.*?)</(?:div|ul)>',
    ):
        detail_chunks.extend(match.group("body") for match in re.finditer(pattern, html, re.IGNORECASE | re.DOTALL))

    if not detail_chunks:
        # Limit fallback to the upper detail page and intentionally exclude
        # recommendation/top-list sections where unrelated authors often appear.
        stop = re.search(r'(?:class=["\'][^"\']*(?:recommend|ranking|top|lst_thum)[^"\']*["\']|id=["\'][^"\']*(?:recommend|ranking|top)[^"\']*["\'])', html, re.IGNORECASE)
        detail_chunks = [html[: stop.start()] if stop else html[:8000]]

    label_patterns = [
        r"(?:글|저자|작가)\s*</?\w*[^>]*>\s*(?:[:：])?\s*<[^>]+>([^<]+)</",
        r"(?:글|저자|작가)\s*[:：]\s*([^<\n\r|]+)",
        r"<dt[^>]*>\s*(?:글|저자|작가)\s*</dt>\s*<dd[^>]*>(.*?)</dd>",
        r"<span[^>]*>\s*(?:글|저자|작가)\s*</span>\s*<span[^>]*>(.*?)</span>",
    ]
    for chunk in detail_chunks:
        for pattern in label_patterns:
            match = re.search(pattern, chunk, re.IGNORECASE | re.DOTALL)
            if match:
                author = clean_html_text(match.group(1))
                if author:
                    return author
    return ""


def extract_original_product_id(html: str) -> str:
    text = html or ""
    for pattern in _ORIGINAL_PRODUCT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    raise ValueError("originalProductId를 찾을 수 없습니다.")


def normalize_pstatic_image_url(
    url: str | None,
    *,
    reject_placeholders: bool = True,
    reject_type_m101: bool = True,
) -> str | None:
    text = unescape(str(url or ""))
    text = text.replace("\\/", "/")
    text = re.sub(r"\\u002[fF]", "/", text)
    text = text.strip().strip("\"'")
    text = text.rstrip(" \t\r\n\"',;)")
    if not text.startswith(("http://", "https://")):
        return None

    parsed = urllib.parse.urlsplit(text)
    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    host = (parsed.hostname or "").lower()
    if host != "pstatic.net" and not host.endswith(".pstatic.net"):
        return None

    lower_url = text.lower()
    lower_query = parsed.query.lower()
    if reject_placeholders and _REJECTED_PSTATIC_RE.search(lower_url):
        return None
    if reject_type_m101 and re.search(r"(?:^|&)type=m101(?:&|$)", lower_query):
        return None

    if not _IMAGE_SUFFIX_RE.search(urllib.parse.unquote(parsed.path)):
        return None

    query = parsed.query
    if re.search(r"(?:^|&)type=", query, re.IGNORECASE):
        query = ""
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


class _CoverUrlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._collect(tag, attrs)

    def _collect(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {}
        for name, value in attrs:
            if value:
                attr_map[name.lower()] = value
        if tag.lower() == "meta":
            meta_name = (attr_map.get("property") or attr_map.get("name") or "").lower()
            content = attr_map.get("content")
            if meta_name == "og:image" and content:
                self.urls.append(("og:image", content))

        for attr_name in _COVER_ATTRS:
            value = attr_map.get(attr_name)
            if value:
                self.urls.append((attr_name, value))


def _raw_cover_urls(html: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    parser = _CoverUrlParser()
    try:
        parser.feed(html or "")
        urls.extend(parser.urls)
    except Exception:
        pass

    scan_text = unescape(html or "").replace("\\/", "/")
    scan_text = re.sub(r"\\u002[fF]", "/", scan_text)
    urls.extend(("raw", match.group(0)) for match in _RAW_PSTATIC_URL_RE.finditer(scan_text))
    return urls


def _cover_url_score(url: str, raw_url: str, source: str, preferred_ids: tuple[str, ...]) -> int:
    lower = f"{raw_url} {url}".lower()
    score = 0
    if any(pid in raw_url or pid in url for pid in preferred_ids):
        score -= 120
    if "comicthumb" in lower:
        score -= 40
    if "thumbnailbig" in lower:
        score -= 35
    elif re.search(r"(?:^|[?&])type=m(?:260|300|400|500|600|690)(?:&|$)", lower):
        score -= 25
    elif "thumbnail" in lower:
        score -= 10
    if source == "og:image":
        score -= 1
    if _REJECTED_PSTATIC_RE.search(lower):
        score += 500
    if re.search(r"(?:^|[?&])type=m101(?:&|$)", lower):
        score += 60
    return score


def extract_cover_urls(html: str, preferred_ids=(), *, strict: bool = True) -> list[str]:
    preferred = tuple(str(value) for value in preferred_ids if value)
    candidates: dict[str, tuple[int, int, str]] = {}

    for index, (source, raw_url) in enumerate(_raw_cover_urls(html)):
        url = normalize_pstatic_image_url(
            raw_url,
            reject_placeholders=strict,
            reject_type_m101=strict,
        )
        if not url:
            continue
        score = _cover_url_score(url, raw_url, source, preferred)
        current = candidates.get(url)
        if current is None or (score, index) < (current[0], current[1]):
            candidates[url] = (score, index, url)

    return [url for _, _, url in sorted(candidates.values(), key=lambda item: (item[0], item[1]))]


def episode_number_from_row(row: Mapping[str, object] | None) -> int:
    if not row:
        return _MISSING_EPISODE_NUMBER

    for key in ("volumeNo", "seriesNo"):
        try:
            number = int(row.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number

    text_parts = []
    for key in ("volumnNameText", "volumeName", "subProductName", "productName", "expansionProductName"):
        value = row.get(key)
        if value:
            text_parts.append(str(value))
    text = " / ".join(text_parts)

    for pattern in (r"(?:제\s*)?(\d+)\s*화", r"\b(\d+)\s*회\b"):
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return _MISSING_EPISODE_NUMBER


def extract_episode_covers(html: str) -> list[dict[str, str]]:
    covers: list[dict[str, str]] = []
    for match in re.finditer(r"<img\b[^>]+>", html or "", re.IGNORECASE):
        tag = match.group(0)
        src_match = re.search(r'(?:src|data-src)=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if not src_match:
            continue
        alt_match = re.search(r'alt=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        covers.append(
            {
                "title": clean_html_text(alt_match.group(1) if alt_match else ""),
                "url": unescape(src_match.group(1)),
            }
        )
    return covers


def choose_episode_cover(covers: list[dict[str, str]]) -> dict[str, str] | None:
    if not covers:
        return None

    def score(item: dict[str, str]) -> tuple[int, int]:
        title = item.get("title", "")
        if re.search(r"(?:^|\D)(?:제\s*)?1\s*화(?:\D|$)", title):
            return (0, 1)
        num_match = re.search(r"(?:제\s*)?(\d+)\s*화", title)
        if num_match:
            return (1, int(num_match.group(1)))
        return (2, 999999)

    return sorted(covers, key=score)[0]


def is_ssl_verification_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ssl.SSLCertVerificationError):
        return True
    text = f"{reason} {exc}"
    return "CERTIFICATE_VERIFY_FAILED" in text or "certificate verify failed" in text.lower()


def _cookies_to_dict(cookies: NaverSeriesCookies | Mapping[str, str] | None) -> dict[str, str]:
    if cookies is None:
        return {}
    if isinstance(cookies, NaverSeriesCookies):
        return cookies.as_dict()
    return {str(key): str(value) for key, value in cookies.items() if value}


def _emit(progress: Callable[[str], object] | None, message: str) -> None:
    if progress:
        progress(message)


def _decode_response(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _client_get_text(
    client: object,
    url: str,
    cookies: Mapping[str, str],
    *,
    referer: str | None = None,
) -> str:
    getter = getattr(client, "_get")
    try:
        value = getter(url, cookies=cookies, referer=referer)
    except TypeError:
        try:
            value = getter(url, cookies)
        except TypeError:
            value = getter(url)
    return _decode_response(value)


def _client_get_json(
    client: object,
    url: str,
    cookies: Mapping[str, str],
    *,
    referer: str | None = None,
) -> object:
    return json.loads(_client_get_text(client, url, cookies, referer=referer))


def _client_get_bytes(
    client: object,
    url: str,
    cookies: Mapping[str, str],
    *,
    referer: str | None = None,
) -> tuple[bytes, str]:
    getter = getattr(client, "_get_bytes", None)
    if getter is not None:
        try:
            value = getter(url, cookies=cookies, referer=referer)
        except TypeError:
            try:
                value = getter(url, cookies)
            except TypeError:
                value = getter(url)
    else:
        value = getattr(client, "_get")(url, cookies)

    if isinstance(value, tuple):
        data = value[0]
        content_type = value[1] if len(value) > 1 else "image/jpeg"
    else:
        data = value
        content_type = "image/jpeg"
    if isinstance(data, str):
        data = data.encode("utf-8")
    return bytes(data), str(content_type or "image/jpeg")


def _ext_from_url_and_content_type(url: str, content_type: str) -> str:
    ext = "jpg"
    ctype = (content_type or "").lower()
    if "png" in ctype:
        ext = "png"
    elif "webp" in ctype:
        ext = "webp"
    elif "gif" in ctype:
        ext = "gif"
    path = urllib.parse.urlsplit(url).path.lower()
    for suffix, normalized in (
        (".png", "png"),
        (".webp", "webp"),
        (".gif", "gif"),
        (".jpeg", "jpg"),
        (".jpg", "jpg"),
    ):
        if path.endswith(suffix):
            return normalized
    return ext


def _abs_series_url(url: str) -> str:
    return urllib.parse.urljoin("https://series.naver.com/", unescape(str(url)))


def _with_query_param(url: str, key: str, value: object) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True) if k != key]
    query.append((key, str(value)))
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), parsed.fragment)
    )


def _volume_list_url(detail_html: str, category: str, product_no: str) -> str:
    for pattern in (
        r"sVolumeListUrl\s*:\s*['\"]([^'\"]+)",
        r"volumeListUrl\s*[:=]\s*['\"]([^'\"]+)",
    ):
        match = re.search(pattern, detail_html or "")
        if match:
            return _with_query_param(_abs_series_url(match.group(1)), "sortOrder", "ASC")

    total = "9999"
    match = re.search(r"totalCount\s*[:=]\s*['\"]?(\d+)", detail_html or "")
    if match:
        total = match.group(1)
    base_url = (
        f"https://series.naver.com/{category}/volumeList.series?"
        + urllib.parse.urlencode({"productNo": product_no, "totalCount": total})
    )
    return _with_query_param(base_url, "sortOrder", "ASC")


def _volume_rows(volume_obj: object) -> list[dict[str, object]]:
    data = volume_obj.get("resultData", []) if isinstance(volume_obj, dict) else []
    rows: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            continue
        key = str(row.get("productNo") or row.get("seriesNo") or row.get("volumeNo") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        rows.append(row)
    return rows


def _row_detail_url(row: Mapping[str, object], category: str) -> str | None:
    for key in ("detailPCPageUrlByNstoreKey", "detailPageUrlByNstoreKey"):
        value = row.get(key)
        if value:
            return _abs_series_url(str(value))
    product_no = row.get("productNo")
    if product_no:
        return f"https://series.naver.com/{category}/volumeDetail.series?productNo={product_no}"
    return None


def _row_episode_label(row: Mapping[str, object], episode_no: int) -> str:
    for key in ("volumnNameText", "volumeName", "subProductName", "productName", "expansionProductName"):
        value = row.get(key)
        if value:
            return str(value)
    if episode_no < _MISSING_EPISODE_NUMBER:
        return f"{episode_no}화"
    return "선택 회차"


def _scan_episode_thumbnailbig_urls(html: str) -> list[str]:
    return [
        url
        for url in (
            normalize_pstatic_image_url(
                match.group(0),
                reject_placeholders=False,
                reject_type_m101=False,
            )
            for match in re.finditer(
                r"https://[^\s\"'<>\\\]]+\.pstatic\.net/[^\s\"'<>\\\]]+/\d+/\d+/thumbnail/thumbnailbig\.[a-z]+",
                html or "",
                re.IGNORECASE,
            )
        )
        if url
    ]


def _scan_series_thumbnailbig_urls(html: str) -> list[str]:
    return [
        url
        for url in (
            normalize_pstatic_image_url(
                match.group(0),
                reject_placeholders=False,
                reject_type_m101=False,
            )
            for match in re.finditer(
                r"https://[^\s\"'<>\\\]]+\.pstatic\.net/[^\s\"'<>\\\]]+/\d+/thumbnail/thumbnailbig\.[a-z]+",
                html or "",
                re.IGNORECASE,
            )
        )
        if url
    ]


def _try_download_candidates(
    client: object,
    candidates: list[str],
    label: str,
    cookies: Mapping[str, str],
    *,
    progress: Callable[[str], object] | None = None,
    referer: str | None = None,
    min_bytes: int = 20_000,
) -> tuple[str | None, bytes | None, str | None]:
    for candidate in candidates:
        try:
            data, content_type = _client_get_bytes(client, candidate, cookies, referer=referer)
        except urllib.error.HTTPError:
            raise
        except Exception as exc:
            _emit(progress, f"  ⚠ 다운로드 실패: {exc}")
            continue
        if not str(content_type).lower().startswith("image/"):
            _emit(progress, f"  ⚠ 이미지가 아님: {candidate}")
            continue
        if len(data) < min_bytes:
            _emit(progress, f"  ⚠ 너무 작은 이미지 제외: {len(data) // 1024:,} KB")
            continue
        _emit(progress, f"  ✓ {label}: {len(data) // 1024:,} KB")
        return candidate, data, content_type
    return None, None, None


class NaverSeriesClient:
    def __init__(self) -> None:
        self.context = ssl.create_default_context()
        self.unverified_context: ssl.SSLContext | None = None
        self.ssl_fallback_used = False

    def _urlopen_with_ssl_fallback(self, request: urllib.request.Request, timeout: int):
        try:
            return urllib.request.urlopen(request, timeout=timeout, context=self.context)
        except urllib.error.URLError as exc:
            if not is_ssl_verification_error(exc):
                raise
            self.ssl_fallback_used = True
            if self.unverified_context is None:
                self.unverified_context = ssl._create_unverified_context()
            return urllib.request.urlopen(request, timeout=timeout, context=self.unverified_context)

    def _get(
        self,
        url: str,
        cookies: dict[str, str] | None = None,
        referer: str | None = None,
    ) -> bytes:
        cookie_header = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items() if v)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer or "https://series.naver.com/",
        }
        if cookie_header:
            headers["Cookie"] = cookie_header
        request = urllib.request.Request(url, headers=headers)
        with self._urlopen_with_ssl_fallback(request, timeout=20) as response:
            return response.read()

    def _get_bytes(
        self,
        url: str,
        cookies: dict[str, str] | None = None,
        referer: str | None = None,
    ) -> tuple[bytes, str]:
        cookie_header = "; ".join(f"{k}={v}" for k, v in (cookies or {}).items() if v)
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": referer or "https://series.naver.com/",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        }
        if cookie_header:
            headers["Cookie"] = cookie_header
        request = urllib.request.Request(url, headers=headers)
        with self._urlopen_with_ssl_fallback(request, timeout=20) as response:
            return response.read(), response.headers.get("Content-Type", "image/jpeg")

    def fetch_detail_html(self, product_no_or_url: str, cookies: dict[str, str] | None = None) -> tuple[str, str]:
        product_no = parse_product_no(product_no_or_url)
        url = f"https://series.naver.com/novel/detail.series?productNo={product_no}"
        return product_no, self._get(url, cookies).decode("utf-8", errors="ignore")

    def fetch_cover(self, product_no_or_url: str, cookies: dict[str, str] | None = None) -> NaverCoverResult:
        return fetch_naver_series_cover(product_no_or_url, cookies, client=self).as_cover_result()


def fetch_naver_series_cover(
    product_no_or_url: str,
    cookies: NaverSeriesCookies | Mapping[str, str] | None,
    *,
    client: object | None = None,
    progress: Callable[[str], object] | None = None,
) -> NaverSeriesFetchResult:
    client = client or NaverSeriesClient()
    cookie_dict = _cookies_to_dict(cookies)
    product_no = parse_product_no(product_no_or_url)

    detail_html: str | None = None
    category: str | None = None
    detail_url: str | None = None
    for candidate_category in ("novel", "comic"):
        candidate_url = f"https://series.naver.com/{candidate_category}/detail.series?productNo={product_no}"
        _emit(progress, f"[1] detail 페이지 로드 중... ({candidate_category}, productNo={product_no})")
        try:
            candidate_html = _client_get_text(client, candidate_url, cookie_dict)
        except urllib.error.HTTPError:
            raise
        except Exception:
            continue
        if re.search(r'<meta[^>]+property=["\']og:title["\']', candidate_html or "", re.IGNORECASE):
            detail_html = candidate_html
            category = candidate_category
            detail_url = candidate_url
            _emit(progress, f"✓ 카테고리: {candidate_category}")
            break

    if not detail_html or not category or not detail_url:
        raise ValueError(
            f"productNo={product_no} 에 해당하는 작품을 찾지 못했습니다.\n"
            "URL/productNo가 올바른지 확인해주세요."
        )

    original_product_id: str | None = None
    try:
        original_product_id = extract_original_product_id(detail_html)
    except ValueError:
        original_product_id = None

    if original_product_id:
        _emit(progress, f"✓ originalProductId: {original_product_id}")
    else:
        _emit(progress, "⚠ originalProductId 미발견 — CDN 시도 생략")

    image_url: str | None = None
    image_data: bytes | None = None
    image_content_type: str | None = None
    selected_episode = ""

    _emit(progress, "[3-A] 회차 목록에서 1화 표지 탐색...")
    try:
        list_url = _with_query_param(_volume_list_url(detail_html, category, product_no), "page", 1)
        volume_obj = _client_get_json(client, list_url, cookie_dict, referer=detail_url)
        rows = _volume_rows(volume_obj)
        if not rows:
            _emit(progress, "  ⚠ 회차 목록이 비어 있습니다.")
        else:
            _emit(progress, f"  ✓ 1페이지: {len(rows)}개 수집")
            _emit(progress, f"✓ 총 {len(rows)}개 회차 발견")
            target = min(
                rows,
                key=lambda row: (
                    episode_number_from_row(row),
                    int(row.get("productNo") or 0) if str(row.get("productNo") or "").isdigit() else 0,
                ),
            )
            episode_no = episode_number_from_row(target)
            selected_episode = _row_episode_label(target, episode_no)
            episode_detail_url = _row_detail_url(target, category)
            _emit(progress, f"  → 선택 회차: {selected_episode} (productNo={target.get('productNo', '')})")
            if episode_detail_url:
                episode_html = _client_get_text(client, episode_detail_url, cookie_dict, referer=detail_url)
                preferred_ids = (
                    target.get("upperOriginalProductId"),
                    original_product_id,
                    target.get("originalProductId"),
                    target.get("productNo"),
                )
                image_url, image_data, image_content_type = _try_download_candidates(
                    client,
                    extract_cover_urls(episode_html, preferred_ids, strict=False),
                    f"{selected_episode} 표지",
                    cookie_dict,
                    progress=progress,
                    referer=episode_detail_url,
                    min_bytes=20_000,
                )
            else:
                _emit(progress, "  ⚠ 선택 회차 상세 URL을 찾지 못했습니다.")
    except urllib.error.HTTPError:
        raise
    except Exception as exc:
        _emit(progress, f"  ⚠ volumeList 실패: {exc}")

    if not image_url:
        _emit(progress, "[3-B] 작품 상세 페이지 원본 표지 탐색...")
        image_url, image_data, image_content_type = _try_download_candidates(
            client,
            extract_cover_urls(detail_html, (original_product_id,), strict=False),
            "상세 페이지 표지",
            cookie_dict,
            progress=progress,
            referer=detail_url,
            min_bytes=20_000,
        )

    if not image_url:
        _emit(progress, "[3-C] thumbnailbig 패턴으로 폴백 탐색...")
        image_url, image_data, image_content_type = _try_download_candidates(
            client,
            _scan_episode_thumbnailbig_urls(detail_html),
            "에피소드 표지(detail)",
            cookie_dict,
            progress=progress,
            referer=detail_url,
            min_bytes=20_000,
        )
        if not image_url:
            image_url, image_data, image_content_type = _try_download_candidates(
                client,
                _scan_series_thumbnailbig_urls(detail_html),
                "시리즈 표지(detail)",
                cookie_dict,
                progress=progress,
                referer=detail_url,
                min_bytes=8_000,
            )

    if not image_url and original_product_id:
        _emit(progress, "[3-D] CDN URL 패턴으로 시도 중...")
        cdn_candidates = [
            f"https://image-comic.pstatic.net/series/{original_product_id}/thumbnail/thumbnailbig.jpg",
            f"https://image-comic.pstatic.net/{category}/{original_product_id}/thumbnail/thumbnailbig.jpg",
            f"https://image-comic.pstatic.net/series/{original_product_id}/thumbnail/thumbnail.jpg",
        ]
        for cdn_url in cdn_candidates:
            _emit(progress, f"  → {cdn_url}")
            try:
                data, content_type = _client_get_bytes(client, cdn_url, cookie_dict, referer=detail_url)
                if len(data) > 8_000:
                    image_url = cdn_url
                    image_data = data
                    image_content_type = content_type
                    _emit(progress, f"  ✓ {len(data) // 1024:,} KB")
                    break
            except urllib.error.HTTPError:
                raise
            except Exception:
                continue

    if not image_url:
        for pattern in (
            r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            r'property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        ):
            match = re.search(pattern, detail_html, re.IGNORECASE)
            if not match:
                continue
            og_url = normalize_pstatic_image_url(
                match.group(1),
                reject_placeholders=False,
                reject_type_m101=False,
            )
            if og_url:
                image_url, image_data, image_content_type = _try_download_candidates(
                    client,
                    [og_url],
                    "og:image",
                    cookie_dict,
                    progress=progress,
                    referer=detail_url,
                    min_bytes=8_000,
                )
            if image_url:
                _emit(progress, f"⚠ og:image 사용: {image_url}")
            break

    if not image_url:
        raise ValueError("표지 이미지 URL을 찾지 못했습니다.")

    if image_data is None:
        _emit(progress, "[4] 이미지 다운로드 중...")
        image_data, image_content_type = _client_get_bytes(client, image_url, cookie_dict, referer=detail_url)

    title = extract_og_title(detail_html)
    author = extract_detail_author(detail_html)
    ext = _ext_from_url_and_content_type(image_url, image_content_type or "image/jpeg")
    return NaverSeriesFetchResult(
        cover_bytes=image_data,
        ext=ext,
        title=title,
        author=author,
        source_url=image_url,
        selected_episode=selected_episode,
        product_no=product_no,
        category=category,
        detail_url=detail_url,
        original_product_id=original_product_id,
        ssl_fallback_used=bool(getattr(client, "ssl_fallback_used", False)),
    )


def dumps_cover_debug(result: NaverCoverResult) -> str:
    return json.dumps(
        {
            "title": result.title,
            "author": result.author,
            "selected_episode": result.selected_episode,
            "source_url": result.source_url,
            "size_kb": round(len(result.cover_bytes) / 1024, 1),
            "ext": result.ext,
        },
        ensure_ascii=False,
    )
