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


def _source_episode_range_suffix(source_path: str | Path) -> str:
    stem = Path(source_path).stem.replace("_", " ")
    stem = re.sub(r"\s+", " ", stem).strip()
    side_prefix = ""
    if re.search(r"외전|번외|특전|특별\s*외전|특외", stem, re.IGNORECASE):
        if re.search(r"특별\s*외전|특외", stem, re.IGNORECASE):
            side_prefix = "특별외전 "
        elif re.search(r"외전|번외", stem, re.IGNORECASE):
            side_prefix = "외전 "
        else:
            side_prefix = "특전 "
    for match in re.finditer(
        r"(?<!\d)(?P<start>\d{1,5})\s*[-~–—]\s*(?P<end>\d{1,5})(?:\s*(?P<unit>화|회|장))?",
        stem,
        re.IGNORECASE,
    ):
        start = int(match.group("start"))
        end = int(match.group("end"))
        if end > start and end - start >= 3:
            unit = match.group("unit") or "화"
            return f"{side_prefix}{start}-{end}{unit}".strip()
    return ""


def append_source_episode_range(title: str, source_path: str | Path) -> str:
    title = str(title or "").strip()
    if re.search(r"(?<!\d)\d{1,5}\s*[-~–—]\s*\d{1,5}\s*(?:화|회|권)?", title):
        return title
    suffix = _source_episode_range_suffix(source_path)
    if not suffix:
        return title
    base = re.sub(r"\s*\(완결\)\s*$", "", title).strip()
    complete = " (완결)" if re.search(r"\(완결\)\s*$", title) else ""
    return f"{base} {suffix}{complete}".strip()


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
    title = append_source_episode_range(title, job.path)
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
