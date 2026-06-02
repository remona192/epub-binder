from pathlib import Path
import sys
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.naver_series import (  # noqa: E402
    NaverSeriesCookies,
    choose_episode_cover,
    episode_number_from_row,
    extract_cover_urls,
    extract_detail_author,
    extract_og_title,
    extract_original_product_id,
    fetch_naver_series_cover,
    normalize_pstatic_image_url,
    parse_product_no,
)


def test_extract_author_from_detail_info_not_recommendations():
    html = (Path(__file__).parent / "fixtures" / "naver_4433040_detail.html").read_text(encoding="utf-8")

    assert extract_detail_author(html) == "신화진"
    assert extract_og_title(html) == "성스러운 아이돌"


def test_parse_product_no_accepts_plain_number_and_detail_urls():
    assert parse_product_no("13364647") == "13364647"
    assert (
        parse_product_no("https://series.naver.com/novel/detail.series?productNo=4433040")
        == "4433040"
    )
    assert (
        parse_product_no("https://series.naver.com/comic/detail.series?foo=1&productNo=98765")
        == "98765"
    )


def test_parse_product_no_rejects_missing_product_number():
    try:
        parse_product_no("https://series.naver.com/novel/detail.series?productId=123")
    except ValueError as exc:
        assert "productNo" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing productNo")


def test_choose_episode_cover_prefers_first_episode():
    covers = [
        {"title": "대표 표지", "url": "https://example.com/main.jpg"},
        {"title": "3화", "url": "https://example.com/3.jpg"},
        {"title": "1화", "url": "https://example.com/1.jpg"},
    ]

    assert choose_episode_cover(covers) == {"title": "1화", "url": "https://example.com/1.jpg"}


def test_extract_original_product_id_accepts_legacy_patterns():
    cases = {
        "originalProductId: 123": "123",
        'originalProductId = "234"': "234",
        '{"originalProductId": "345"}': "345",
        "{'originalProductId':456}": "456",
        '<div data-original-product-id="567"></div>': "567",
    }

    for html, expected in cases.items():
        assert extract_original_product_id(html) == expected


def test_normalize_pstatic_image_url_filters_and_cleans_candidates():
    url = r"https:\/\/image-comic.pstatic.net\/novel\/123\/thumbnail\/thumbnailbig.jpg?type=m600#fragment"

    assert (
        normalize_pstatic_image_url(url)
        == "https://image-comic.pstatic.net/novel/123/thumbnail/thumbnailbig.jpg"
    )
    assert (
        normalize_pstatic_image_url("http://image-comic.pstatic.net/novel/123/cover.png?quality=90#x")
        == "http://image-comic.pstatic.net/novel/123/cover.png?quality=90"
    )

    rejected = [
        "https://example.com/novel/123/cover.jpg",
        "//image-comic.pstatic.net/novel/123/cover.jpg",
        "https://image-comic.pstatic.net/static/cover.jpg",
        "https://image-comic.pstatic.net/novel/123/noimg.jpg",
        "https://image-comic.pstatic.net/novel/123/loading.gif",
        "https://image-comic.pstatic.net/novel/123/thumb/no/cover.jpg",
        "https://image-comic.pstatic.net/novel/123/thumb/19/cover.jpg",
        "https://image-comic.pstatic.net/gnb_/logo.png",
        "https://image-comic.pstatic.net/novel/123/cover.jpg?type=m101",
        "https://image-comic.pstatic.net/novel/123/cover.txt",
    ]
    for bad_url in rejected:
        assert normalize_pstatic_image_url(bad_url) is None


def test_extract_cover_urls_scores_preferred_and_large_pstatic_urls():
    html = r'''
        <meta property="og:image" content="https://image-comic.pstatic.net/static/noimg.jpg?type=m260">
        <img src="https://image-comic.pstatic.net/novel/555/thumbnail/small.jpg?type=m260">
        <img data-src="https://image-comic.pstatic.net/novel/555/11/thumbnail/thumbnail.jpg?type=m101">
        <img data-original="https://image-comic.pstatic.net/novel/123/thumbnail/thumbnailbig.jpg?type=m600">
        <img data-lazy="https://image-comic.pstatic.net/novel/777/thumbnail/cover.webp">
        <script>
            window.cover = "https:\/\/image-comic.pstatic.net\/novel\/999\/thumbnail\/thumbnailbig.jpg?type=m600";
        </script>
        <span data-original="https://image-comic.pstatic.net/novel/123/thumbnail/thumbnailbig.jpg?type=m260"></span>
    '''

    assert extract_cover_urls(html, preferred_ids=("123",)) == [
        "https://image-comic.pstatic.net/novel/123/thumbnail/thumbnailbig.jpg",
        "https://image-comic.pstatic.net/novel/999/thumbnail/thumbnailbig.jpg",
        "https://image-comic.pstatic.net/novel/555/thumbnail/small.jpg",
        "https://image-comic.pstatic.net/novel/777/thumbnail/cover.webp",
    ]


def test_cover_url_helpers_can_keep_legacy_low_priority_candidates():
    raw = "https://image-comic.pstatic.net/novel/123/cover.jpg?type=m101"

    assert normalize_pstatic_image_url(raw) is None
    assert (
        normalize_pstatic_image_url(raw, reject_type_m101=False)
        == "https://image-comic.pstatic.net/novel/123/cover.jpg"
    )
    assert extract_cover_urls(f'<img src="{raw}">', strict=False) == [
        "https://image-comic.pstatic.net/novel/123/cover.jpg"
    ]


def test_episode_number_from_row_mirrors_volume_list_priority():
    assert episode_number_from_row({"volumeNo": "2", "volumnNameText": "1화"}) == 2
    assert episode_number_from_row({"seriesNo": "", "volumeName": "제 12 화"}) == 12
    assert episode_number_from_row({"productName": "외전 3회"}) == 3
    assert episode_number_from_row({"productName": "공지"}) == 999999999


class FakeNaverSeriesClient:
    def __init__(self, *, detail_has_original_product_id=True, raise_403=False):
        self.detail_has_original_product_id = detail_has_original_product_id
        self.raise_403 = raise_403
        self.get_urls = []
        self.byte_urls = []

    def _get(self, url, cookies=None, referer=None):
        self.get_urls.append((url, dict(cookies or {}), referer))
        if self.raise_403:
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        if "/novel/detail.series" in url:
            return "<html><head></head><body>missing og title</body></html>"
        if "/comic/detail.series" in url:
            original = "originalProductId: 777" if self.detail_has_original_product_id else ""
            return f"""
                <html>
                    <head>
                        <meta property="og:title" content="테스트 만화 - 네이버 시리즈">
                        <meta property="og:image" content="https://image-comic.pstatic.net/comic/777/thumbnail/og.jpg">
                    </head>
                    <body>
                        <ul class="end_info"><li>글 <span><a>테스트 작가</a></span></li></ul>
                        <script>
                            {original}
                            var volumeListUrl = "/comic/volumeList.series?productNo=123&totalCount=2";
                        </script>
                    </body>
                </html>
            """
        if "/comic/volumeList.series" in url:
            return """
                {
                    "resultData": [
                        {
                            "productNo": "9002",
                            "volumeNo": 2,
                            "volumnNameText": "2화",
                            "detailPCPageUrlByNstoreKey": "/comic/volumeDetail.series?productNo=9002"
                        },
                        {
                            "productNo": "9001",
                            "volumeNo": 1,
                            "volumnNameText": "1화",
                            "detailPCPageUrlByNstoreKey": "/comic/volumeDetail.series?productNo=9001",
                            "upperOriginalProductId": "777"
                        }
                    ]
                }
            """
        if "/comic/volumeDetail.series?productNo=9001" in url:
            return """
                <html>
                    <body>
                        <img data-original="https://image-comic.pstatic.net/comic/777/9001/thumbnail/thumbnailbig.jpg?type=m600">
                    </body>
                </html>
            """
        raise AssertionError(f"unexpected GET URL: {url}")

    def _get_bytes(self, url, cookies=None, referer=None):
        self.byte_urls.append((url, dict(cookies or {}), referer))
        return b"\xff\xd8" + (b"x" * 25_000), "image/jpeg"


def test_fetch_naver_series_cover_uses_comic_detail_volume_json_episode_html_and_image_bytes():
    client = FakeNaverSeriesClient()
    messages = []

    result = fetch_naver_series_cover(
        "https://series.naver.com/comic/detail.series?productNo=123",
        NaverSeriesCookies(nid_aut="aut", nid_ses="ses"),
        client=client,
        progress=messages.append,
    )

    assert result.category == "comic"
    assert result.product_no == "123"
    assert result.original_product_id == "777"
    assert result.title == "테스트 만화"
    assert result.author == "테스트 작가"
    assert result.selected_episode == "1화"
    assert result.source_url == "https://image-comic.pstatic.net/comic/777/9001/thumbnail/thumbnailbig.jpg"
    assert result.cover_bytes.startswith(b"\xff\xd8")
    assert result.ext == "jpg"
    assert any("[1] detail 페이지 로드 중... (novel, productNo=123)" in msg for msg in messages)
    assert any("✓ 카테고리: comic" == msg for msg in messages)
    assert any("✓ originalProductId: 777" == msg for msg in messages)
    assert any("[3-A] 회차 목록에서 1화 표지 탐색..." == msg for msg in messages)
    assert any("1페이지: 2개 수집" in msg for msg in messages)
    assert any("→ 선택 회차: 1화 (productNo=9001)" in msg for msg in messages)
    assert any("1화 표지" in msg for msg in messages)
    assert client.byte_urls == [
        (
            "https://image-comic.pstatic.net/comic/777/9001/thumbnail/thumbnailbig.jpg",
            {"NID_AUT": "aut", "NID_SES": "ses"},
            "https://series.naver.com/comic/volumeDetail.series?productNo=9001",
        )
    ]


def test_fetch_naver_series_cover_reports_missing_original_product_id_but_keeps_fetching():
    client = FakeNaverSeriesClient(detail_has_original_product_id=False)
    messages = []

    result = fetch_naver_series_cover("123", {}, client=client, progress=messages.append)

    assert result.original_product_id is None
    assert result.category == "comic"
    assert "⚠ originalProductId 미발견 — CDN 시도 생략" in messages


def test_fetch_naver_series_cover_lets_http_403_propagate():
    client = FakeNaverSeriesClient(raise_403=True)

    try:
        fetch_naver_series_cover("123", {}, client=client)
    except urllib.error.HTTPError as exc:
        assert exc.code == 403
    else:
        raise AssertionError("expected HTTPError 403")
