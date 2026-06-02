from epub_binder_core import toc


def test_toc_label_from_filename_preserves_author_prefix_and_cleans_noise():
    assert toc.toc_label_from_filename("[유인] 외과의사 엘리제 4권.epub") == "[유인] 외과의사 엘리제 4권"
    assert toc.toc_label_from_filename("_도희채__가이드를_함부로_줍지_마세요__정상_.epub") == "가이드를 함부로 줍지 마세요"
    assert toc.toc_label_from_filename("7.epub") == "7"


def test_prefer_filename_toc_title_uses_more_reliable_filename_label():
    assert toc.prefer_filename_toc_title("34화. 작전 개시.xhtml", "34화") == "34화. 작전 개시"
    assert toc.prefer_filename_toc_title("35화. 귀환.xhtml", "34화") == "35화. 귀환"
    assert toc.prefer_filename_toc_title("권두부.xhtml", "프롤로그") == "프롤로그"
    assert toc.toc_episode_no("[0001] 12화. 시작") == 12


def test_consistent_filename_label_set_requires_structured_episode_majority():
    labels = [f"{i}화. 제목 {i}" for i in range(1, 6)]
    assert toc.is_consistent_filename_label_set(labels)
    assert not toc.is_consistent_filename_label_set(["1", "2", "3", "4", "5"])


def test_skip_page_detector_uses_legacy_copyright_cover_and_index_rules():
    copyright_html = "<html><body><p>지은이 : 작가</p><p>펴낸곳 : 출판사</p></body></html>"
    cover_html = '<html><body><img src="../Images/cover.jpg"/></body></html>'
    index_html = "<html><body><h1>목차</h1><p>1화 시작</p><p>2화 다음</p></body></html>"

    assert toc.is_skip_page("book_info.xhtml", copyright_html.encode("utf-8")) == "copyright"
    assert toc.is_skip_page("chapter_0.xhtml", cover_html.encode("utf-8")) == "cover"
    assert toc.is_skip_page("toc.xhtml", index_html.encode("utf-8")) == "index"


def test_chapter_title_and_subheading_anchor_helpers():
    paired = """
    <html><body>
      <p style="text-align: center;">1화</p>
      <p style="text-align: center;">종남의 사파 천하제일 검수</p>
    </body></html>
    """
    raw = """
    <html><body>
      <p><strong>2화. 복귀</strong></p>
    </body></html>
    """
    subheadings = toc.extract_all_subheadings(raw)
    anchored, anchor_map = toc.inject_subheading_anchors(raw, subheadings, id_prefix="chap")

    assert toc.extract_chapter_title(paired.encode("utf-8")) == "1화. 종남의 사파 천하제일 검수"
    assert toc.extract_chapter_title(raw.encode("utf-8")) == "2화. 복귀"
    assert subheadings == [("2화. 복귀", "<p><strong>2화. 복귀</strong></p>", raw.index("<p><strong>"))]
    assert anchor_map == [("chap_001", "2화. 복귀")]
    assert '<a id="chap_001"></a><p><strong>2화. 복귀</strong></p>' in anchored


def test_chapter_title_extracts_episode_marker_inside_span():
    raw = """
    <html><body>
      <p class="p00 center"><span class="fs12 kbb">248화</span></p>
      <p>&#160;</p>
      <p>본문</p>
    </body></html>
    """
    raw_with_nbsp_span = """
    <html><body>
      <p class="p00 center"><span class="fs12 kbb">262화</span><span>&#160;</span></p>
      <p>본문</p>
    </body></html>
    """

    assert toc.extract_chapter_title(raw.encode("utf-8")) == "248화"
    assert toc.extract_chapter_title(raw_with_nbsp_span.encode("utf-8")) == "262화"


def test_merge_page_title_from_sources_uses_shared_priority():
    raw = """
    <html><body>
      <p class="p00 center"><span class="fs12 kbb">248화</span></p>
      <p>본문</p>
    </body></html>
    """

    assert toc.merge_page_title_from_sources(
        raw,
        out_filename="Section0242.xhtml",
        ncx_labels={"section0242.xhtml": "Start"},
        ncx_doc_title="천하제일 당소예",
        series_title="천하제일 당소예 1-323",
    ) == "248화"
    assert toc.merge_page_title_from_sources(
        raw,
        out_filename="Section0242.xhtml",
        override_title="248화 직접 수정",
        has_override=True,
    ) == "248화 직접 수정"


def test_merge_page_title_prefers_html_over_numeric_id_ncx_label():
    raw = """
    <html><body>
      <p class="p00 center"><span class="fs12 kbb">248화</span></p>
      <p>본문</p>
    </body></html>
    """
    assert toc.merge_page_title_from_sources(
        raw,
        out_filename="Text/Section0242.xhtml",
        ncx_labels={"section0242.xhtml": "658204 248"},
        ncx_doc_title="천하제일 당소예",
        series_title="천하제일 당소예 1-323",
    ) == "248화"


def test_merge_page_title_uses_html_when_ncx_lists_only_cover():
    raw = """
    <html><body>
      <p class="p00 center"><span class="fs12 kbb">260화</span></p>
      <p>본문</p>
    </body></html>
    """
    assert toc.merge_page_title_from_sources(
        raw,
        out_filename="Text/Section0260.xhtml",
        ncx_labels={"coverpage.xhtml": "Start"},
        ncx_doc_title="천하제일 당소예",
        series_title="천하제일 당소예 1-323",
    ) == "260화"


def test_chapter_title_filters_plain_number_sentences_and_decimal_lines():
    plain = "<html><body><p>1. 원고의 청구를 기각한다.</p></body></html>"
    decimal = "<html><body><p>6.25 때의 난리는 난리도 아니다.</p></body></html>"
    author_volume = "<html><body><p>[백산] 너희들은 변호됐다 1권</p></body></html>"

    assert toc.extract_chapter_title(plain.encode("utf-8")) is None
    assert toc.extract_chapter_title(decimal.encode("utf-8")) is None
    assert toc.extract_chapter_title(author_volume.encode("utf-8")) is None


def test_chapter_title_keeps_short_numbered_subtitles():
    raw = "<html><body><p><b>8. 부부 싸움은 칼로 물 베기</b></p></body></html>"

    assert toc.extract_chapter_title(raw.encode("utf-8")) == "8. 부부 싸움은 칼로 물 베기"
    assert toc.is_subnav_heading_candidate("8. 부부 싸움은 칼로 물 베기")


def test_continuation_notice_helpers_remove_numbered_volume_notice():
    raw = "<html><body><h2>8. 부제</h2><p>-2권에 계속-</p><p>본문</p></body></html>"
    cleaned, removed = toc.remove_continued_notice_html(raw)

    assert removed == 1
    assert "2권에 계속" not in cleaned
    assert toc.extract_chapter_title("<html><body><p>-2권에 계속-</p></body></html>".encode("utf-8")) is None
    assert toc.merge_page_title_from_sources(
        "<html><body><p>-2권에 계속-</p></body></html>",
        out_filename="continued.xhtml",
    ) == ""


def test_chapter_title_ignores_quote_bullet_and_plain_numeric_bold():
    quote_bullet = '<html><body><p class="body"><b>≫ 최제호 진짜 신기한 사람……</b></p></body></html>'
    plain_numeric = '<html><body><p><b>1.</b></p></body></html>'
    assert toc.extract_chapter_title(quote_bullet.encode("utf-8")) is None
    assert toc.extract_chapter_title(plain_numeric.encode("utf-8")) is None


def test_subnav_heading_candidate_ignores_quote_bullet():
    assert not toc.is_subnav_heading_candidate("≫ 최제호 진짜 신기한 사람……")
