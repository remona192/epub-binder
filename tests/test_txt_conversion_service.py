from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.txt_conversion import (  # noqa: E402
    normalize_txt_epub_job,
    safe_txt_epub_stem,
    write_txt_epub_job,
)


def test_safe_txt_epub_stem_adds_author_without_duplicate_prefix():
    assert safe_txt_epub_stem("작품", "작가") == "[작가] 작품"
    assert safe_txt_epub_stem("[작가] 작품", "작가") == "[작가] 작품"
    assert safe_txt_epub_stem("작품", "미상") == "작품"
    assert (
        safe_txt_epub_stem("뇌조_1990_할리우드_망나니_배우가_되었다_1_216_미완", "뇌조")
        == "[뇌조] 1990 할리우드 망나니 배우가 되었다 1-216 미완"
    )


def test_write_txt_epub_job_writes_unique_valid_epub(tmp_path):
    job = normalize_txt_epub_job(
        {
            "path": "source.txt",
            "title": "작품",
            "author": "작가",
            "chapters": (("1화", ("본문",)),),
        }
    )

    first = write_txt_epub_job(job, tmp_path)
    second = write_txt_epub_job(job, tmp_path)

    assert Path(first.output_path).name == "[작가] 작품.epub"
    assert Path(second.output_path).name == "[작가] 작품 (1).epub"
    assert first.chapter_count == 1
    assert first.byte_count == Path(first.output_path).stat().st_size
    with zipfile.ZipFile(first.output_path, "r") as zf:
        assert zf.infolist()[0].filename == "mimetype"
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert "OEBPS/content.opf" in zf.namelist()


def test_write_txt_epub_job_uses_clean_title_and_author_in_opf(tmp_path):
    job = normalize_txt_epub_job(
        {
            "path": "source.txt",
            "title": "뇌조_1990_할리우드_망나니_배우가_되었다_1_216_미완",
            "author": "뇌조",
            "chapters": (("1화", ("본문",)),),
        }
    )

    result = write_txt_epub_job(job, tmp_path)

    assert Path(result.output_path).name == "[뇌조] 1990 할리우드 망나니 배우가 되었다 1-216 미완.epub"
    with zipfile.ZipFile(result.output_path, "r") as zf:
        opf = zf.read("OEBPS/content.opf").decode("utf-8")
    assert "<dc:title>1990 할리우드 망나니 배우가 되었다 1-216 미완</dc:title>" in opf
    assert '<dc:creator opf:role="aut">뇌조</dc:creator>' in opf
