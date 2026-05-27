from epub_binder_core.merge_plan import (
    cover_asset_basenames,
    decide_merge_page_skip,
    page_has_image_and_short_text,
    plan_unreferenced_image_prune,
    referenced_image_basenames,
)
import epub_binder_core.merge_plan as merge_plan
from epub_binder_core.epub_io import ManifestItem
import pytest


IMAGE_ONLY_PAGE = b"""
<html>
  <head><style>body { color: red; } .hidden { content: "long ignored text"; }</style></head>
  <body><img src="../Images/cover.jpg" alt="cover"> </body>
</html>
"""


def test_detector_cover_kept_for_later_volume_when_volume_covers_enabled():
    result = decide_merge_page_skip(
        "Text/cover.xhtml",
        IMAGE_ONLY_PAGE,
        book_index=1,
        keep_vol_covers=True,
        flat_toc=False,
        skip_page_detector=lambda _href, _content: "cover",
    )

    assert result is None


def test_ncx_cover_image_only_page_is_detected():
    assert (
        decide_merge_page_skip(
            "Text/content-0001.xhtml",
            IMAGE_ONLY_PAGE,
            ncx_label="cover",
        )
        == "cover"
    )


def test_flat_toc_ncx_index_labels_are_detected():
    assert (
        decide_merge_page_skip(
            "Text/nav.xhtml",
            b"<html><body><p>chapter list</p></body></html>",
            ncx_label="\ubaa9\ucc28",
            flat_toc=True,
        )
        == "index"
    )
    assert (
        decide_merge_page_skip(
            "Text/nav.xhtml",
            b"<html><body><p>1</p></body></html>",
            ncx_label="Contents",
            flat_toc=True,
        )
        == "index"
    )


def test_book_title_page_is_index_in_flat_toc():
    assert (
        decide_merge_page_skip(
            "Text/book_title.xhtml",
            b"<html><body><h1>Volume 2</h1></body></html>",
            flat_toc=True,
        )
        == "index"
    )


def test_second_volume_first_two_image_only_pages_are_covers():
    assert (
        decide_merge_page_skip(
            "Text/section0002.xhtml",
            IMAGE_ONLY_PAGE,
            book_index=1,
            spine_position=2,
        )
        == "cover"
    )
    assert (
        decide_merge_page_skip(
            "Text/section0003.xhtml",
            IMAGE_ONLY_PAGE,
            book_index=1,
            spine_position=3,
        )
        is None
    )


def test_cover_asset_basenames_url_decodes_and_strips_query_fragment():
    html = """
    <html><body>
      <img src="../Images/My%20Cover.JPG?width=900#frag">
      <img src="subdir/%ED%91%9C%EC%A7%80.png?x=1">
    </body></html>
    """

    assert cover_asset_basenames(html) == frozenset({"my cover.jpg", "\ud45c\uc9c0.png"})


def test_referenced_image_basenames_reads_markup_and_css_refs():
    markup = r"""
    <html>
      <head><link href="..\Styles\book.css"></head>
      <body>
        <img src="../Images/My%20Cover.JPG?width=900#frag">
        <image href="..\Images\Plate%2001.PNG#svg">
        <style>.hero { background-image: url('../Images/Bg%20One.WEBP?cache=1#top'); }</style>
      </body>
    </html>
    """

    assert referenced_image_basenames(markup) == frozenset(
        {"my cover.jpg", "plate 01.png", "bg one.webp"}
    )


def test_plan_unreferenced_image_prune_keeps_cover_and_non_images():
    manifest = (
        ManifestItem("cover-image", "Images/Cover.JPG", "image/jpeg"),
        ManifestItem("used", "Images/Used.PNG", "image/png"),
        ManifestItem("unused", "Images/Unused.GIF", "image/gif"),
        ManifestItem("chapter", "Text/chapter.xhtml", "application/xhtml+xml"),
        ManifestItem("style", "Styles/book.css", "text/css"),
    )

    plan = plan_unreferenced_image_prune(manifest, frozenset({"used.png"}))

    assert plan.remove_manifest_ids == frozenset({"unused"})
    assert plan.protected_basenames == frozenset({"cover.jpg"})
    assert plan.removable_file_basenames == frozenset({"unused.gif"})


def test_page_has_image_and_short_text_ignores_style_and_tags():
    assert page_has_image_and_short_text(IMAGE_ONLY_PAGE)
    assert not page_has_image_and_short_text(
        b"<html><body><img src='cover.jpg'><p>" + (b"long " * 30) + b"</p></body></html>"
    )


def test_render_merge_opf_matches_legacy_shape_with_cover_and_escaped_metadata():
    manifest = {
        "cover-image": ("OEBPS/Images/cover.jpg", "image/jpeg"),
        "Text/chap:1": ("OEBPS/Text/1/chapter.xhtml", "application/xhtml+xml"),
        "img space#2": ("OEBPS/Images/plate.png", "image/png"),
    }

    opf = merge_plan.render_merge_opf(
        "AT&T <Novel> 1-3권",
        "urn:uuid:test-merge-id",
        manifest,
        ["Text/chap:1"],
        creator="A&B <C>",
        publisher="Pub <House> & Co",
        language="ko-KR",
    )

    assert opf.startswith('<?xml version="1.0" encoding="utf-8"?>\n<package ')
    assert '<package unique-identifier="uuid_id" version="2.0"' in opf
    assert 'xmlns="http://www.idpf.org/2007/opf">' in opf
    assert "<dc:title>AT&amp;T &lt;Novel&gt; 1-3권</dc:title>" in opf
    assert "<dc:creator>A&amp;B &lt;C&gt;</dc:creator>" in opf
    assert "<dc:publisher>Pub &lt;House&gt; &amp; Co</dc:publisher>" in opf
    assert "<dc:language>ko-KR</dc:language>" in opf
    assert '<dc:identifier id="uuid_id">urn:uuid:test-merge-id</dc:identifier>' in opf
    assert '<meta name="cover" content="cover-image"/>' in opf
    assert '<meta name="calibre:series" content="AT&amp;T &lt;Novel&gt;"/>' in opf
    assert '<meta name="calibre:series_index" content="1"/>' in opf
    assert opf.index('id="ncx" href="toc.ncx"') < opf.index('id="cover-image"')
    assert (
        '<item id="Text_chap_1" href="OEBPS/Text/1/chapter.xhtml" '
        'media-type="application/xhtml+xml"/>'
    ) in opf
    assert (
        '<item id="img_space_2" href="OEBPS/Images/plate.png" '
        'media-type="image/png"/>'
    ) in opf
    assert '<itemref idref="Text_chap_1"/>' in opf
    assert '<reference type="cover" title="Cover" href="OEBPS/Text/cover.xhtml"/>' in opf


def test_render_merge_opf_accepts_manifest_items_and_omits_cover_blocks_without_cover_image():
    manifest = (
        ManifestItem("chapter.1", "OEBPS/Text/1/chapter.xhtml", "application/xhtml+xml"),
        ManifestItem("style main", "OEBPS/Styles/main.css", "text/css"),
    )

    opf = merge_plan.render_merge_opf(
        "다 해먹는 슈퍼스타 12화",
        "urn:uuid:no-cover",
        manifest,
        ["chapter.1"],
    )

    assert '<dc:title>다 해먹는 슈퍼스타 12화</dc:title>' in opf
    assert "<dc:creator>" not in opf
    assert "<dc:publisher>" not in opf
    assert "<dc:language>ko</dc:language>" in opf
    assert '<meta name="cover" content="cover-image"/>' not in opf
    assert "<guide>" not in opf
    assert '<meta name="calibre:series" content="다 해먹는 슈퍼스타"/>' in opf
    assert opf.index('id="ncx" href="toc.ncx"') < opf.index('id="chapter_1"')
    assert (
        '<item id="chapter_1" href="OEBPS/Text/1/chapter.xhtml" '
        'media-type="application/xhtml+xml"/>'
    ) in opf
    assert '<item id="style_main" href="OEBPS/Styles/main.css" media-type="text/css"/>' in opf
    assert '<itemref idref="chapter_1"/>' in opf


def test_render_merge_opf_strips_legacy_series_suffixes_for_calibre_metadata():
    cases = {
        "초심돌 12권": "초심돌",
        "다 해먹는 슈퍼스타 12화": "다 해먹는 슈퍼스타",
        "장편 판타지 1-3권": "장편 판타지",
        "장편 판타지 4-10화": "장편 판타지",
        "장편 판타지 1-2부": "장편 판타지",
    }

    for title, series in cases.items():
        opf = merge_plan.render_merge_opf(title, "urn:uuid:series", {}, [])

        assert f'<meta name="calibre:series" content="{series}"/>' in opf
        assert '<meta name="calibre:series_index" content="1"/>' in opf


def test_infer_creator_prefers_bracketed_title_author():
    assert (
        merge_plan.infer_creator_from_title_or_filename("[작가] 작품 1권", "_다른작가__작품")
        == "작가"
    )


def test_infer_creator_uses_legacy_filename_prefix_fallback():
    assert merge_plan.infer_creator_from_title_or_filename("작품 1권", "_작가__작품") == "작가"


def test_infer_creator_returns_empty_without_legacy_patterns():
    assert merge_plan.infer_creator_from_title_or_filename("작품 1권", "plain-title") == ""


def test_plan_volume_chapter_toc_groups_volume_chapter_filenames():
    plan = merge_plan.plan_volume_chapter_toc(
        (
            (0, "작품 1권 1화", "Text/0.xhtml"),
            (1, "작품 1권 2화", "Text/1.xhtml"),
            (2, "작가 후기", "Text/2.xhtml"),
        ),
        ("작품 1권 1화.epub", "작품 1권 2화.epub", "작가 후기.epub"),
        filename_toc_labels={0: "작품 1권 1화", 1: "작품 1권 2화", 2: "작가 후기"},
        flat_toc=False,
        force_filename_toc=True,
    )

    assert plan.groups == {
        1: (
            (0, "작품 1권 1화", "Text/0.xhtml", 1),
            (1, "작품 1권 2화", "Text/1.xhtml", 2),
        )
    }
    assert plan.ungrouped == ((2, "작가 후기", "Text/2.xhtml"),)
    assert plan.filename_chapter_numbers == {0: 1, 1: 2}
    assert plan.filename_volume_numbers == {0: 1, 1: 1}
    assert plan.chapter_only_filename_numbers == {0: 1, 1: 2}
    assert plan.filename_toc_labels[2] == "작가 후기"
    assert plan.force_filename_toc is True
    assert plan.use_grouping is True
    assert plan.use_flat is False


def test_plan_volume_chapter_toc_flat_mode_and_label_helpers():
    plan = merge_plan.plan_volume_chapter_toc(
        ((0, "작품 1권", "Text/0.xhtml"),),
        ("작품 1권 3화.epub",),
        flat_toc=True,
    )

    assert plan.use_grouping is False
    assert plan.use_flat is True
    assert merge_plan.volume_parent_label(1, "작품 1권 3화") == "작품 1권"
    assert merge_plan.volume_parent_label(2, "외전") == "외전 2권"
    assert merge_plan.flat_volume_chapter_label("작품 1권", 3) == "작품 1권 3화"
    assert merge_plan.flat_volume_chapter_label("작품 1권 3화", 3) == "작품 1권 3화"


def test_should_use_multi_volume_ncx_for_multi_page_volume_labels():
    assert merge_plan.should_use_multi_volume_ncx(
        (
            (0, "작품 1권", "Text/v1.xhtml"),
            (1, "작품 2권", "Text/v2.xhtml"),
        ),
        (0, 0, 1, 1),
        flat_toc=False,
        volume_chapter_grouping=False,
    ) is True


def test_should_use_multi_volume_ncx_false_for_all_single_page_serial():
    assert merge_plan.should_use_multi_volume_ncx(
        (
            (0, "작품 1권", "Text/v1.xhtml"),
            (1, "작품 2권", "Text/v2.xhtml"),
        ),
        (0, 1),
        flat_toc=False,
        volume_chapter_grouping=False,
    ) is False


@pytest.mark.parametrize(
    ("toc_entries", "flat_toc", "volume_chapter_grouping"),
    [
        (((0, "작품 1권", "a.xhtml"), (1, "작품 2권", "b.xhtml")), True, False),
        (((0, "작품 1권", "a.xhtml"), (1, "작품 2권", "b.xhtml")), False, True),
        (((0, "빙하기 86화", "a.xhtml"), (1, "빙하기 87화", "b.xhtml")), False, False),
    ],
)
def test_should_use_multi_volume_ncx_respects_legacy_gates(
    toc_entries,
    flat_toc,
    volume_chapter_grouping,
):
    assert merge_plan.should_use_multi_volume_ncx(
        toc_entries,
        (0, 0, 1, 1),
        flat_toc=flat_toc,
        volume_chapter_grouping=volume_chapter_grouping,
    ) is False


def test_has_multi_volume_label_marker_preserves_legacy_special_volume_order():
    assert merge_plan.has_multi_volume_label_marker("외전 1화") is True
    assert merge_plan.has_multi_volume_label_marker("왕의 귀환 1") is True
    assert merge_plan.has_multi_volume_label_marker("빙하기 86화") is False


def test_build_volume_chapter_ncx_entries_preserves_legacy_order_and_counters():
    result = merge_plan.build_volume_chapter_ncx_entries(
        ((9, "작가 후기", "Text/after.xhtml"),),
        {
            2: ((2, "작품 2권 1화", "Text/v2c1.xhtml", 1),),
            1: (
                (1, "작품 1권 2화", "Text/v1c2.xhtml", 2),
                (0, "작품 1권 1화", "Text/v1c1.xhtml", 1),
            ),
        },
        start_play_order=7,
        start_book_index=3,
    )

    assert result.next_play_order == 13
    assert result.next_book_index == 9

    afterword, volume_1, volume_2 = result.entries
    assert afterword == merge_plan.NcxNavEntry(
        "book004",
        "작가 후기",
        "Text/after.xhtml",
        7,
    )
    assert volume_1.nav_id == "book005"
    assert volume_1.label == "작품 1권"
    assert volume_1.src == "Text/v1c1.xhtml"
    assert volume_1.play_order == 8
    assert volume_1.children == (
        merge_plan.NcxNavEntry("book006", "1화", "Text/v1c1.xhtml", 9),
        merge_plan.NcxNavEntry("book007", "2화", "Text/v1c2.xhtml", 10),
    )
    assert volume_2.nav_id == "book008"
    assert volume_2.label == "작품 2권"
    assert volume_2.children == (
        merge_plan.NcxNavEntry("book009", "1화", "Text/v2c1.xhtml", 12),
    )


def test_build_multi_volume_ncx_entry_preserves_parent_child_ids_and_counters():
    result = merge_plan.build_multi_volume_ncx_entry(
        "작품 1권",
        "Text/v1.xhtml",
        (
            ("item-1", "Text/v1.xhtml", ""),
            ("item-2", "Text/chapter2.xhtml", "2화"),
            ("item-3", "Text/chapter3.xhtml", "3화"),
        ),
        book_index=4,
        start_play_order=9,
    )

    assert result.next_play_order == 12
    assert result.next_book_index == 4
    assert result.entries == (
        merge_plan.NcxNavEntry(
            "book004",
            "작품 1권",
            "Text/v1.xhtml",
            9,
            (
                merge_plan.NcxNavEntry("book004_item-2", "2화", "Text/chapter2.xhtml", 10),
                merge_plan.NcxNavEntry("book004_item-3", "3화", "Text/chapter3.xhtml", 11),
            ),
        ),
    )


def _render_nav_point(entry, indent=8):
    rendered = merge_plan.render_ncx_nav_point(entry, indent=indent)
    if isinstance(rendered, str):
        return rendered
    return "\n".join(rendered)


def test_render_ncx_document_matches_legacy_header_and_cover_entry():
    entries = (
        merge_plan.NcxNavEntry("cover", "\ud45c\uc9c0", "Text/cover.xhtml", 1),
    )

    ncx = merge_plan.render_ncx_document(
        "AT&T <Novel>",
        "urn:uuid:test-merge-id",
        entries,
        depth=2,
    )

    assert ncx.startswith('<?xml version="1.0" encoding="utf-8"?>\n<ncx ')
    assert 'xmlns="http://www.daisy.org/z3986/2005/ncx/"' in ncx
    assert "<head>" in ncx
    assert '<meta name="dtb:uid" content="urn:uuid:test-merge-id"/>' in ncx
    assert '<meta name="dtb:depth" content="2"/>' in ncx
    assert '<meta name="dtb:totalPageCount" content="0"/>' in ncx
    assert '<meta name="dtb:maxPageNumber" content="0"/>' in ncx
    assert "<docTitle><text>AT&amp;T &lt;Novel&gt;</text></docTitle>" in ncx
    assert "<navMap>" in ncx
    assert '<navPoint id="cover" playOrder="1">' in ncx
    assert "<text>\ud45c\uc9c0</text>" in ncx
    assert '<content src="Text/cover.xhtml"/>' in ncx


def test_render_ncx_nav_point_escapes_labels_and_preserves_anchor_src():
    entry = merge_plan.NcxNavEntry(
        "chapter-1",
        "A&B <C> > D",
        "Text/chapter.xhtml#h1",
        3,
    )

    nav_point = _render_nav_point(entry)

    assert '<navPoint id="chapter-1" playOrder="3">' in nav_point
    assert "<text>A&amp;B &lt;C&gt; &gt; D</text>" in nav_point
    assert '<content src="Text/chapter.xhtml#h1"/>' in nav_point


def test_render_ncx_nav_point_quotes_attribute_values():
    entry = merge_plan.NcxNavEntry(
        'chapter "one" \'two\'',
        "Chapter",
        'Text/chapter.xhtml?name=A&B&quote="yes"',
        7,
    )

    nav_point = _render_nav_point(entry)

    assert 'id="chapter &quot;one&quot; \'two\'"' in nav_point
    assert 'src=\'Text/chapter.xhtml?name=A&amp;B&amp;quote="yes"\'' in nav_point


def test_render_ncx_nav_point_preserves_nested_order_and_indentation():
    parent = merge_plan.NcxNavEntry(
        "vol-1",
        "Volume 1",
        "Text/vol1.xhtml",
        2,
        children=(
            merge_plan.NcxNavEntry("chap-1", "Chapter 1", "Text/ch1.xhtml", 3),
            merge_plan.NcxNavEntry("chap-2", "Chapter 2", "Text/ch2.xhtml", 4),
        ),
    )

    nav_point = _render_nav_point(parent, indent=8)

    assert '        <navPoint id="vol-1" playOrder="2">' in nav_point
    assert '            <content src="Text/vol1.xhtml"/>' in nav_point
    assert '            <navPoint id="chap-1" playOrder="3">' in nav_point
    assert '                <content src="Text/ch1.xhtml"/>' in nav_point
    assert nav_point.index('id="vol-1"') < nav_point.index('id="chap-1"')
    assert nav_point.index('id="chap-1"') < nav_point.index('id="chap-2"')


def test_render_ncx_document_renders_multiple_top_level_entries_in_order():
    entries = (
        merge_plan.NcxNavEntry("cover", "\ud45c\uc9c0", "Text/cover.xhtml", 1),
        merge_plan.NcxNavEntry("chap-1", "Chapter 1", "Text/ch1.xhtml", 2),
        merge_plan.NcxNavEntry("chap-2", "Chapter 2", "Text/ch2.xhtml", 3),
    )

    ncx = merge_plan.render_ncx_document("Merged", "urn:uuid:order", entries)

    assert ncx.index('id="cover"') < ncx.index('id="chap-1"')
    assert ncx.index('id="chap-1"') < ncx.index('id="chap-2"')
    assert ncx.count("<navPoint ") == 3
    assert ncx.rstrip().endswith("</ncx>")


def _render_toc_page(entries, **kwargs):
    renderer = getattr(merge_plan, "render_toc_page_document", None)
    if renderer is None:
        pytest.skip("pure TOC page renderer has not been extracted yet")
    return renderer(entries, **kwargs)


def test_render_toc_page_document_matches_legacy_xhtml_shell_and_escapes_entries():
    toc_html = _render_toc_page(
        (
            (0, "A&B <Chapter>", 'Text/chapter.xhtml?name=A&B&quote="yes"'),
            (1, "\ub2e4\uc74c \ud654", "Text/next.xhtml#sigil_toc_id_1"),
        )
    )

    assert toc_html.startswith('<?xml version="1.0" encoding="utf-8"?>')
    assert (
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
    ) in toc_html
    assert '<html xmlns="http://www.w3.org/1999/xhtml">' in toc_html
    assert "<head><title>\ubaa9\ucc28</title>" in toc_html
    assert "<body><h1>\U0001f4da \ubaa9\ucc28</h1><ol>" in toc_html
    assert (
        '<li><a href="Text/chapter.xhtml?name=A&amp;B&amp;quote=&quot;yes&quot;">'
        "A&amp;B &lt;Chapter&gt;</a></li>"
    ) in toc_html
    assert '<li><a href="Text/next.xhtml#sigil_toc_id_1">\ub2e4\uc74c \ud654</a></li>' in toc_html
    assert toc_html.rstrip().endswith("</ol></body></html>")


def test_render_toc_page_document_renders_legacy_nested_volume_entries():
    toc_html = _render_toc_page(
        (
            {
                "label": "\uc791\ud488 1\uad8c",
                "href": "Text/vol1.xhtml",
                "children": (
                    {"label": "1\ud654", "href": "Text/vol1_ch1.xhtml"},
                    {"label": "2\ud654", "href": "Text/vol1_ch2.xhtml"},
                ),
            },
        )
    )

    assert '<li><a href="Text/vol1.xhtml">\uc791\ud488 1\uad8c</a><ul>' in toc_html
    assert '<li><a href="Text/vol1_ch1.xhtml">1\ud654</a></li>' in toc_html
    assert '<li><a href="Text/vol1_ch2.xhtml">2\ud654</a></li>' in toc_html
    assert "</ul></li>" in toc_html
    assert toc_html.index("Text/vol1.xhtml") < toc_html.index("Text/vol1_ch1.xhtml")
    assert toc_html.index("Text/vol1_ch1.xhtml") < toc_html.index("Text/vol1_ch2.xhtml")
