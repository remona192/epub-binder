from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .name_cleanup import clean_series_title_author
from .txt_epub import build_txt_epub


@dataclass(frozen=True)
class TxtEpubJob:
    path: str
    title: str
    author: str
    chapters: tuple
    cover_data: bytes | None = None
    cover_ext: str = ".jpg"


@dataclass(frozen=True)
class TxtEpubConversionResult:
    source_path: str
    output_path: str
    title: str
    author: str
    chapter_count: int
    byte_count: int


def safe_txt_epub_stem(title: str, author: str = "") -> str:
    title, author = clean_series_title_author(title, author)
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", title or "").strip() or "untitled"
    author_clean = (author or "").strip()
    if not author_clean or author_clean == "미상":
        return safe_title
    safe_author = re.sub(r'[\\/:*?"<>|\[\]]', "_", author_clean).strip()
    if re.match(r"^\s*\[[^\]]+\]", title or ""):
        return safe_title
    return f"[{safe_author}] {safe_title}"


def unique_epub_output_path(output_dir: str | Path, stem: str) -> Path:
    out_dir = Path(output_dir)
    out_path = out_dir / f"{stem}.epub"
    index = 1
    while out_path.exists():
        out_path = out_dir / f"{stem} ({index}).epub"
        index += 1
    return out_path


def normalize_txt_epub_job(
    job,
    *,
    default_cover_data: bytes | None = None,
    default_cover_ext: str = ".jpg",
) -> TxtEpubJob:
    if isinstance(job, TxtEpubJob):
        return job
    if isinstance(job, dict):
        cover_data = job.get("cover_data") or default_cover_data
        cover_ext = job.get("cover_ext", ".jpg") if job.get("cover_data") else default_cover_ext
        return TxtEpubJob(
            path=str(job["path"]),
            title=str(job["title"]),
            author=str(job["author"]),
            chapters=tuple(job["chapters"]),
            cover_data=cover_data,
            cover_ext=str(cover_ext or ".jpg"),
        )
    txt_path, title, author, chapters = job
    return TxtEpubJob(
        path=str(txt_path),
        title=str(title),
        author=str(author),
        chapters=tuple(chapters),
        cover_data=default_cover_data,
        cover_ext=str(default_cover_ext or ".jpg"),
    )


def write_txt_epub_job(job: TxtEpubJob, output_dir: str | Path) -> TxtEpubConversionResult:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    title, author = clean_series_title_author(job.title, job.author)
    data = build_txt_epub(
        job.chapters,
        title,
        author,
        job.cover_data,
        job.cover_ext,
    )
    stem = safe_txt_epub_stem(title, author)
    out_path = unique_epub_output_path(out_dir, stem)
    out_path.write_bytes(data)
    return TxtEpubConversionResult(
        source_path=job.path,
        output_path=str(out_path),
        title=title,
        author=author,
        chapter_count=len(job.chapters),
        byte_count=len(data),
    )
