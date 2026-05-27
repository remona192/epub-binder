from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.epub_text import (  # noqa: E402
    TextOutputOptions,
    build_combined_text_output_from_paths,
    build_text_output_from_path,
    write_combined_text_output_from_paths,
    write_text_output_from_path,
)


def _write_text_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
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
            """<package><manifest>
<item id="body" href="body.xhtml" media-type="application/xhtml+xml"/>
</manifest><spine><itemref idref="body"/></spine></package>""",
        )
        zf.writestr("OEBPS/body.xhtml", "<html><body><p>첫 문장</p><p>둘째 문장</p></body></html>")


def test_build_text_output_from_txt_applies_cleanup_and_indent(tmp_path):
    src = tmp_path / "source.txt"
    src.write_bytes("front\n본문\n\n\n다음".encode("utf-8"))

    text = build_text_output_from_path(
        src,
        TextOutputOptions(cleanup_text=True, indent_paragraphs=True),
    )

    assert text == "본문\n\n　다음\n"


def test_write_text_output_from_epub_writes_unique_txt(tmp_path):
    src = tmp_path / "book.epub"
    _write_text_epub(src)
    options = TextOutputOptions(remove_skip_pages=False, strip_invisible=False)

    first = write_text_output_from_path(src, tmp_path, options)
    second = write_text_output_from_path(src, tmp_path, options)

    assert Path(first.output_path).name == "book.txt"
    assert Path(second.output_path).name == "book (1).txt"
    assert Path(first.output_path).read_text(encoding="utf-8") == "첫 문장\n둘째 문장\n"
    assert first.char_count == len("첫 문장\n둘째 문장\n")


def test_build_combined_text_output_adds_file_headings(tmp_path):
    first = tmp_path / "001.txt"
    second = tmp_path / "002.txt"
    first.write_text("front\n첫 화", encoding="utf-8")
    second.write_text("둘째 화", encoding="utf-8")

    text = build_combined_text_output_from_paths(
        [first, second],
        TextOutputOptions(cleanup_text=True, indent_paragraphs=False),
    )

    assert text == "001\n\n첫 화\n\n002\n\n둘째 화\n"


def test_write_combined_text_output_writes_unique_file(tmp_path):
    first = tmp_path / "001.txt"
    second = tmp_path / "002.txt"
    first.write_text("첫 화", encoding="utf-8")
    second.write_text("둘째 화", encoding="utf-8")

    result = write_combined_text_output_from_paths(
        [first, second],
        tmp_path,
        TextOutputOptions(cleanup_text=True),
        output_stem="합본:테스트",
    )

    out_path = Path(result.output_path)
    assert out_path.name == "합본_테스트.txt"
    assert out_path.read_text(encoding="utf-8") == "001\n\n첫 화\n\n002\n\n둘째 화\n"
    assert result.source_paths == (str(first), str(second))
