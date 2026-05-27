from __future__ import annotations

from html import escape
import io
import uuid
import zipfile

from .merge_plan import NcxNavEntry, render_ncx_nav_point


def build_txt_epub(
    chapters,
    title: str,
    author: str,
    cover_data: bytes | None = None,
    cover_ext: str = ".jpg",
) -> bytes:
    """Build EPUB bytes from ``[(chapter_title, html_lines), ...]``."""
    book_id = str(uuid.uuid4())
    css = (
        "body { font-family: serif; line-height: 1.8; margin: 5% 8%; "
        "text-align: justify; }\n"
        "p { margin-bottom: 1.2em; text-indent: 0.75em; }\n"
        "h2 { text-align: center; margin: 2em 0 1em; }\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        zf.writestr("OEBPS/style.css", css)

        cover_manifest = ""
        cover_meta = ""
        cover_spine = ""
        cover_guide = ""
        if cover_data:
            ext = (cover_ext or ".jpg").lower()
            if ext not in (".jpg", ".jpeg", ".png"):
                ext = ".jpg"
            mime = "image/png" if ext == ".png" else "image/jpeg"
            zf.writestr(f"OEBPS/cover{ext}", cover_data)
            zf.writestr(
                "OEBPS/cover.xhtml",
                '<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>Cover</title>'
                "<style>body{margin:0;padding:0;text-align:center;}"
                "img{max-width:100%;height:auto;}</style></head>"
                f'<body><img src="cover{ext}" alt="cover"/></body></html>',
            )
            cover_manifest = (
                f'<item id="cover-img" href="cover{ext}" media-type="{mime}" '
                'properties="cover-image"/>'
                '<item id="cover-xhtml" href="cover.xhtml" '
                'media-type="application/xhtml+xml"/>'
            )
            cover_meta = '<meta name="cover" content="cover-img"/>'
            cover_spine = '<itemref idref="cover-xhtml"/>'
            cover_guide = '<reference type="cover" title="Cover" href="cover.xhtml"/>'

        manifest_items = ""
        spine_items = ""
        nav_point_lines: list[str] = []
        play_order = 1
        if cover_data:
            nav_point_lines.extend(
                render_ncx_nav_point(
                    NcxNavEntry("cover", "표지", "cover.xhtml", play_order),
                    indent=0,
                )
            )
            play_order += 1

        for index, (chapter_title, chapter_lines) in enumerate(chapters):
            filename = f"ch_{index:04d}.xhtml"
            body = "".join(f"<p>{line}</p>" for line in chapter_lines) or "<p>&#160;</p>"
            nav_label = chapter_title or f"챕터 {index + 1}"
            safe_title = escape(nav_label)
            zf.writestr(
                f"OEBPS/{filename}",
                '<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head>'
                f"<title>{safe_title}</title>"
                '<link rel="stylesheet" type="text/css" href="style.css"/></head>'
                f"<body><h2>{safe_title}</h2>{body}</body></html>",
            )
            manifest_items += f'<item id="c{index}" href="{filename}" media-type="application/xhtml+xml"/>'
            spine_items += f'<itemref idref="c{index}"/>'
            nav_point_lines.extend(
                render_ncx_nav_point(
                    NcxNavEntry(f"n{index}", nav_label, filename, play_order),
                    indent=0,
                )
            )
            play_order += 1
        nav_points = "".join(nav_point_lines)

        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<package version="2.0" xmlns="http://www.idpf.org/2007/opf" '
            'unique-identifier="BookId">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:opf="http://www.idpf.org/2007/opf">'
            f"<dc:title>{escape(title)}</dc:title>"
            f'<dc:creator opf:role="aut">{escape(author)}</dc:creator>'
            "<dc:language>ko</dc:language>"
            f'<dc:identifier id="BookId">urn:uuid:{book_id}</dc:identifier>'
            f"{cover_meta}</metadata>"
            "<manifest>"
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
            '<item id="css" href="style.css" media-type="text/css"/>'
            f"{cover_manifest}{manifest_items}</manifest>"
            f'<spine toc="ncx">{cover_spine}{spine_items}</spine>'
            + (f"<guide>{cover_guide}</guide>" if cover_guide else "")
            + "</package>",
        )

        zf.writestr(
            "OEBPS/toc.ncx",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            f'<head><meta name="dtb:uid" content="urn:uuid:{book_id}"/></head>'
            f"<docTitle><text>{escape(title)}</text></docTitle>"
            f"<navMap>{nav_points}</navMap></ncx>",
        )
    return buf.getvalue()
