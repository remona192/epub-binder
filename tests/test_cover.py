from pathlib import Path
import io
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.cover import collect_cover_candidates, extract_cover_candidates, extract_cover_image  # noqa: E402


def _cover_sample() -> tuple[bytes, bytes]:
    cover_bytes = b"\xff\xd8\xff\xe0cover-data"
    interior_bytes = b"\x89PNG\r\n\x1ainterior-data"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, b"application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0" encoding="utf-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Cover Sample</dc:title>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    <item id="cover-image" href="Images/cover.jpg" media-type="image/jpeg"/>
    <item id="interior-image" href="Images/interior.png" media-type="image/png"/>
    <item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine><itemref idref="body"/></spine>
</package>""",
        )
        zf.writestr("OEBPS/Images/cover.jpg", cover_bytes)
        zf.writestr("OEBPS/Images/interior.png", interior_bytes)
        zf.writestr("OEBPS/body.xhtml", "<html><body><p>body</p></body></html>")
    return buf.getvalue(), cover_bytes


def test_extracts_opf_meta_cover_and_candidates():
    epub_bytes, cover_bytes = _cover_sample()

    data, ext = extract_cover_image(epub_bytes)
    assert data == cover_bytes
    assert ext == ".jpg"

    candidates = collect_cover_candidates(epub_bytes)
    assert len(candidates) == 1
    assert candidates[0].filename == "OEBPS/Images/cover.jpg"
    assert candidates[0].source == "opf_meta"
    assert candidates[0].is_default is True


def test_extract_cover_candidates_can_include_non_cover_images():
    epub_bytes, cover_bytes = _cover_sample()

    candidates = extract_cover_candidates(epub_bytes, include_all_images=True)

    assert [item["filename"] for item in candidates] == [
        "OEBPS/Images/cover.jpg",
        "OEBPS/Images/interior.png",
    ]
    assert candidates[0]["data"] == cover_bytes
    assert candidates[0]["source"] == "opf_meta"
    assert candidates[0]["is_default"] is True
    assert candidates[1]["source"] == "image"
    assert candidates[1]["is_default"] is False
