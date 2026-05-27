# -*- coding: utf-8 -*-
from __future__ import annotations

import io
import os
from pathlib import Path
import re
import shutil
import uuid
import zipfile

from PyQt6.QtCore import QThread, pyqtSignal

from epub_binder_app.settings import APP_COLORS as C
from epub_binder_app.ui.helpers import natural_sort_key
from epub_binder_core.cover import extract_cover_image as _core_extract_cover_image
from epub_binder_core.cover import extract_cover_candidates as _core_extract_cover_candidates
from epub_binder_core.epub_archive import (
    add_noise_to_epub,
    apply_epub_timestamp,
    compress_epub_images,
    write_epub_directory_to_file as _core_write_epub_directory_to_file,
    write_epub_shell_files as _core_write_epub_shell_files,
)
from epub_binder_core.epub_cleanup import (
    remove_invisible_chars as _core_remove_invisible_chars,
    scan_invisible_chars as _core_scan_invisible_chars,
    strip_epub_in_memory as _core_strip_epub_in_memory,
)
from epub_binder_core.epub_text import (
    TextOutputOptions as _CoreTextOutputOptions,
    write_combined_text_output_from_paths as _core_write_combined_text_output_from_paths_v2,
    write_text_output_from_path as _core_write_text_output_from_path_v2,
)
from epub_binder_core.errors import (
    format_naver_fetch_error as _core_format_naver_fetch_error,
    format_worker_error as _core_format_worker_error,
)
from epub_binder_core.merge_plan import (
    NcxNavEntry as _CoreNcxNavEntry,
    build_multi_volume_ncx_entry as _core_build_multi_volume_ncx_entry,
    build_volume_chapter_ncx_entries as _core_build_volume_chapter_ncx_entries,
    cover_asset_basenames as _core_cover_asset_basenames,
    decide_merge_page_skip as _core_decide_merge_page_skip,
    flat_volume_chapter_label as _core_flat_volume_chapter_label,
    infer_creator_from_title_or_filename as _core_infer_creator_from_title_or_filename,
    plan_unreferenced_image_prune as _core_plan_unreferenced_image_prune,
    plan_volume_chapter_toc as _core_plan_volume_chapter_toc,
    referenced_image_basenames as _core_referenced_image_basenames,
    render_merge_opf as _core_render_merge_opf,
    render_ncx_nav_point as _core_render_ncx_nav_point,
    render_toc_page_document as _core_render_toc_page_document,
    should_use_multi_volume_ncx as _core_should_use_multi_volume_ncx,
    volume_parent_label as _core_volume_parent_label,
)
from epub_binder_core.naver_series import (
    NaverSeriesCookies as _CoreNaverSeriesCookies,
    fetch_naver_series_cover as _core_fetch_naver_series_cover,
)
from epub_binder_core.title_metadata import (
    extract_creator_from_html as _extract_creator_from_html,
    extract_title_from_html as _extract_title_from_html,
    is_chapterish_title as _is_chapterish_title,
    is_generic_ncx_label as _is_generic_ncx_label,
    normalize_title as _normalize_title,
    read_dc_tag as _read_dc_tag,
    strip_trailing_volume_suffix as _strip_trailing_volume_suffix,
)
from epub_binder_core.toc import (
    SUBNAV_HEAD_PAT as _SUBNAV_HEAD_PAT,
    extract_all_subheadings,
    extract_chapter_title,
    inject_subheading_anchors,
    is_consistent_filename_label_set as _is_consistent_filename_label_set,
    is_skip_page as _core_is_skip_page,
    is_subnav_heading_candidate as _is_subnav_heading_candidate,
    merge_page_title_from_sources as _core_merge_page_title_from_sources,
    prefer_filename_toc_title as _prefer_filename_toc_title,
    toc_label_from_filename as _toc_label_from_filename,
)
from epub_binder_core.txt_conversion import (
    normalize_txt_epub_job as _core_normalize_txt_epub_job_v2,
    write_txt_epub_job as _core_write_txt_epub_job_v2,
)

def _format_worker_error(exc):
    return _core_format_worker_error(exc)


def _remove_continued_notice_html(raw: str) -> tuple[str, int]:
    """Remove standalone end-of-volume continuation notices from merged body HTML."""
    removed = 0

    def _is_notice(inner_html: str) -> bool:
        text = re.sub(r"<style[^>]*>.*?</style>", "", inner_html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"&nbsp;|&#160;", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        text = text.strip("「」『』[]()（）<>〈〉-–—_*·.。…!！~")
        if not text:
            return False
        compact = re.sub(r"\s+", "", text)
        return bool(re.fullmatch(
            r"(?:다음|다음번|차기|차권|다음권|다음 권|다음화|다음 화|다음장|다음 장)"
            r"(?:에|에서|으로)?(?:계속|이어집니다|이어짐|계속됩니다|계속됩니다\.?|계속됨)"
            r"|(?:다음|다음권|다음 권)(?:에서|에)?만나요",
            compact,
        ))

    def _drop_block(match):
        nonlocal removed
        if _is_notice(match.group(0)):
            removed += 1
            return ""
        return match.group(0)

    block_pat = re.compile(
        r"<(?P<tag>p|div|h[1-6])\b[^>]*>.*?</(?P=tag)>",
        re.DOTALL | re.IGNORECASE,
    )
    raw = block_pat.sub(_drop_block, raw)

    line_pat = re.compile(
        r"(?im)^\s*(?:다음\s*권|다음권|다음\s*화|다음화|다음\s*장|다음장)"
        r"\s*(?:에|에서|으로)?\s*(?:계속(?:됩니다|됨)?|이어집니다|이어짐)\s*[.!。…]*\s*$"
    )
    raw, line_removed = line_pat.subn("", raw)
    return raw, removed + line_removed


def scan_invisible_chars(epub_bytes: bytes) -> tuple:
    return _core_scan_invisible_chars(epub_bytes)


def remove_invisible_chars(epub_bytes: bytes):
    return _core_remove_invisible_chars(epub_bytes)


def is_skip_page(filename: str, content_bytes: bytes):
    return _core_is_skip_page(filename, content_bytes)


def strip_epub_in_memory(epub_bytes: bytes) -> tuple:
    return _core_strip_epub_in_memory(epub_bytes, skip_page_detector=is_skip_page)


def extract_cover_image(epub_bytes: bytes):
    return _core_extract_cover_image(epub_bytes, sort_key=natural_sort_key)


def extract_cover_candidates(epub_bytes: bytes, include_all_images: bool = False):
    return _core_extract_cover_candidates(
        epub_bytes,
        include_all_images=include_all_images,
        sort_key=natural_sort_key,
    )

class ScanWorker(QThread):
    """파일 목록을 백그라운드에서 스캔, 파일 하나씩 결과 emit."""
    scan_done = pyqtSignal(str, int, dict)   # path, total, char_counts

    def __init__(self, paths: list):
        super().__init__()
        self._paths = list(paths)

    def run(self):
        for path in self._paths:
            try:
                data = open(path, 'rb').read()
                total, counts = scan_invisible_chars(data)
                # 판권 페이지 감지
                try:
                    import zipfile as _zf
                    _cr = 0
                    with _zf.ZipFile(_zf.io.BytesIO(data)) as _z:
                        for _n in _z.namelist():
                            if _n.lower().endswith(('.html', '.xhtml', '.htm')):
                                if is_skip_page(_n, _z.read(_n)):
                                    _cr += 1
                    if _cr:
                        counts['판권'] = _cr
                except Exception:
                    pass
                self.scan_done.emit(path, total, counts)
            except Exception:
                self.scan_done.emit(path, -1, {})


class StripOnlyWorker(QThread):
    """합본 없이 공백코드 + 판권·표지·목차 페이지 제거만 수행하는 워커."""
    log_signal      = pyqtSignal(str, str)   # (message, tag)
    progress_signal = pyqtSignal(int)         # 0–100
    done_signal     = pyqtSignal(int, int, int, int)  # (ok, fail, total_pages, total_chars)

    _REASON_KR = {'copyright': '판권', 'cover': '표지', 'index': '목차'}

    # 공백코드 이름 → 설명
    _CHAR_DESC = {
        'U+200B': 'ZERO WIDTH SPACE',
        'U+200C': 'ZERO WIDTH NON-JOINER',
        'U+200D': 'ZERO WIDTH JOINER',
        'U+200E': 'LEFT-TO-RIGHT MARK',
        'U+200F': 'RIGHT-TO-LEFT MARK',
        'U+180E': 'MONGOLIAN VOWEL SEPARATOR',
        'U+2060': 'WORD JOINER',
        'U+2061': 'FUNCTION APPLICATION',
        'U+2062': 'INVISIBLE TIMES',
        'U+2063': 'INVISIBLE SEPARATOR',
        'U+2064': 'INVISIBLE PLUS',
        'U+2066': 'LEFT-TO-RIGHT ISOLATE',
        'U+2067': 'RIGHT-TO-LEFT ISOLATE',
        'U+2068': 'FIRST STRONG ISOLATE',
        'U+2069': 'POP DIRECTIONAL ISOLATE',
        'U+206A': 'INHIBIT SYMMETRIC SWAPPING',
        'U+206B': 'ACTIVATE SYMMETRIC SWAPPING',
        'U+206C': 'INHIBIT ARABIC FORM SHAPING',
        'U+206D': 'ACTIVATE ARABIC FORM SHAPING',
        'U+206E': 'NATIONAL DIGIT SHAPES',
        'U+206F': 'NOMINAL DIGIT SHAPES',
        'U+034F': 'COMBINING GRAPHEME JOINER',
        'U+FEFF': 'BOM / ZERO WIDTH NO-BREAK SPACE',
        'U+FFF9': 'INTERLINEAR ANNOTATION ANCHOR',
        'U+FFFA': 'INTERLINEAR ANNOTATION SEPARATOR',
        'U+FFFB': 'INTERLINEAR ANNOTATION TERMINATOR',
        'U+E0001': 'LANGUAGE TAG',
        'book-token': '리디북스 워터마크',
    }

    def __init__(self, files: list, out_dir: str, timestamp=None,
                 compress_images=False, noise_level=0):
        super().__init__()
        self._files           = list(files)   # [(path, name, size_str), ...]
        self._out_dir         = out_dir
        self._timestamp       = timestamp      # (y, mo, d, 0, 0, 0) 또는 None
        self._compress_images = compress_images
        self._noise_level     = noise_level    # 0=미적용, 1~3=강도

    def _log(self, msg, tag="info"):
        self.log_signal.emit(msg, tag)

    def run(self):
        ok = 0; fail = 0; skip = 0; total_pages = 0; total_chars = 0
        total_bytes_saved = 0
        agg_char_counts: dict = {}   # 전체 파일 합산 char_counts
        n = len(self._files)
        out = Path(self._out_dir)
        out.mkdir(parents=True, exist_ok=True)

        for i, (path, name, _) in enumerate(self._files):
            orig_bytes = Path(path).read_bytes()
            orig_size  = len(orig_bytes)
            self._log(
                f'<span style="font-weight:600;">[{i+1}/{n}] 처리 중: {name}</span>',
                "html")
            try:
                cleaned, removed_pages, chars_removed, char_counts = \
                    strip_epub_in_memory(orig_bytes)
                new_size  = len(cleaned)
                size_diff = orig_size - new_size

                changed = chars_removed > 0 or bool(removed_pages)

                if changed:
                    # ── 공백코드 상세 ───────────────────────────
                    if char_counts:
                        for cname, cnt in sorted(char_counts.items()):
                            desc = self._CHAR_DESC.get(cname, '')
                            label = f"{cname} ({desc})" if desc else cname
                            self._log(f"   ✂️ {label} 제거: {cnt:,}개", "ok")
                            agg_char_counts[cname] = agg_char_counts.get(cname, 0) + cnt
                    elif chars_removed > 0:
                        self._log(f"   ✂️ 공백코드 제거: {chars_removed:,}개", "ok")

                    # ── 판권·표지·목차 상세 ─────────────────────
                    if removed_pages:
                        _page_emoji = {'표지': '🖼️', '판권': '📜', '목차': '📑'}
                        for pg_name, reason in removed_pages:
                            kr = self._REASON_KR.get(reason, reason)
                            em = next((v for k, v in _page_emoji.items() if k in kr), '🗑️')
                            self._log(f"   {em} {kr} 페이지 제거: {pg_name}", "ok")
                        total_pages += len(removed_pages)

                    # ── 파일 크기 변화 ──────────────────────────
                    self._log(
                        f"   💾 파일 크기: {orig_size:,} → {new_size:,} bytes"
                        f"  (△{size_diff:,})", "info")

                    total_chars    += chars_removed
                    total_bytes_saved += size_diff

                    # ── 용량 줄이기 ─────────────────────────────
                    if self._compress_images:
                        self._log("   🗜️ 이미지 압축 적용 중...", "info")
                        cleaned = compress_epub_images(cleaned)

                    # ── 노이즈 삽입 ──────────────────────────────
                    if self._noise_level > 0:
                        self._log(f"   🎲 노이즈 삽입 중 (레벨 {self._noise_level})...", "info")
                        cleaned = add_noise_to_epub(cleaned, self._noise_level)

                    # ── 타임스탬프 적용 + 저장 ──────────────────
                    if self._timestamp:
                        cleaned = apply_epub_timestamp(cleaned, self._timestamp)
                    out_path = out / Path(path).name
                    out_path.write_bytes(cleaned)
                    self._log(
                        f'  ✅ 완료: <span style="color:#18a870;">{name}</span>', "html")
                    ok += 1
                else:
                    self._log(f"   ✨ 공백코드 없음 / 판권·표지 없음", "info")
                    if self._compress_images:
                        self._log("   🗜️ 이미지 압축 적용 중...", "info")
                        cleaned = compress_epub_images(cleaned)
                    if self._noise_level > 0:
                        self._log(f"   🎲 노이즈 삽입 중 (레벨 {self._noise_level})...", "info")
                        cleaned = add_noise_to_epub(cleaned, self._noise_level)
                    if self._timestamp:
                        cleaned = apply_epub_timestamp(cleaned, self._timestamp)
                    out_path = out / Path(path).name
                    out_path.write_bytes(cleaned)
                    self._log(
                        f'  ✅ 완료 (변경 없음): <span style="color:#8893b0;">{name}</span>',
                        "html")
                    ok += 1; skip += 1

            except Exception as ex:
                self._log(f"  ❌ {_format_worker_error(ex)}", "err")
                fail += 1

            self.progress_signal.emit(int((i + 1) / n * 100))

        # ── 최종 통계 요약 ──────────────────────────────────
        changed_cnt = ok - skip
        self._log("", "info")
        self._log(f"✅ 처리 완료: {ok}/{n} 성공!", "ok")
        self._log(f"   🧹 코드 제거 후 저장: {changed_cnt}개", "ok" if changed_cnt else "info")
        self._log(f"   📋 변경 없이 저장:    {skip}개", "info")
        if fail:
            self._log(f"   ❌ 실패: {fail}개", "err")

        if agg_char_counts:
            self._log("📊 제거 통계:", "info")
            for cname, cnt in sorted(agg_char_counts.items()):
                desc = self._CHAR_DESC.get(cname, '')
                label = f"{cname} ({desc})" if desc else cname
                self._log(f"   ✂️ {label}: {cnt:,}개", "info")
        if total_pages:
            self._log(f"   🗑️ 판권·표지·목차 제거: 총 {total_pages}페이지", "info")
        if total_bytes_saved > 0:
            self._log(f"   💾 총 절약된 용량: {total_bytes_saved:,} bytes", "info")

        self.done_signal.emit(ok, fail, total_pages, total_chars)


class MergeWorker(QThread):
    log_signal      = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    done_signal     = pyqtSignal(bool, str)
    cover_missing_signal = pyqtSignal(str, str)  # (epub_path, suggested_title)

    def __init__(self, epub_files, output_path, title, add_toc, toc_titles,
                 custom_cover=None, custom_cover_ext='.jpg',
                 page_title_overrides=None, compress_images=False,
                 timestamp=None, flat_toc=False, keep_vol_covers=False):
        super().__init__()
        self.epub_files            = epub_files
        self.output_path           = output_path
        self.title                 = title
        self.add_toc               = add_toc
        self.toc_titles            = toc_titles
        self.custom_cover          = custom_cover
        self.custom_cover_ext      = custom_cover_ext
        self.page_title_overrides  = page_title_overrides or {}
        self.compress_images       = compress_images
        self.flat_toc              = flat_toc
        self.keep_vol_covers       = keep_vol_covers   # 2권+ 표지 페이지 유지 여부
        # timestamp: (year, month, day) 튜플, None이면 시스템 시간 그대로
        self.timestamp             = timestamp

    def log(self, msg, tag="info"):
        self.log_signal.emit(msg, tag)

    def run(self):
        import tempfile
        import html as hm
        tmp = tempfile.mkdtemp()
        try:
            out_dir   = os.path.join(tmp, "output")
            oebps_dir = os.path.join(out_dir, "OEBPS")
            meta_dir  = os.path.join(out_dir, "META-INF")
            # 파일 구조: OEBPS/Text/{n}/, OEBPS/Styles/{epub_idx}/,
            #             OEBPS/Images/, OEBPS/Fonts/
            text_base   = os.path.join(oebps_dir, "Text")
            styles_base = os.path.join(oebps_dir, "Styles")
            images_dir  = os.path.join(oebps_dir, "Images")
            fonts_dir   = os.path.join(oebps_dir, "Fonts")
            os.makedirs(text_base); os.makedirs(styles_base)
            os.makedirs(images_dir); os.makedirs(meta_dir); os.makedirs(fonts_dir)

            all_spine    = []   # [(id, href, label), ...]  href = OEBPS/Text/{n}/Section0001.xhtml
            all_manifest = {}   # id → (href, media-type)   href relative to content.opf (=out_dir)
            toc_entries  = []   # [(epub_idx, label, content_src), ...]
            # 한 xhtml에 여러 챕터 헤딩이 있는 경우 sub-navPoint 분할용
            # key: item_id, value: [(anchor_id, sub_title), ...] (문서 순서)
            _sub_navs: dict = {}
            total = len(self.epub_files)
            # 사용자가 목차 편집(화 제목 override)을 한 경우에는
            # 자동 서브헤딩 분할이 최종 결과를 덮어쓰지 않도록 비활성화한다.
            _disable_auto_subnav = bool(self.page_title_overrides)
            _CHAP_UNIT_PAT = re.compile(
                r'(?:\d+\s*[화권장부회편절막]|(?:chapter|ch\.?|part)\s*\d+)',
                re.IGNORECASE,
            )
            _CHAP_START_PAT = re.compile(
                r'^(?:제\s*)?\d+\s*[화권장부회편절막]',
                re.IGNORECASE,
            )
            _PLAIN_LIST_TITLE_PAT = re.compile(r'^\d+\s*[.)]\s*\S+')

            def _has_chapter_unit(text: str) -> bool:
                return bool(_CHAP_UNIT_PAT.search(_normalize_title(text or "")))

            def _has_vol_marker(label: str) -> bool:
                """label에 권·부·외전 번호가 있으면 True (다권 계층 판정용).
                화 번호만 있는 연재물은 flat 구조 → 여기서 제외.
                단행본처럼 끝에 숫자만 있는 경우(예: '왕의 귀환 1')도 다권으로 인식.
                """
                if re.search(r'\d+\s*[권부]|외전|번외|특전', label):
                    return True
                # 화/권 없이 끝에 숫자만 있는 단행본 제목 (예: "왕의 귀환 1", "교육 2")
                # 단, 화 번호로 끝나는 연재물("빙하기 ... 86화")은 제외
                if re.search(r'\d+\s*화', label):
                    return False
                return bool(re.search(r'\s\d+\s*$', label))

            def _compact_chapter_label(text: str) -> str:
                """Flat TOC: keep only chapter/episode marker like 185?."""
                t = _normalize_title(text or "").strip()
                if not t:
                    return t
                m = re.search(r'(?:\uC81C\s*)?(\d{1,5})\s*([\uD654\uC7A5\uD68C\uAD8C\uBD80\uD3B8\uC808\uB9C9])', t)
                if m:
                    return f"{int(m.group(1))}{m.group(2)}"
                m_en = re.search(r'\b(?:chapter|ch\.?|part)\s*(\d{1,5})\b', t, re.IGNORECASE)
                if m_en:
                    return f"{int(m_en.group(1))}\uC7A5"
                return t

            # epub별 CSS/폰트 추적
            _fonts_copied: set = set()   # 이미 복사한 폰트 파일명 (중복 방지)
            _css_hash_to_href: dict = {} # sha256 → (oebps_rel_path, xhtml_rel_href) 중복 CSS 재사용

            # 본문 xhtml 전역 순번 (화별 폴더 이름에 사용)
            text_seq = 0
            # 첫 번째 epub에서 추출한 저자명 / 출판사 / 언어
            creator   = ''
            publisher = ''
            language  = 'ko'
            # 삽화 이미지 파일명 중복 방지용 set
            _img_fnames_used = set()
            # 해시 → 저장된 img_rel 매핑 (동일 이미지 재사용)
            _img_hash_to_rel: dict = {}
            # 원본 파일명(소문자) → 변환 후 파일명 (PNG→JPEG 변환 시 src 경로 교정용)
            _img_rename_map: dict = {}

            for idx, epub_path in enumerate(self.epub_files):
                label = (self.toc_titles[idx]
                         if idx < len(self.toc_titles)
                         else Path(epub_path).stem)
                self.progress_signal.emit(int(idx / total * 75))

                # 권별 카운터
                _cnt_invisible = 0
                _cnt_img       = 0
                _cnt_img_skip  = 0
                _cnt_removed   = 0  # 판권/표지 제거 페이지
                _warn_msgs     = []  # 경고만 별도 출력

                # 1. 파일 읽기
                with open(epub_path, 'rb') as f:
                    epub_bytes = f.read()
                size_before = len(epub_bytes)

                # 2. 공백코드 full 제거 (항상)
                try:
                    epub_bytes, removed, char_counts = remove_invisible_chars(epub_bytes)
                    _cnt_invisible = removed
                except Exception as e:
                    _warn_msgs.append(f"코드제거 실패: {e}")

                # 3. EPUB 압축 해제
                bk = os.path.join(tmp, f"b{idx}"); os.makedirs(bk)
                with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as z:
                    # Zip Slip 방지: 압축 엔트리가 대상 폴더(bk) 밖으로 벗어나는지 검사
                    _dest_root = Path(bk).resolve()
                    for _info in z.infolist():
                        _name = _info.filename
                        if not _name:
                            continue
                        _target = (_dest_root / _name).resolve()
                        try:
                            _target.relative_to(_dest_root)
                        except ValueError:
                            raise ValueError(f"Unsafe ZIP entry blocked: {_name}")
                        if _info.is_dir():
                            _target.mkdir(parents=True, exist_ok=True)
                            continue
                        _target.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(_info, 'r') as _src, open(_target, 'wb') as _dst:
                            shutil.copyfileobj(_src, _dst)

                opf_path = self._find_opf(bk)
                manifest, spine, opf_dir = self._parse_opf(opf_path)
                # 메타(작가/출판사/언어) 보강:
                # 첫 파일에 비어있으면 이후 파일들에서라도 채운다.
                try:
                    _opf_meta_raw = Path(opf_path).read_text(encoding='utf-8', errors='replace')
                    if not creator:
                        _v = _read_dc_tag(_opf_meta_raw, 'dc:creator')
                        if _v:
                            creator = _normalize_title(_v)
                    if not publisher:
                        _v = _read_dc_tag(_opf_meta_raw, 'dc:publisher')
                        if _v:
                            publisher = _normalize_title(_v)
                    if (not language) or (language == 'ko'):
                        _v = _read_dc_tag(_opf_meta_raw, 'dc:language')
                        if _v:
                            language = _normalize_title(_v) or language
                except Exception:
                    pass

                # 원본 toc.ncx 파싱: {파일명(소문자): navLabel}
                ncx_labels, ncx_doc_title = self._parse_ncx(opf_dir)
                _ncx_structured = (
                    sum(1 for _v in (ncx_labels or {}).values() if _has_chapter_unit(_v)) >= 2
                )

                # 권목차 단일화/권표지 OFF에서는 스킵될 권표지 페이지가 참조하던
                # 이미지 파일도 함께 제외한다. 파일명이 cover가 아닌 표지도 여기서 잡는다.
                _keep_volume_cover_assets = self.keep_vol_covers and not self.flat_toc
                _cover_asset_names_to_skip: set[str] = set()
                if not _keep_volume_cover_assets:
                    from urllib.parse import unquote as _url_unquote_scan

                    def _mark_cover_assets(_raw_s: str):
                        for _src in re.findall(
                                r'<img\b[^>]+\bsrc=["\']([^"\']+)["\']',
                                _raw_s, re.IGNORECASE):
                            _src = _url_unquote_scan(
                                _src.split('#', 1)[0].split('?', 1)[0])
                            _name = Path(_src.replace('\\', '/')).name.lower()
                            if _name:
                                _cover_asset_names_to_skip.add(_name)

                    _spine_scan_pos = 0
                    for _sid_scan in spine:
                        _href_scan = manifest.get(_sid_scan)
                        if not _href_scan:
                            continue
                        _href_scan = _url_unquote_scan(_href_scan)
                        _src_scan = os.path.join(
                            opf_dir, _href_scan.replace("/", os.sep))
                        if not os.path.exists(_src_scan):
                            continue
                        try:
                            _raw_scan_b = Path(_src_scan).read_bytes()
                        except Exception:
                            continue
                        _spine_scan_pos += 1
                        _skip_scan = None
                        _used_core_skip_scan = False
                        if _core_decide_merge_page_skip:
                            try:
                                _skip_scan = _core_decide_merge_page_skip(
                                    _href_scan,
                                    _raw_scan_b,
                                    ncx_label=ncx_labels.get(Path(_href_scan).name.lower(), '') if ncx_labels else '',
                                    book_index=idx,
                                    spine_position=_spine_scan_pos,
                                    keep_vol_covers=self.keep_vol_covers,
                                    flat_toc=self.flat_toc,
                                    skip_page_detector=is_skip_page,
                                )
                                _used_core_skip_scan = True
                            except Exception:
                                _skip_scan = None
                        if not _used_core_skip_scan:
                            try:
                                _skip_scan = is_skip_page(_href_scan, _raw_scan_b)
                            except Exception:
                                pass
                            if not _skip_scan and ncx_labels:
                                _fname_scan = Path(_href_scan).name.lower()
                                _ncx_scan = ncx_labels.get(_fname_scan, '').strip().lower()
                                if _ncx_scan == 'cover':
                                    _raw_scan_s = _raw_scan_b.decode('utf-8', 'replace')
                                    _has_img_scan = bool(re.search(
                                        r'<img\b', _raw_scan_s, re.IGNORECASE))
                                    _text_scan = re.sub(
                                        r'<style[^>]*>.*?</style>', '',
                                        _raw_scan_s,
                                        flags=re.DOTALL | re.IGNORECASE)
                                    _text_scan = re.sub(r'<[^>]+>', '', _text_scan)
                                    _text_scan = re.sub(r'\s+', ' ', _text_scan).strip()
                                    if _has_img_scan and len(_text_scan) < 80:
                                        _skip_scan = 'cover'
                            if (not _skip_scan and idx > 0 and _spine_scan_pos <= 2):
                                _raw_scan_s = _raw_scan_b.decode('utf-8', 'replace')
                                if re.search(r'<img\b', _raw_scan_s, re.IGNORECASE):
                                    _text_scan = re.sub(
                                        r'<style[^>]*>.*?</style>', '',
                                        _raw_scan_s,
                                        flags=re.DOTALL | re.IGNORECASE)
                                    _text_scan = re.sub(r'<[^>]+>', '', _text_scan)
                                    _text_scan = re.sub(r'\s+', ' ', _text_scan).strip()
                                    if len(_text_scan) < 80:
                                        _skip_scan = 'cover'
                        if _skip_scan == 'cover':
                            if _core_cover_asset_basenames:
                                try:
                                    _cover_asset_names_to_skip.update(
                                        _core_cover_asset_basenames(_raw_scan_b))
                                except Exception:
                                    _mark_cover_assets(
                                        _raw_scan_b.decode('utf-8', 'replace'))
                            else:
                                _mark_cover_assets(
                                    _raw_scan_b.decode('utf-8', 'replace'))

                # 4-a. 커버 이미지: 사용자 지정 우선, 없으면 1권 자동 추출 (최초 1회)
                if idx == 0:
                    # 저자명(dc:creator), 출판사(dc:publisher), 언어(dc:language) 추출
                    try:
                        opf_content_raw = Path(opf_path).read_text(encoding='utf-8', errors='replace')
                        v = _read_dc_tag(opf_content_raw, 'dc:creator')
                        if v: creator = _normalize_title(v)
                        v = _read_dc_tag(opf_content_raw, 'dc:publisher')
                        if v: publisher = _normalize_title(v)
                        v = _read_dc_tag(opf_content_raw, 'dc:language')
                        language = _normalize_title(v) or 'ko'
                    except Exception:
                        pass
                    # OPF에 작가/제목 없으면 판권 페이지 HTML에서 직접 추출
                    if not creator or not self.title:
                        try:
                            with zipfile.ZipFile(io.BytesIO(epub_bytes), 'r') as _zc:
                                for _zname in _zc.namelist():
                                    if not re.search(r'\.(xhtml|html|htm)$', _zname, re.IGNORECASE):
                                        continue
                                    _raw_c = _zc.read(_zname).decode('utf-8', 'replace')
                                    if not creator:
                                        _fc = _extract_creator_from_html(_raw_c)
                                        if _fc:
                                            creator = _fc
                                    if not self.title:
                                        _ft = _extract_title_from_html(_raw_c)
                                        if _ft:
                                            self.title = _ft
                                    if creator and self.title:
                                        break
                        except Exception:
                            pass
                    if self.custom_cover:
                        cover_data = self.custom_cover
                        cover_ext  = self.custom_cover_ext
                    else:
                        cover_data, cover_ext = extract_cover_image(epub_bytes)
                        if not cover_data:
                            # cover 메타가 없는 낱펍은 첫 이미지를 표지로 폴백 (리디 표지 미표시 방지)
                            try:
                                _cands = extract_cover_candidates(
                                    epub_bytes, include_all_images=True)
                                if _cands:
                                    cover_data = _cands[0].get('data')
                                    cover_ext = _cands[0].get('ext', '.jpg')
                            except Exception:
                                pass
                    if cover_data:
                        # ⑤ compress_images=True 이면 커버도 JPEG 압축/변환 적용
                        if self.compress_images:
                            try:
                                from PIL import Image as _PilImgC
                                import io as _ioC
                                _pil_c = _PilImgC.open(_ioC.BytesIO(cover_data))
                                if _pil_c.mode in ('RGBA', 'P', 'LA'):
                                    _bg_c = _PilImgC.new('RGB', _pil_c.size, (255, 255, 255))
                                    _bg_c.paste(_pil_c.convert('RGBA'), mask=_pil_c.convert('RGBA').split()[3])
                                    _pil_c = _bg_c
                                elif _pil_c.mode != 'RGB':
                                    _pil_c = _pil_c.convert('RGB')
                                _buf_c = _ioC.BytesIO()
                                _MAX_DIM_C = 1500
                                _cw, _ch = _pil_c.size
                                if max(_cw, _ch) > _MAX_DIM_C:
                                    _r = _MAX_DIM_C / max(_cw, _ch)
                                    _pil_c = _pil_c.resize((int(_cw*_r), int(_ch*_r)), _PilImgC.LANCZOS)
                                try:
                                    import numpy as _np_c
                                    _arr_c = _np_c.array(_pil_c, dtype=_np_c.int16)
                                    _noise_c = _np_c.random.randint(-1, 2, _arr_c.shape, dtype=_np_c.int16)
                                    _arr_c = _np_c.clip(_arr_c + _noise_c, 0, 255).astype(_np_c.uint8)
                                    _pil_c = _PilImgC.fromarray(_arr_c)
                                except ImportError:
                                    pass
                                _pil_c.save(_buf_c, 'JPEG', quality=80, optimize=True, progressive=True)
                                _recomp_c = _buf_c.getvalue()
                                if len(_recomp_c) < len(cover_data):
                                    cover_data = _recomp_c
                                    cover_ext  = '.jpg'
                            except Exception:
                                pass
                        cover_fname = f"cover{cover_ext}"
                        cover_dst   = os.path.join(images_dir, cover_fname)
                        with open(cover_dst, 'wb') as _cf:
                            _cf.write(cover_data)
                        cover_mt = ('image/jpeg' if cover_ext in ('.jpg','.jpeg') else 'image/png')
                        all_manifest['cover-image'] = (f"OEBPS/Images/{cover_fname}", cover_mt)
                        # 마스터 커버 해시 + 파일명 등록 → 이후 epub의 동일 커버는 재사용
                        import hashlib as _hlib_cv
                        _master_cover_hash = _hlib_cv.md5(cover_data).hexdigest()
                        _img_hash_to_rel[_master_cover_hash] = cover_fname
                        _img_fnames_used.add(cover_fname)

                        # cover.xhtml 생성 (정상 파일과 동일 구조)
                        cover_xhtml = (
                            '<?xml version=\'1.0\' encoding=\'utf-8\'?>\n'
                            '<html xmlns="http://www.w3.org/1999/xhtml">\n'
                            '<head>\n<title>Cover</title>\n'
                            '<style>\n'
                            '    @page { padding:0; margin:0; }\n'
                            '    body { text-align:center; padding:0; margin:0; }\n'
                            '    div { margin:0; padding:0; }\n'
                            '</style>\n</head>\n<body>\n'
                            '<h2 style="display:none;">표지</h2>\n'
                            f'<div><img alt="cover" src="../Images/{cover_fname}"/></div>\n'
                            '</body>\n</html>'
                        )
                        cover_xhtml_dst = os.path.join(text_base, "cover.xhtml")
                        Path(cover_xhtml_dst).write_text(cover_xhtml, encoding="utf-8")
                        all_manifest['cover-html'] = (
                            "OEBPS/Text/cover.xhtml", "application/xhtml+xml")
                        all_spine.insert(0, ("cover-html", "OEBPS/Text/cover.xhtml", -1, "표지", ""))
                    else:
                        _warn_msgs.append("커버 이미지 없음")
                        try:
                            self.cover_missing_signal.emit(
                                str(epub_path),
                                str(self.title or Path(epub_path).stem),
                            )
                        except Exception:
                            pass

                # 4-b. CSS: epub별로 Styles/{idx+1}/ 에 개별 파일 보존
                #      폰트: Fonts/ 에 복사 (파일명 기준 중복 제외)
                epub_styles_dir = os.path.join(styles_base, str(idx + 1))
                # 폴더는 새 CSS가 실제로 생길 때만 생성
                # css_href_map: {원본 css 파일명 → xhtml 내 상대경로}
                css_href_map: dict = {}
                _font_exts = {'.ttf', '.otf', '.woff', '.woff2'}
                css_count = 0; font_count = 0

                for iid, href in manifest.items():
                    # OPF manifest href는 URL 인코딩일 수 있음 (한글/공백 파일명 등)
                    # 파일 시스템 경로 생성 전에 디코딩 (예: %EC%B4%88... → 초심돌...)
                    from urllib.parse import unquote as _url_unquote
                    href = _url_unquote(href)
                    ext = Path(href).suffix.lower()

                    # ── CSS 파일 ──
                    if ext == '.css':
                        src_css = os.path.join(opf_dir, href.replace("/", os.sep))
                        if not os.path.exists(src_css): continue
                        try:
                            import hashlib as _hashlib
                            css_content = Path(src_css).read_text(encoding='utf-8', errors='replace')
                            # @font-face src: ../Fonts/ → ../../Fonts/
                            # (CSS가 Styles/{n}/ 에 저장되므로 폰트까지 두 단계 위)
                            css_content = re.sub(
                                r'(url\(["\']?)(\.\./Fonts/)',
                                r'\1../../Fonts/', css_content, flags=re.IGNORECASE)
                            css_name = Path(href).name
                            css_hash = _hashlib.sha256(css_content.encode('utf-8')).hexdigest()
                            if css_hash in _css_hash_to_href:
                                # 동일 내용 CSS 재사용 → 새 파일 생성 없이 경로만 매핑
                                _, existing_href = _css_hash_to_href[css_hash]
                                css_href_map[css_name] = existing_href
                            else:
                                os.makedirs(epub_styles_dir, exist_ok=True)
                                dst_css  = os.path.join(epub_styles_dir, css_name)
                                Path(dst_css).write_text(css_content, encoding='utf-8')
                                # xhtml(Text/{n}/) → CSS(Styles/{idx+1}/): ../../Styles/{idx+1}/name
                                xhtml_href = f"../../Styles/{idx + 1}/{css_name}"
                                css_href_map[css_name] = xhtml_href
                                css_mid = f"css_{idx}_{re.sub(r'[^a-zA-Z0-9_]', '_', iid)}"
                                all_manifest[css_mid] = (f"OEBPS/Styles/{idx + 1}/{css_name}", "text/css")
                                _css_hash_to_href[css_hash] = (f"OEBPS/Styles/{idx + 1}/{css_name}", xhtml_href)
                                css_count += 1
                        except Exception as e:
                            _warn_msgs.append(f"CSS 실패: {Path(href).name}")

                    # ── 폰트 파일 ──
                    elif ext in _font_exts:
                        src_font = os.path.join(opf_dir, href.replace("/", os.sep))
                        if not os.path.exists(src_font): continue
                        font_name = Path(href).name
                        if font_name not in _fonts_copied:
                            dst_font = os.path.join(fonts_dir, font_name)
                            if not os.path.exists(dst_font):
                                shutil.copy2(src_font, dst_font)
                            _fonts_copied.add(font_name)
                            _mt = {'.ttf': 'application/x-font-ttf',
                                   '.otf': 'application/x-font-opentype',
                                   '.woff': 'application/font-woff',
                                   '.woff2': 'font/woff2'}.get(ext, 'application/octet-stream')
                            fmid = f"font_{re.sub(r'[^a-zA-Z0-9_]', '_', font_name)}"
                            all_manifest[fmid] = (f"OEBPS/Fonts/{font_name}", _mt)
                            font_count += 1

                # 5. 삽화 이미지 복사
                from urllib.parse import unquote as _url_unquote
                for iid, href in manifest.items():
                    href = _url_unquote(href)  # URL 인코딩 해제 (한글/공백 파일명 대응)
                    ext = Path(href).suffix.lower()
                    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                        continue
                    src_img = os.path.join(opf_dir, _url_unquote(href).replace("/", os.sep))
                    if not os.path.exists(src_img):
                        continue

                    # ── 해시 기반 중복 감지: 동일 내용 이미지는 재사용 ──
                    import hashlib as _hashlib
                    src_hash = _hashlib.md5(Path(src_img).read_bytes()).hexdigest()
                    orig_fname_lc = Path(href.replace('\\', '/')).name.lower()

                    if (orig_fname_lc in _cover_asset_names_to_skip
                            and src_hash not in _img_hash_to_rel):
                        _cnt_img_skip += 1
                        continue

                    # cover 계열 이미지: 마스터 커버와 동일하면 skip, 다르면 rename해서 저장
                    if 'cover' in orig_fname_lc:
                        if src_hash in _img_hash_to_rel:
                            # 마스터 커버와 동일 → 이미 등록됨, xhtml rename map만 갱신
                            existing_rel = _img_hash_to_rel[src_hash]
                            final_fname   = Path(existing_rel).name
                            if orig_fname_lc != final_fname.lower():
                                _img_rename_map[orig_fname_lc] = final_fname
                        elif _keep_volume_cover_assets:
                            # 마스터와 다른 커버 이미지 → rename해서 별도 저장
                            orig_fname = Path(href.replace('\\', '/')).name
                            renamed = f"b{idx:02d}_{orig_fname}"
                            if renamed in _img_fnames_used:
                                renamed = f"b{idx:02d}_{idx}_{orig_fname}"
                            cover_extra_dst = os.path.join(images_dir, renamed)
                            shutil.copy2(src_img, cover_extra_dst)
                            _img_hash_to_rel[src_hash] = renamed
                            _img_fnames_used.add(renamed)
                            _img_rename_map[orig_fname.lower()] = renamed
                            cv_mt = ('image/jpeg' if ext in ('.jpg','.jpeg') else 'image/png')
                            all_manifest[f"img_{idx}_cover_extra"] = (f"OEBPS/Images/{renamed}", cv_mt)
                        else:
                            _cnt_img_skip += 1
                        continue
                    if src_hash in _img_hash_to_rel:
                        # 이미 저장된 동일 이미지 → 그 경로 재사용, 복사 생략
                        existing_rel = _img_hash_to_rel[src_hash]
                        # manifest 재등록 없이 경로 매핑만 (중복 manifest 항목 방지)
                        orig_fname_lc = Path(href.replace('\\', '/')).name.lower()
                        final_fname   = Path(existing_rel).name
                        if orig_fname_lc != final_fname.lower():
                            _img_rename_map[orig_fname_lc] = final_fname
                        _cnt_img_skip += 1
                        continue

                    href_norm = href.replace('\\', '/')
                    if re.search(r'[Ii]mages/', href_norm):
                        img_rel = re.sub(r'^.*?[Ii]mages/', '', href_norm)
                    else:
                        img_rel = Path(href_norm).name  # Images/ 폴더 없는 epub 대응
                    # ④ 중복 검사는 변환 전 이름 기준 (변환 후 이름은 아래에서 갱신)
                    if img_rel in _img_fnames_used:
                        parts = img_rel.rsplit('/', 1)
                        img_rel = (f"{parts[0]}/b{idx:02d}_{parts[1]}"
                                   if len(parts) == 2 else f"b{idx:02d}_{img_rel}")
                    _img_hash_to_rel[src_hash] = img_rel  # 임시 등록 (변환 후 갱신)
                    img_dst_dir = os.path.join(images_dir,
                                               os.path.dirname(img_rel.replace('/', os.sep)))
                    os.makedirs(img_dst_dir, exist_ok=True)
                    img_dst_path = os.path.join(images_dir, img_rel.replace('/', os.sep))

                    # 이미지 복사: 기본은 원본 그대로, compress_images=True 시 JPEG 재압축
                    # PNG는 JPEG 변환 후 크기 비교 → 더 작으면 변환본 사용 (파일명도 .jpg로 변경)
                    if self.compress_images:
                        try:
                            from PIL import Image as _PilImg
                            import io as _io2
                            _MAX_DIM   = 1500
                            _PNG_SMALL = 10 * 1024
                            raw_img    = Path(src_img).read_bytes()
                            _orig_size = len(raw_img)
                            if ext == '.png' and _orig_size < _PNG_SMALL:
                                shutil.copy2(src_img, img_dst_path)
                                _cnt_img += 1
                            else:
                                pil_img = _PilImg.open(_io2.BytesIO(raw_img))
                                _iw, _ih = pil_img.size
                                if max(_iw, _ih) > _MAX_DIM:
                                    _r = _MAX_DIM / max(_iw, _ih)
                                    pil_img = pil_img.resize((int(_iw*_r), int(_ih*_r)), _PilImg.LANCZOS)
                                _q = 62 if _orig_size > 500*1024 else (67 if _orig_size > 100*1024 else 72)
                                buf = _io2.BytesIO()
                                _save_img = pil_img
                                if pil_img.mode in ('RGBA', 'P', 'LA'):
                                    _bg = _PilImg.new('RGB', pil_img.size, (255, 255, 255))
                                    _bg.paste(pil_img.convert('RGBA'), mask=pil_img.convert('RGBA').split()[3])
                                    _save_img = _bg
                                elif pil_img.mode != 'RGB':
                                    _save_img = pil_img.convert('RGB')
                                try:
                                    import numpy as _np
                                    _arr = _np.array(_save_img, dtype=_np.int16)
                                    _noise = _np.random.randint(-1, 2, _arr.shape, dtype=_np.int16)
                                    _arr = _np.clip(_arr + _noise, 0, 255).astype(_np.uint8)
                                    _save_img = _PilImg.fromarray(_arr)
                                except ImportError:
                                    pass
                                _save_img.save(buf, 'JPEG', quality=_q, optimize=True, progressive=True)
                                recomp = buf.getvalue()
                                if len(recomp) < _orig_size:
                                    if ext == '.png':
                                        orig_rel = img_rel
                                        img_rel = re.sub(r'\.png$', '.jpg', img_rel, flags=re.IGNORECASE)
                                        img_dst_path = re.sub(r'\.png$', '.jpg', img_dst_path, flags=re.IGNORECASE)
                                        _img_rename_map[Path(orig_rel).name.lower()] = Path(img_rel).name
                                        _img_fnames_used.discard(orig_rel)
                                        _img_fnames_used.add(img_rel)
                                        _img_hash_to_rel[src_hash] = img_rel
                                    Path(img_dst_path).write_bytes(recomp)
                                    _cnt_img += 1
                                else:
                                    shutil.copy2(src_img, img_dst_path)
                                    _cnt_img += 1
                        except Exception as _ie:
                            shutil.copy2(src_img, img_dst_path)
                            _cnt_img += 1
                    else:
                        shutil.copy2(src_img, img_dst_path)
                        _cnt_img += 1

                    img_mt = ('image/jpeg' if img_rel.lower().endswith(('.jpg', '.jpeg')) else 'image/png')
                    img_id = f"img_{idx}_{re.sub(r'[^a-zA-Z0-9_]', '_', iid)}"
                    all_manifest[img_id] = (f"OEBPS/Images/{img_rel}", img_mt)
                    _img_fnames_used.add(img_rel)  # 파일명 사용 등록 (다음 epub 중복 방지)

                # 6. 본문 xhtml 처리: spine 순서로 cover/copyright 제외 후 저장
                toc_first_set = False
                skipped = 0
                kept_in_book = 0

                _pending_chap_prefix = ''  # 빈 화번호 섹션 → 다음 섹션 제목 합성용

                _spine_pos = 0            # 스파인 내 순서 (2권+ 표지 제거 기준)
                for iid in spine:
                    if iid not in manifest: continue
                    href = _url_unquote(manifest[iid])
                    src_f = os.path.join(opf_dir, href.replace("/", os.sep))
                    if not os.path.exists(src_f): continue

                    raw_bytes = Path(src_f).read_bytes()
                    _spine_pos += 1
                    _keep_this_cover = self.keep_vol_covers and not self.flat_toc

                    # 판권·커버·목차 감지 → 제거
                    skip_reason = None
                    _used_core_skip = False
                    if _core_decide_merge_page_skip:
                        try:
                            skip_reason = _core_decide_merge_page_skip(
                                href,
                                raw_bytes,
                                ncx_label=ncx_labels.get(Path(href).name.lower(), '') if ncx_labels else '',
                                book_index=idx,
                                spine_position=_spine_pos,
                                keep_vol_covers=self.keep_vol_covers,
                                flat_toc=self.flat_toc,
                                skip_page_detector=is_skip_page,
                            )
                            _used_core_skip = True
                        except Exception:
                            skip_reason = None
                    if not _used_core_skip:
                        try:
                            skip_reason = is_skip_page(href, raw_bytes)
                        except: pass
                        if skip_reason == 'cover' and idx > 0 and _keep_this_cover:
                            skip_reason = None
                        # NCX 라벨이 "cover"인 이미지 전용 페이지 → 커버 이미지는 별도로 추출되므로 제거
                        # (파일명에 cover가 없어도 content-0001.html 등으로 된 권별 표지 페이지 포함)
                        if not skip_reason and ncx_labels:
                            _fname_lc = Path(href).name.lower()
                            _ncx_lbl  = ncx_labels.get(_fname_lc, '').strip().lower()
                            if _ncx_lbl == 'cover' and not (idx > 0 and _keep_this_cover):
                                _raw_s = raw_bytes.decode('utf-8', 'replace')
                                _has_img = bool(re.search(r'<img\b', _raw_s, re.IGNORECASE))
                                _text_only = re.sub(r'<style[^>]*>.*?</style>', '', _raw_s, flags=re.DOTALL|re.IGNORECASE)
                                _text_only = re.sub(r'<[^>]+>', '', _text_only)
                                _text_only = re.sub(r'\s+', ' ', _text_only).strip()
                                if _has_img and len(_text_only) < 80:
                                    skip_reason = 'cover'
                            # flat_toc 시: 원본 NCX 라벨이 "차례"/"목차"인 페이지 제거
                            if not skip_reason and self.flat_toc:
                                if re.match(r'^(차례|목차|contents?|table\s*of\s*contents?)$', _ncx_lbl, re.IGNORECASE):
                                    skip_reason = 'index'
                        # flat_toc 시: 권별 제목 페이지(book_title) 제거
                        if not skip_reason and self.flat_toc:
                            if Path(href).stem.lower() == 'book_title':
                                skip_reason = 'index'
                        # 2권+ 합본: 스파인 앞쪽(1~2번째) 이미지 전용 페이지 → 권별 표지 제거
                        # 표지는 1권에서만 추출·삽입되고, 2권 이후의 표지 페이지는 중복이므로 제외
                        # keep_vol_covers=True AND flat_toc=False(권 목차 ON)일 때만 표지 유지
                        if not skip_reason and idx > 0 and _spine_pos <= 2 and not _keep_this_cover:
                            _raw_cv = raw_bytes.decode('utf-8', 'replace')
                            if re.search(r'<img\b', _raw_cv, re.IGNORECASE):
                                _txt_cv = re.sub(r'<style[^>]*>.*?</style>', '', _raw_cv,
                                                 flags=re.DOTALL | re.IGNORECASE)
                                _txt_cv = re.sub(r'<[^>]+>', '', _txt_cv)
                                _txt_cv = re.sub(r'\s+', ' ', _txt_cv).strip()
                                if len(_txt_cv) < 80:
                                    skip_reason = 'cover'
                    if skip_reason:
                        _cnt_removed += 1
                        skipped += 1
                        continue

                    # 본문 저장: Text/{text_seq}/ 폴더에
                    text_seq += 1
                    seq_dir = os.path.join(text_base, str(text_seq))
                    os.makedirs(seq_dir, exist_ok=True)
                    out_fname = Path(href).name   # Section0001.xhtml 등

                    # CSS href 경로 재작성: 각 화 고유 CSS 파일 경로로 변환
                    raw_str = raw_bytes.decode('utf-8', 'replace')

                    # 본문 텍스트 0자 섹션 → 제외 (태그·스타일 제거 후 텍스트 없으면 스킵)
                    _body_chk = re.sub(r'<style[^>]*>.*?</style>', '', raw_str,
                                       flags=re.DOTALL | re.IGNORECASE)
                    _body_chk = re.sub(r'<[^>]+>', '', _body_chk)
                    if not _body_chk.strip():
                        # 화번호 있는 빈 섹션 → 다음 섹션 제목 합성을 위해 저장
                        _skipped_title = extract_chapter_title(raw_bytes)
                        if _skipped_title and re.search(r'\d+\s*화', _skipped_title):
                            _pending_chap_prefix = _skipped_title.strip()
                        text_seq -= 1
                        skipped += 1
                        continue

                    def _fix_css_link(m):
                        tag = m.group(0)
                        hm = re.search(r'href=["\']([^"\']+)["\']', tag, re.IGNORECASE)
                        if not hm: return tag
                        css_name = Path(hm.group(1).replace('\\', '/')).name
                        new_href = css_href_map.get(css_name)
                        if new_href:
                            return f'<link rel="stylesheet" type="text/css" href="{new_href}"/>'
                        return tag
                    raw_str = re.sub(r'<link[^>]+\.css[^>]*/?>',
                                     _fix_css_link, raw_str, flags=re.IGNORECASE)

                    # img src 경로 재작성: ../../Images/{원본 상대경로} 로 통일
                    # 원본이 Images/1/map.jpg 이면 ../../Images/1/map.jpg 유지
                    def _fix_img_src(m):
                        orig_src = m.group(2)   # 원본 src 값 (따옴표 제외)
                        norm_src = orig_src.replace('\\', '/')
                        # Images/ 폴더 기준 추출; 없으면 파일명만 사용
                        if re.search(r'[Ii]mages/', norm_src):
                            img_part = re.sub(r'^.*?[Ii]mages/', '', norm_src)
                        else:
                            img_part = Path(norm_src).name
                        # PNG→JPEG 변환된 경우 파일명 교정 (.png → .jpg)
                        fname_lc = Path(img_part).name.lower()
                        if fname_lc in _img_rename_map:
                            img_part = img_part[:len(img_part)-len(Path(img_part).name)] + _img_rename_map[fname_lc]
                        return m.group(1) + '"../../Images/' + img_part + '"'
                    raw_str = re.sub(
                        r'(<img\b[^>]+\bsrc=)["\']([^"\']+\.(jpg|jpeg|png|gif|webp))["\']',
                        _fix_img_src,
                        raw_str, flags=re.IGNORECASE)

                    raw_str, _ = _remove_continued_notice_html(raw_str)

                    # ── 단일 xhtml 내 다중 헤딩 감지 → 앵커 삽입 ──
                    # 예) 538356_1.epub:
                    #   <p class="text"><b>솔저 오브 아포칼립스</b></p>
                    #   <p class="text"><b>Prologue</b></p>
                    #   <p class="text"><b>1화. 새로운 시작(1)</b></p>
                    # → 한 파일에 3개 헤딩 → 각각 navPoint로 분할
                    _sub_anchors_for_this = []
                    if not _disable_auto_subnav:
                        try:
                            _all_subs = extract_all_subheadings(raw_str)
                            # 본문 문장 오탐 방지: 챕터성 헤딩만 sub-navPoint 대상으로 사용
                            _all_subs = [s for s in _all_subs if _is_subnav_heading_candidate(s[0])]
                            # 동일 제목 중복 제거 (순서 유지)
                            _dedup = []
                            _seen_sub_titles = set()
                            for _st, _full, _pos in _all_subs:
                                _k = re.sub(r'\s+', ' ', _st).strip().lower()
                                if _k in _seen_sub_titles:
                                    continue
                                _seen_sub_titles.add(_k)
                                _dedup.append((_st, _full, _pos))
                            _all_subs = _dedup[:6]  # 과도한 분할 방지
                            if len(_all_subs) >= 2:
                                raw_str, _sub_anchors_for_this = inject_subheading_anchors(
                                    raw_str, _all_subs,
                                    id_prefix=f'sub_{text_seq:04d}')
                        except Exception:
                            _sub_anchors_for_this = []

                    # 줄바꿈 이중 변환(\r\r\n) 방지: write_bytes 사용
                    dst_path = os.path.join(seq_dir, out_fname)
                    Path(dst_path).write_bytes(raw_str.encode('utf-8'))

                    # 챕터 제목 결정 (공용 core 로직)
                    override_key = f"{idx}:{iid}"
                    _has_title_override = override_key in self.page_title_overrides
                    if _has_title_override:
                        # 사용자가 직접 편집한 페이지는 자동 서브분할을 강제로 끈다.
                        _sub_anchors_for_this = []
                    page_title = _core_merge_page_title_from_sources(
                        raw_str,
                        out_filename=out_fname,
                        ncx_labels=ncx_labels,
                        ncx_doc_title=ncx_doc_title,
                        series_title=self.title,
                        override_title=self.page_title_overrides.get(override_key, ""),
                        has_override=_has_title_override,
                    )

                    # 이전 빈 화번호 섹션 + 현재 에필로그 등 키워드 제목 합성
                    # 예) "203화"(0자 스킵) + "에필로그 (완결)" → "203화 에필로그 (완결)"
                    if _pending_chap_prefix and page_title:
                        if not re.search(r'\d+\s*화', page_title):
                            page_title = f'{_pending_chap_prefix} {page_title}'
                    _pending_chap_prefix = ''  # 사용 여부 관계없이 초기화

                    if self.flat_toc and page_title:
                        page_title = _compact_chapter_label(page_title)
                        label = _compact_chapter_label(page_title)

                    # OPF href: OEBPS/ 기준 (out_dir 기준 상대경로)
                    opf_href = f"OEBPS/Text/{text_seq}/{out_fname}"
                    item_id  = f"Section{text_seq}"
                    all_manifest[item_id] = (opf_href, "application/xhtml+xml")

                    # TOC 첫 항목 등록
                    if not toc_first_set:
                        toc_entries.append((idx, label, opf_href))
                        toc_first_set = True

                    all_spine.append((item_id, opf_href, idx, label, page_title))
                    # 다중 헤딩 sub-navPoint 등록
                    if _sub_anchors_for_this:
                        _sub_navs[item_id] = list(_sub_anchors_for_this)
                    kept_in_book += 1

                # ── 권 처리 완료: 한 줄 요약 ──────────────────
                _stem = Path(epub_path).stem
                _log_name = label if re.search(r'\d', label) else _stem
                _G   = f'color:{C["text3"]};font-size:11px;'
                _num = f'[{idx+1}/{total}]'
                if kept_in_book == 0:
                    self.log_signal.emit(
                        f'<span style="{_G}">{_num} 📖  {_log_name}  ⚠ 본문 없음</span>',
                        "html")
                else:
                    _cr = f'  🧹 판권·커버 {_cnt_removed}개 제거' if _cnt_removed > 0 else ''
                    self.log_signal.emit(
                        f'<span style="{_G}">{_num} 📖  {_log_name}{_cr}  완료 ✓</span>',
                        "html")
                for w in _warn_msgs:
                    self.log(f"  ⚠ {w}", "warn")

            # ── 권+화 그룹화 사전 계산 ───────────────────────
            # 파일명에 'N권 M화' 패턴이 있는 epub들을 권 단위로 그룹화
            # (예: 1권 1화, 1권 2화 → '1권' 부모 노드 + '1화', '2화' 자식)
            from collections import OrderedDict as _OD
            _filename_toc_labels: dict = {} # ei → 파일명 기반 목차 라벨 (낱펍 메타 오류 보정)
            for _ei, _lbl, _fh in toc_entries:
                _filename_toc_labels[_ei] = _toc_label_from_filename(Path(self.epub_files[_ei]).name)
            _force_filename_toc = _is_consistent_filename_label_set(list(_filename_toc_labels.values()))
            if _core_plan_volume_chapter_toc:
                _vc_plan = _core_plan_volume_chapter_toc(
                    toc_entries,
                    self.epub_files,
                    filename_toc_labels=_filename_toc_labels,
                    flat_toc=self.flat_toc,
                    force_filename_toc=_force_filename_toc,
                )
                _vc_groups = _OD((k, list(v)) for k, v in _vc_plan.groups.items())
                _vc_ungrouped = list(_vc_plan.ungrouped)
                _vc_filename_chap = dict(_vc_plan.filename_chapter_numbers)
                _vc_filename_vol = dict(_vc_plan.filename_volume_numbers)
                _chap_only_filename = dict(_vc_plan.chapter_only_filename_numbers)
                _filename_toc_labels = dict(_vc_plan.filename_toc_labels)
                _force_filename_toc = _vc_plan.force_filename_toc
                _vol_chap_grouping = _vc_plan.use_grouping
                _vol_chap_flat = _vc_plan.use_flat
            else:
                _vc_groups: _OD = _OD()       # {vol_num: [(ei, lbl, first_href, chap_num), ...]}
                _vc_ungrouped: list = []       # 권+화 패턴이 없는 entry
                _vc_filename_chap: dict = {}   # ei → chap_num (권+화 패턴; flat 모드 라벨링용)
                _vc_filename_vol: dict = {}    # ei → vol_num
                _chap_only_filename: dict = {} # ei → chap_num (파일명에 '화'만 있는 경우 모두; ptitle 보강용)
                for _ei, _lbl, _fh in toc_entries:
                    _stem_vc = Path(self.epub_files[_ei]).stem
                    _vm_fn = re.search(r'(\d+)\s*권', _stem_vc)
                    _cm_fn = re.search(r'(\d+)\s*화', _stem_vc)
                    if _cm_fn:
                        _chap_only_filename[_ei] = int(_cm_fn.group(1))
                    if _vm_fn and _cm_fn:
                        _vn_fn = int(_vm_fn.group(1))
                        _cn_fn = int(_cm_fn.group(1))
                        _vc_filename_chap[_ei] = _cn_fn
                        _vc_filename_vol[_ei] = _vn_fn
                        _vc_groups.setdefault(_vn_fn, []).append((_ei, _lbl, _fh, _cn_fn))
                    else:
                        _vc_ungrouped.append((_ei, _lbl, _fh))
                _vol_chap_grouping = (
                    not self.flat_toc
                    and any(len(_g) >= 2 for _g in _vc_groups.values())
                )
                _vol_chap_flat = (
                    self.flat_toc
                    and len(_vc_filename_chap) >= 1
                )

            def _ensure_chap_prefix(ei: int, title: str, label_hint: str = '') -> str:
                """파일명에 'N화'가 있고 title에 그 화수가 없으면 'N화 ' 접두사 추가.
                예) ei의 파일명이 '... 1화.epub'이고 ptitle이 '프롤로그'면
                    → '1화 프롤로그'."""
                if ei not in _chap_only_filename:
                    return title
                _n = _chap_only_filename[ei]
                if not title:
                    return f'{_n}화'
                # 이미 같은 화수가 들어있으면 그대로
                if re.search(rf'(?<!\d){_n}\s*화', title):
                    return title
                # 다른 화수 패턴이 이미 있으면 그대로 (덮어쓰지 않음)
                if re.search(r'\d+\s*화', title):
                    return title
                # 작품명/권명 같은 상위 라벨(시리즈명)에는 접두사 강제 부여하지 않음.
                if label_hint:
                    _t_norm = _normalize_title(re.sub(r'\s+', ' ', title)).strip().lower()
                    _l_norm = _normalize_title(re.sub(r'\s+', ' ', label_hint)).strip().lower()
                    _l_norm = re.sub(r'^\[[^\]]+\]\s*', '', _l_norm).strip()
                    _l_norm = _strip_trailing_volume_suffix(_l_norm).strip().lower()
                    if _l_norm and (_t_norm == _l_norm or _t_norm.startswith(_l_norm + ' ')):
                        return title
                return f'{_n}화 {title}'.strip()

            def _prefer_filename_title(ei: int, title: str) -> str:
                if self.page_title_overrides:
                    return title
                return _prefer_filename_toc_title(
                    _filename_toc_labels.get(ei, ''), title,
                    force_filename=_force_filename_toc)
            def _vol_lbl_for(vn, sample_lbl):
                """권 부모 노드 라벨 — sample_lbl(첫 epub의 lbl)에서 화 잔류분 제거,
                권 번호 누락 시 보강."""
                if _core_volume_parent_label:
                    return _core_volume_parent_label(vn, sample_lbl)
                _v = re.sub(r'\s*제?\s*\d+\s*화.*$', '', sample_lbl).strip()
                if not re.search(rf'(?<!\d){vn}\s*권', _v):
                    _v = re.sub(r'\s*\d+\s*권\s*$', '', _v).strip()
                    _v = f'{_v} {vn}권'.strip()
                return _v

            def _flat_lbl_for(ei, lbl):
                lbl = _filename_toc_labels.get(ei, '') or lbl
                """flat 모드용 라벨 — 권+화 패턴 epub은 라벨 + N화 형식으로 보강."""
                if _core_flat_volume_chapter_label:
                    return _core_flat_volume_chapter_label(lbl, _vc_filename_chap.get(ei))
                if ei in _vc_filename_chap and not re.search(r'\d+\s*화', lbl):
                    return f'{lbl} {_vc_filename_chap[ei]}화'.strip()
                return lbl

            # 7. 목차 페이지 (선택)
            if self.add_toc and toc_entries:
                _toc_page_items = []
                if _vol_chap_grouping:
                    # ungrouped 먼저
                    for _ei_h, _lbl_h, _fh_h in _vc_ungrouped:
                        _toc_page_items.append({"href": _fh_h, "label": _lbl_h})
                    # 권 그룹
                    for _vn_h in sorted(_vc_groups.keys()):
                        _entries_h = sorted(_vc_groups[_vn_h], key=lambda e: e[3])
                        _vlbl_h = _vol_lbl_for(_vn_h, _entries_h[0][1])
                        _children_h = []
                        for _ei_c, _lbl_c, _fh_c, _cn_c in _entries_h:
                            _children_h.append({"href": _fh_c, "label": f"{_cn_c}화"})
                        _toc_page_items.append({
                            "href": _entries_h[0][2],
                            "label": _vlbl_h,
                            "children": tuple(_children_h),
                        })
                elif _vol_chap_flat:
                    # flat 모드 + 권+화 패턴: 라벨 + 화 보강
                    for _ei_f, _lbl_f, _fh_f in toc_entries:
                        _toc_page_items.append({
                            "href": _fh_f,
                            "label": _flat_lbl_for(_ei_f, _lbl_f),
                        })
                else:
                    for _ei_n, lbl, opf_href in toc_entries:
                        # 다중 헤딩 sub-nav 분할: 첫 spine item에 sub_navs 있으면 펼침
                        _first_iid_h = None
                        for _iid_h, _href_h, _ei_h, _, _ in all_spine:
                            if _ei_h == _ei_n and _href_h == opf_href:
                                _first_iid_h = _iid_h
                                break
                        if _first_iid_h and _first_iid_h in _sub_navs and len(_sub_navs[_first_iid_h]) >= 2:
                            _subs_h = _sub_navs[_first_iid_h]
                            for _si_h, (_anchor_h, _stitle_h) in enumerate(_subs_h):
                                _suri_h = opf_href if _si_h == 0 else f'{opf_href}#{_anchor_h}'
                                _stitle_h = _ensure_chap_prefix(_ei_n, _stitle_h, lbl)
                                if self.flat_toc:
                                    _stitle_h = _compact_chapter_label(_stitle_h)
                                _toc_page_items.append({"href": _suri_h, "label": _stitle_h})
                        else:
                            _toc_lbl = _compact_chapter_label(lbl) if self.flat_toc else lbl
                            _toc_page_items.append({"href": opf_href, "label": _toc_lbl})
                if _core_render_toc_page_document:
                    toc_html = _core_render_toc_page_document(
                        _toc_page_items,
                        bg=C["bg"],
                        text=C["text"],
                        accent=C["accent"],
                    )
                else:
                    toc_html = (
                        '<?xml version="1.0" encoding="utf-8"?>'
                        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" '
                        '"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
                        '<html xmlns="http://www.w3.org/1999/xhtml">'
                        '<head><title>목차</title>'
                        f'<style>'
                        f'body{{font-family:sans-serif;padding:2em;'
                        f'background:{C["bg"]};color:{C["text"]}}}'
                        f'h1{{font-size:1.3em;color:{C["accent"]};margin-bottom:1em}}'
                        f'ol{{padding-left:1.5em}}li{{margin:.5em 0}}'
                        f'ul{{padding-left:1.5em;list-style:disc}}'
                        f'a{{color:{C["accent"]};text-decoration:none}}'
                        f'a:hover{{text-decoration:underline}}'
                        f'</style></head><body><h1>📚 목차</h1><ol>\n'
                    )
                    for _item_h in _toc_page_items:
                        _href_h = _item_h.get("href", "")
                        _label_h = _item_h.get("label", "")
                        _children_h = _item_h.get("children", ())
                        if _children_h:
                            toc_html += (
                                f'<li><a href="{hm.escape(_href_h)}">'
                                f'{hm.escape(_label_h)}</a><ul>\n')
                            for _child_h in _children_h:
                                toc_html += (
                                    f'<li><a href="{hm.escape(_child_h.get("href", ""))}">'
                                    f'{hm.escape(_child_h.get("label", ""))}</a></li>\n')
                            toc_html += '</ul></li>\n'
                        else:
                            toc_html += (
                                f'<li><a href="{hm.escape(_href_h)}">'
                                f'{hm.escape(_label_h)}</a></li>\n')
                    toc_html += '</ol></body></html>'
                Path(os.path.join(text_base, "toc_page.xhtml")).write_text(
                    toc_html, encoding="utf-8")
                all_manifest["toc-page"] = (
                    "OEBPS/Text/toc_page.xhtml", "application/xhtml+xml")
                # spine 맨 앞(cover 다음)에 삽입
                ins = 1 if all_spine and all_spine[0][0] == "cover-html" else 0
                all_spine.insert(ins, ("toc-page", "OEBPS/Text/toc_page.xhtml", -1, "목차", ""))

            # 스킵된 표지/판권 페이지가 참조하던 이미지가 파일만 남는 경우가 있어
            # 최종 XHTML/CSS에서 실제 참조되는 이미지만 패키징한다.
            try:
                if _core_referenced_image_basenames and _core_plan_unreferenced_image_prune:
                    _ref_sources = []
                    for _iid_r, _href_r, _, _, _ in all_spine:
                        _xh_path = os.path.join(out_dir, _href_r.replace('/', os.sep))
                        if os.path.exists(_xh_path):
                            _ref_sources.append(
                                Path(_xh_path).read_text(encoding='utf-8', errors='replace'))
                    for _css_path in Path(styles_base).rglob('*.css'):
                        _ref_sources.append(
                            _css_path.read_text(encoding='utf-8', errors='replace'))
                    _prune_plan = _core_plan_unreferenced_image_prune(
                        all_manifest,
                        _core_referenced_image_basenames(_ref_sources),
                    )
                    for _mid_r in _prune_plan.remove_manifest_ids:
                        all_manifest.pop(_mid_r, None)
                    for _img_path_r in Path(images_dir).rglob('*'):
                        if not _img_path_r.is_file():
                            continue
                        _bn_r = _img_path_r.name.lower()
                        if (
                            _bn_r in _prune_plan.referenced_basenames
                            or _bn_r in _prune_plan.protected_basenames
                        ):
                            continue
                        _img_path_r.unlink(missing_ok=True)
                else:
                    from urllib.parse import unquote as _url_unquote_refs
                    _img_refs: set[str] = set()
                    _ref_pat = re.compile(
                        r'(?:src|href)=["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp))["\']',
                        re.IGNORECASE)
                    _css_url_pat = re.compile(
                        r'url\(["\']?([^"\')]+\.(?:jpg|jpeg|png|gif|webp))["\']?\)',
                        re.IGNORECASE)

                    def _add_img_ref(_ref: str):
                        _ref = _url_unquote_refs(
                            _ref.split('#', 1)[0].split('?', 1)[0])
                        _bn = Path(_ref.replace('\\', '/')).name.lower()
                        if _bn:
                            _img_refs.add(_bn)

                    for _iid_r, _href_r, _, _, _ in all_spine:
                        _xh_path = os.path.join(out_dir, _href_r.replace('/', os.sep))
                        if not os.path.exists(_xh_path):
                            continue
                        _raw_r = Path(_xh_path).read_text(encoding='utf-8', errors='replace')
                        for _m_r in _ref_pat.finditer(_raw_r):
                            _add_img_ref(_m_r.group(1))
                        for _m_r in _css_url_pat.finditer(_raw_r):
                            _add_img_ref(_m_r.group(1))

                    for _css_path in Path(styles_base).rglob('*.css'):
                        _raw_css_r = _css_path.read_text(encoding='utf-8', errors='replace')
                        for _m_r in _css_url_pat.finditer(_raw_css_r):
                            _add_img_ref(_m_r.group(1))

                    _cover_basenames = {
                        Path(_href_c.replace('\\', '/')).name.lower()
                        for _mid_c, (_href_c, _mt_c) in all_manifest.items()
                        if _mid_c == 'cover-image'
                    }
                    _remove_manifest_ids = []
                    for _mid_r, (_href_r, _mt_r) in list(all_manifest.items()):
                        if not str(_mt_r).lower().startswith('image/'):
                            continue
                        _bn_r = Path(_href_r.replace('\\', '/')).name.lower()
                        if _mid_r == 'cover-image' or _bn_r in _img_refs:
                            continue
                        _remove_manifest_ids.append(_mid_r)
                    for _mid_r in _remove_manifest_ids:
                        all_manifest.pop(_mid_r, None)

                    for _img_path_r in Path(images_dir).rglob('*'):
                        if not _img_path_r.is_file():
                            continue
                        _bn_r = _img_path_r.name.lower()
                        if _bn_r in _img_refs or _bn_r in _cover_basenames:
                            continue
                        _img_path_r.unlink(missing_ok=True)
            except Exception:
                pass

            self.progress_signal.emit(86)
            uid = str(uuid.uuid4())
            epub_merge_id = f"epub-merge-{uid}"

            # ── OPF ──────────────────────────────────────────
            # creator 비어있으면 파일명 [작가명] 또는 _작가__ 패턴에서 추출
            if not creator:
                if _core_infer_creator_from_title_or_filename:
                    creator = _core_infer_creator_from_title_or_filename(
                        self.title,
                        Path(self.epub_files[0]).stem if self.epub_files else "",
                    )
                else:
                    _m = re.match(r'^\[([^\]]+)\]', self.title)
                    if _m: creator = _m.group(1).strip()
            if not creator and not _core_infer_creator_from_title_or_filename:
                _fn0 = Path(self.epub_files[0]).stem
                _fm = re.match(r'^_([^_]{1,10})__', _fn0)
                if _fm: creator = _fm.group(1).strip()
            if _core_render_merge_opf:
                opf_text = _core_render_merge_opf(
                    self.title,
                    epub_merge_id,
                    all_manifest,
                    [iid for iid, _, _, _, _ in all_spine],
                    creator=creator,
                    publisher=publisher,
                    language=language,
                )
            else:
                has_cover = 'cover-image' in all_manifest
                opf_lines = [
                    '<?xml version="1.0" encoding="utf-8"?>',
                    '<package unique-identifier="uuid_id" version="2.0"'
                    ' xmlns="http://www.idpf.org/2007/opf">',
                    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">',
                    f'    <dc:title>{hm.escape(self.title)}</dc:title>',
                ]
                if creator:
                    opf_lines.append(f'    <dc:creator>{hm.escape(creator)}</dc:creator>')
                if publisher:
                    opf_lines.append(f'    <dc:publisher>{hm.escape(publisher)}</dc:publisher>')
                opf_lines += [
                    f'    <dc:language>{hm.escape(language)}</dc:language>',
                    f'    <dc:identifier id="uuid_id">{epub_merge_id}</dc:identifier>',
                ]
                if has_cover:
                    opf_lines.append('    <meta name="cover" content="cover-image"/>')
                # calibre 시리즈 메타: 제목에서 권/화 범위 제거
                _series_name = re.sub(r'\s*\d+[-~]\d+\s*[권화부]?\s*$', '', self.title)
                _series_name = re.sub(r'\s*\d+\s*[권화부]\s*$', '', _series_name).strip()
                if _series_name:
                    opf_lines.append(f'    <meta name="calibre:series" content="{hm.escape(_series_name)}"/>')
                    opf_lines.append(f'    <meta name="calibre:series_index" content="1"/>')
                opf_lines += ['</metadata>', '<manifest>']
                opf_lines.append(
                    '    <item id="ncx" href="toc.ncx"'
                    ' media-type="application/x-dtbncx+xml"/>')
                for iid, (href, mt) in all_manifest.items():
                    sid = re.sub(r'[^a-zA-Z0-9_\-]', '_', iid)
                    opf_lines.append(
                        f'    <item id="{sid}" href="{href}" media-type="{mt}"/>')
                opf_lines.append('</manifest>')
                opf_lines.append('<spine toc="ncx">')
                for iid, _, _, _, _ in all_spine:
                    sid = re.sub(r'[^a-zA-Z0-9_\-]', '_', iid)
                    opf_lines.append(f'    <itemref idref="{sid}"/>')
                opf_lines.append('</spine>')
                if has_cover:
                    opf_lines += [
                        '<guide>',
                        '    <reference type="cover" title="Cover" href="OEBPS/Text/cover.xhtml"/>',
                        '</guide>',
                    ]
                opf_lines.append('</package>')
                opf_text = "\n".join(opf_lines)
            Path(os.path.join(out_dir, "content.opf")).write_text(
                opf_text, encoding="utf-8")

            # ── NCX ──────────────────────────────────────────
            def _normalize_nav_label_text(text: str) -> str:
                t = _normalize_title(text or "").strip()
                # "1화 #1." / "제1화 #1. ..." 같은 중복 회차 표기를 한 번만 남긴다.
                m = re.match(
                    r'^(?:제\s*)?(\d+)\s*화\s*[#＃]\s*\1\s*[.\)]?\s*(.*)$',
                    t,
                    re.IGNORECASE,
                )
                if m:
                    tail = (m.group(2) or "").strip()
                    return f"{int(m.group(1))}화 {tail}".strip() if tail else f"{int(m.group(1))}화"
                return t

            def _is_noise_nav_label(text: str) -> bool:
                t = _normalize_nav_label_text(text or "")
                if not t:
                    return True
                if re.match(r'^[≫▶▷▸▹►»]+', t):
                    return True
                if re.match(r'^\d+\s*[.)]\s*$', t):
                    return True
                if re.match(r'^\d+\s*$', t):
                    return True
                return False

            _seen_nav_pairs: set[tuple[str, str]] = set()
            def _allow_nav(label: str, src: str) -> bool:
                key = (re.sub(r'\s+', ' ', _normalize_nav_label_text(label)).strip().lower(), (src or '').strip())
                if not key[0] or not key[1]:
                    return False
                if _is_noise_nav_label(key[0]):
                    return False
                if key in _seen_nav_pairs:
                    return False
                _seen_nav_pairs.add(key)
                return True

            ncx_lines = [
                '<?xml version="1.0" encoding="utf-8"?>',
                '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">',
                '<head>',
                f'    <meta name="dtb:uid" content="{epub_merge_id}"/>',
                '    <meta name="dtb:depth" content="2"/>',
                '    <meta name="dtb:totalPageCount" content="0"/>',
                '    <meta name="dtb:maxPageNumber" content="0"/>',
                '</head>',
                f'<docTitle><text>{hm.escape(self.title)}</text></docTitle>',
                '<navMap>',
            ]
            ni = 1
            # 표지 navPoint
            _cover_nav_src = next((href for _iid, href, *_ in all_spine if _iid == "cover-html"), "")
            if _cover_nav_src:
                if _CoreNcxNavEntry and _core_render_ncx_nav_point:
                    ncx_lines += _core_render_ncx_nav_point(
                        _CoreNcxNavEntry(
                            f"navPoint-{ni}",
                            "표지",
                            _cover_nav_src,
                            ni,
                        ),
                        indent=8,
                    )
                else:
                    ncx_lines += [
                        f'        <navPoint id="navPoint-{ni}" playOrder="{ni}">',
                        f'            <navLabel><text>표지</text></navLabel>',
                        f'            <content src="{_cover_nav_src}"/>',
                        f'        </navPoint>',
                    ]
                ni += 1

            # 각 화별 navPoint: toc_entries 기준
            # 다권 여부 판정: label 중 권/부/외전 번호가 있는 것이 2개 이상
            # flat_toc=True 시 강제 단일화 (권별 상위노드 생성 안 함)
            # 모든 epub이 단일 페이지(화 단위 연재)면 권별 계층 미생성 → flat
            # multi_vol: 기존 다권 경로 — 권+화 그룹화가 이미 담당하면 비활성
            if _core_should_use_multi_volume_ncx:
                multi_vol = _core_should_use_multi_volume_ncx(
                    toc_entries,
                    (_ei for _, _, _ei, _, _ in all_spine),
                    flat_toc=self.flat_toc,
                    volume_chapter_grouping=_vol_chap_grouping,
                )
            else:
                _pages_per_epub: dict = {}
                for _, _, _ei, _, _ in all_spine:
                    _pages_per_epub[_ei] = _pages_per_epub.get(_ei, 0) + 1
                _all_single_page = len(_pages_per_epub) > 1 and all(
                    v == 1 for v in _pages_per_epub.values())
                multi_vol = (
                    sum(1 for _, lbl, _ in toc_entries if _has_vol_marker(lbl)) >= 2
                    and not self.flat_toc
                    and not _all_single_page
                    and not _vol_chap_grouping
                )

            book_idx = 0
            if _vol_chap_grouping:
                # ── 권+화 그룹화: 권 부모 + 화 자식 ──────────────
                if (
                    _core_build_volume_chapter_ncx_entries
                    and _core_render_ncx_nav_point
                ):
                    _ncx_build = _core_build_volume_chapter_ncx_entries(
                        _vc_ungrouped,
                        _vc_groups,
                        start_play_order=ni,
                        start_book_index=book_idx,
                    )
                    for _entry in _ncx_build.entries:
                        ncx_lines += _core_render_ncx_nav_point(_entry, indent=8)
                    ni = _ncx_build.next_play_order
                    book_idx = _ncx_build.next_book_index
                else:
                    # ungrouped (외전, 작가노트 등) 먼저 flat 렌더
                    for _ei_u, _lbl_u, _fh_u in _vc_ungrouped:
                        book_idx += 1
                        ncx_lines += [
                            f'        <navPoint id="book{book_idx:03d}" playOrder="{ni}">',
                            f'            <navLabel><text>{hm.escape(_lbl_u)}</text></navLabel>',
                            f'            <content src="{_fh_u}"/>',
                            f'        </navPoint>',
                        ]
                        ni += 1
                    # 권 번호 오름차순 → 부모 노드 + 화 자식
                    for _vn_g in sorted(_vc_groups.keys()):
                        _entries_g = sorted(_vc_groups[_vn_g], key=lambda e: e[3])
                        book_idx += 1
                        _vol_lbl_g = _vol_lbl_for(_vn_g, _entries_g[0][1])
                        ncx_lines += [
                            f'        <navPoint id="book{book_idx:03d}" playOrder="{ni}">',
                            f'            <navLabel><text>{hm.escape(_vol_lbl_g)}</text></navLabel>',
                            f'            <content src="{_entries_g[0][2]}"/>',
                        ]
                        ni += 1
                        for _ei_c, _lbl_c, _fh_c, _cn_c in _entries_g:
                            book_idx += 1
                            ncx_lines += [
                                f'            <navPoint id="book{book_idx:03d}" playOrder="{ni}">',
                                f'                <navLabel><text>{_cn_c}화</text></navLabel>',
                                f'                <content src="{_fh_c}"/>',
                                f'            </navPoint>',
                            ]
                            ni += 1
                        ncx_lines.append(f'        </navPoint>')
            else:
                for _toc_epub_idx, lbl, first_href in toc_entries:
                    book_idx += 1
                    # ② epub_idx 기준으로 필터: 동일 라벨이 여러 권에 있어도 섞이지 않음
                    book_pages = [
                        (iid, href, ptitle)
                        for iid, href, ei, l, ptitle in all_spine if ei == _toc_epub_idx
                    ]
                    if not book_pages:
                        continue

                    if multi_vol:
                        # ── 다권: 상위노드(label 풀네임) + 하위노드(화 제목) ──
                        # 권 번호 없는 특수권(작가노트 등)도 상위노드 반드시 생성
                        if _core_build_multi_volume_ncx_entry and _core_render_ncx_nav_point:
                            _book_pages_mv = []
                            for iid, href, ptitle in book_pages:
                                # 첫 페이지가 상위노드와 src 동일하면 중복 — 건너뜀
                                # title 없는 파트(* * * 이어지는 파일)도 NCX 생략
                                if not ptitle:
                                    continue
                                ptitle = _prefer_filename_title(_toc_epub_idx, ptitle)
                                ptitle = _ensure_chap_prefix(_toc_epub_idx, ptitle, lbl)
                                _book_pages_mv.append((iid, href, ptitle))
                            _ncx_build = _core_build_multi_volume_ncx_entry(
                                lbl,
                                first_href,
                                _book_pages_mv,
                                book_index=book_idx,
                                start_play_order=ni,
                            )
                            for _entry in _ncx_build.entries:
                                ncx_lines += _core_render_ncx_nav_point(_entry, indent=8)
                            ni = _ncx_build.next_play_order
                            book_idx = _ncx_build.next_book_index
                        else:
                            ncx_lines += [
                                f'        <navPoint id="book{book_idx:03d}" playOrder="{ni}">',
                                f'            <navLabel><text>{hm.escape(lbl)}</text></navLabel>',
                                f'            <content src="{first_href}"/>',
                            ]
                            ni += 1
                            for iid, href, ptitle in book_pages:
                                # 첫 페이지가 상위노드와 src 동일하면 중복 — 건너뜀
                                # title 없는 파트(* * * 이어지는 파일)도 NCX 생략
                                if not ptitle:
                                    continue
                                ptitle = _prefer_filename_title(_toc_epub_idx, ptitle)
                                ptitle = _ensure_chap_prefix(_toc_epub_idx, ptitle, lbl)
                                ptitle = _normalize_nav_label_text(ptitle)
                                if not _allow_nav(ptitle, href):
                                    continue
                                ncx_lines += [
                                    f'            <navPoint id="book{book_idx:03d}_{iid}" playOrder="{ni}">',
                                    f'                <navLabel><text>{hm.escape(ptitle)}</text></navLabel>',
                                    f'                <content src="{href}"/>',
                                    f'            </navPoint>',
                                ]
                                ni += 1
                            ncx_lines.append(f'        </navPoint>')
                    elif _vol_chap_flat and _toc_epub_idx in _vc_filename_chap:
                        # ── flat 모드 + 권+화 패턴: epub당 1엔트리, '라벨 + N화' ──
                        _flat_lbl_e = _flat_lbl_for(_toc_epub_idx, lbl)
                        if _CoreNcxNavEntry and _core_render_ncx_nav_point:
                            ncx_lines += _core_render_ncx_nav_point(
                                _CoreNcxNavEntry(
                                    f"book{book_idx:03d}",
                                    _flat_lbl_e,
                                    first_href,
                                    ni,
                                ),
                                indent=8,
                            )
                        else:
                            ncx_lines += [
                                f'        <navPoint id="book{book_idx:03d}" playOrder="{ni}">',
                                f'            <navLabel><text>{hm.escape(_flat_lbl_e)}</text></navLabel>',
                                f'            <content src="{first_href}"/>',
                                f'        </navPoint>',
                            ]
                        ni += 1
                    else:
                        # ── 단권/화 연재: flat하게 나열 ──
                        # ptitle 있는 항목이 있으면 없는 항목(주의사항 등) 제외
                        # 모두 없으면 첫 번째만 유지 (중복 방지)
                        _any_ptitle = any(ptitle for _, _, ptitle in book_pages)
                        _first_done = False
                        for iid, href, ptitle in book_pages:
                            # ── 한 xhtml에 여러 헤딩 → sub-navPoint 분할 ──
                            # 예) 538356_1.epub: '솔저 오브 아포칼립스' / 'Prologue' / '1화. 새로운 시작(1)'
                            if iid in _sub_navs and len(_sub_navs[iid]) >= 2:
                                _subs = _sub_navs[iid]
                                for _si, (_anchor, _stitle) in enumerate(_subs):
                                    _suri = href if _si == 0 else f'{href}#{_anchor}'
                                    # 파일명 화수(예: 1화.epub)를 서브헤딩에도 일관 반영
                                    _stitle = _prefer_filename_title(_toc_epub_idx, _stitle)
                                    _stitle = _ensure_chap_prefix(_toc_epub_idx, _stitle, lbl)
                                    _stitle = _normalize_nav_label_text(_stitle)
                                    if self.flat_toc:
                                        _stitle = _compact_chapter_label(_stitle)
                                    if not _allow_nav(_stitle, _suri):
                                        continue
                                    if _CoreNcxNavEntry and _core_render_ncx_nav_point:
                                        ncx_lines += _core_render_ncx_nav_point(
                                            _CoreNcxNavEntry(
                                                f"book{book_idx:03d}_{iid}_{_si:02d}",
                                                _stitle,
                                                _suri,
                                                ni,
                                            ),
                                            indent=8,
                                        )
                                    else:
                                        ncx_lines += [
                                            f'        <navPoint id="book{book_idx:03d}_{iid}_{_si:02d}" playOrder="{ni}">',
                                            f'            <navLabel><text>{hm.escape(_stitle)}</text></navLabel>',
                                            f'            <content src="{_suri}"/>',
                                            f'        </navPoint>',
                                        ]
                                    ni += 1
                                _first_done = True  # 이 epub은 sub-nav로 처리됨
                                continue

                            # 순수 화수("N화")는 generic이어도 유효한 제목으로 사용
                            _is_pure_ep = bool(re.match(r'^\d+\s*[화권]\s*$', ptitle)) if ptitle else False
                            # "Chapter N" 등 숫자는 있지만 화/권 없는 단행본 챕터 제목 → 실제 제목으로 사용
                            _is_non_ep_numbered = bool(ptitle and re.search(r'\d+', ptitle) and not re.search(r'\d+\s*[화권]', ptitle))
                            title = (lbl if (not ptitle or (_is_generic_ncx_label(ptitle) and not _is_pure_ep and not _is_non_ep_numbered)) else ptitle)
                            # ptitle이 lbl의 앞부분인 경우(삽화/번외 등 suffix 누락) → lbl 사용
                            _lbl_core = re.sub(r'^\[[^\]]*\]\s*', '', lbl).strip()
                            if title == ptitle and ptitle and _lbl_core.startswith(ptitle):
                                title = _lbl_core
                            if not title:
                                continue
                            # ptitle 있는 항목이 있는데 이 항목엔 없으면 제외
                            if _any_ptitle and not ptitle:
                                continue
                            # 모두 ptitle 없으면 첫 번째만 (주의사항 중복 방지)
                            if not _any_ptitle:
                                if _first_done:
                                    continue
                                _first_done = True
                            # 파일명 화수(예: 1화.epub)를 각 챕터 라벨에 반영
                            # (예: ptitle '1장 ...' → '1화 1장 ...')
                            title = _prefer_filename_title(_toc_epub_idx, title)
                            title = _ensure_chap_prefix(_toc_epub_idx, title, lbl)
                            title = _normalize_nav_label_text(title)
                            if self.flat_toc:
                                title = _compact_chapter_label(title)
                            if not _allow_nav(title, href):
                                continue
                            if _CoreNcxNavEntry and _core_render_ncx_nav_point:
                                ncx_lines += _core_render_ncx_nav_point(
                                    _CoreNcxNavEntry(
                                        f"book{book_idx:03d}_{iid}",
                                        title,
                                        href,
                                        ni,
                                    ),
                                    indent=8,
                                )
                            else:
                                ncx_lines += [
                                    f'        <navPoint id="book{book_idx:03d}_{iid}" playOrder="{ni}">',
                                    f'            <navLabel><text>{hm.escape(title)}</text></navLabel>',
                                    f'            <content src="{href}"/>',
                                    f'        </navPoint>',
                                ]
                            ni += 1

            ncx_lines += ['</navMap>', '</ncx>']
            Path(os.path.join(out_dir, "toc.ncx")).write_text(
                "\n".join(ncx_lines), encoding="utf-8")

            # ── EPUB shell/package ───────────────────────────
            _core_write_epub_shell_files(out_dir, rootfile_path="content.opf")

            self.progress_signal.emit(93)

            # 타임스탬프 튜플 준비 (year, month, day, hour, min, sec)
            _ts = None
            if self.timestamp:
                y, mo, d = self.timestamp[:3]
                _ts = (y, mo, d, 0, 0, 0)
            _core_write_epub_directory_to_file(out_dir, self.output_path, timestamp=_ts)

            self.progress_signal.emit(100)
            self.log(f"✅ 완료: {self.output_path}", "ok")
            self.done_signal.emit(True, self.output_path)

        except Exception as e:
            import traceback; traceback.print_exc()
            self.log(_format_worker_error(e), "err")
            self.done_signal.emit(False, "")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _find_opf(self, base):
        from epub_binder_core.epub_io import find_extracted_opf_path
        return find_extracted_opf_path(base)

    def _parse_opf(self, opf_path):
        from epub_binder_core.epub_io import parse_legacy_merge_opf
        content = Path(opf_path).read_text(encoding="utf-8", errors="replace")
        opf_dir = os.path.dirname(opf_path)
        manifest, spine = parse_legacy_merge_opf(content)
        return manifest, spine, opf_dir

    def _parse_ncx(self, opf_dir):
        """toc.ncx 파싱 → (ncx_labels dict, doc_title str)."""
        from epub_binder_core.epub_io import parse_ncx_labels_from_opf_dir
        return parse_ncx_labels_from_opf_dir(opf_dir)


class TxtEpubWorker(QThread):
    """TXT → EPUB 변환 워커. jobs = [(txt_path, title, author, chapters), ...]"""
    log_signal      = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    done_signal     = pyqtSignal(int, int, str)   # ok_count, fail_count, last_dir

    def __init__(self, jobs, output_dir, cover_data=None, cover_ext='.jpg'):
        super().__init__()
        self.jobs = jobs
        self.output_dir = output_dir
        self.cover_data = cover_data
        self.cover_ext = cover_ext

    def run(self):
        ok, fail = 0, 0
        total = len(self.jobs)
        for idx, job in enumerate(self.jobs):
            normalized = None
            try:
                normalized = _core_normalize_txt_epub_job_v2(
                    job,
                    default_cover_data=self.cover_data,
                    default_cover_ext=self.cover_ext,
                )
                self.log_signal.emit(
                    f"📖 {Path(normalized.path).name} → 변환 중... ({len(normalized.chapters)} 챕터)",
                    "info")
                result = _core_write_txt_epub_job_v2(normalized, self.output_dir)
                self.log_signal.emit(
                    f"   ✅ 저장: {Path(result.output_path).name}  ({result.byte_count:,} bytes)", "ok")
                ok += 1
            except Exception as ex:
                if normalized is not None:
                    txt_path = normalized.path
                elif isinstance(job, dict):
                    txt_path = job.get('path', '')
                else:
                    txt_path = job[0] if job else ''
                self.log_signal.emit(
                    f"   ❌ 실패: {Path(txt_path).name} — {ex}", "err")
                fail += 1
            self.progress_signal.emit(int((idx + 1) / max(total, 1) * 100))
        self.done_signal.emit(ok, fail, str(self.output_dir))


class EpubTxtWorker(QThread):
    log_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    done_signal = pyqtSignal(int, int, str)

    def __init__(
        self,
        jobs,
        output_dir,
        remove_skip_pages: bool = True,
        strip_invisible: bool = True,
        cleanup_text: bool = True,
        indent_paragraphs: bool = False,
        combine_output: bool = False,
        combined_stem: str = "merged",
    ):
        super().__init__()
        self.jobs = jobs
        self.output_dir = output_dir
        self.remove_skip_pages = remove_skip_pages
        self.strip_invisible = strip_invisible
        self.cleanup_text = cleanup_text
        self.indent_paragraphs = indent_paragraphs
        self.combine_output = combine_output
        self.combined_stem = combined_stem

    def run(self):
        ok, fail = 0, 0
        total = len(self.jobs)
        options = _CoreTextOutputOptions(
            remove_skip_pages=self.remove_skip_pages,
            strip_invisible=self.strip_invisible,
            cleanup_text=self.cleanup_text,
            indent_paragraphs=self.indent_paragraphs,
        )

        if self.combine_output:
            try:
                sorted_jobs = sorted(
                    self.jobs,
                    key=lambda path: natural_sort_key(Path(path).name),
                )
                self.log_signal.emit(f"🧹 {total}개 파일 하나로 합치는 중...", "info")
                result = _core_write_combined_text_output_from_paths_v2(
                    sorted_jobs,
                    self.output_dir,
                    options,
                    output_stem=self.combined_stem,
                    skip_page_detector=is_skip_page,
                )
                self.log_signal.emit(f"   ✅ 저장: {Path(result.output_path).name}", "ok")
                ok += 1
            except Exception as ex:
                self.log_signal.emit(f"   ❌ 실패: 텍스트 합치기 - {ex}", "err")
                fail += 1
            self.progress_signal.emit(100)
            self.done_signal.emit(ok, fail, str(self.output_dir))
            return

        for idx, src_path in enumerate(self.jobs):
            try:
                src_name = Path(src_path).name
                src_ext = Path(src_path).suffix.lower()
                if src_ext == ".txt":
                    self.log_signal.emit(f"🧹 {src_name} 정리 중...", "info")
                else:
                    self.log_signal.emit(f"📖 {src_name} 텍스트 추출 중...", "info")
                result = _core_write_text_output_from_path_v2(
                    src_path,
                    self.output_dir,
                    options,
                    skip_page_detector=is_skip_page,
                )
                self.log_signal.emit(f"   ✅ 저장: {Path(result.output_path).name}", "ok")
                ok += 1
            except Exception as ex:
                self.log_signal.emit(f"   ❌ 실패: {Path(src_path).name} - {ex}", "err")
                fail += 1

            self.progress_signal.emit(int((idx + 1) / max(total, 1) * 100))

        self.done_signal.emit(ok, fail, str(self.output_dir))


class NaverSeriesFetchThread(QThread):
    """네이버 시리즈 productNo로 표지 이미지를 다운로드하는 백그라운드 스레드."""
    progress = pyqtSignal(str)                    # 상태 메시지
    finished = pyqtSignal(bytes, str, str, str)   # (이미지 데이터, 확장자, 제목, 작가)
    failed   = pyqtSignal(str)                    # 오류 메시지

    def __init__(self, product_no: str, nid_aut: str, nid_ses: str):
        super().__init__()
        self.product_no = product_no
        self.nid_aut    = nid_aut
        self.nid_ses    = nid_ses

    def run(self):
        if not (_core_fetch_naver_series_cover and _CoreNaverSeriesCookies):
            self.failed.emit("오류: 네이버 시리즈 core fetch를 사용할 수 없습니다.")
            return

        try:
            result = _core_fetch_naver_series_cover(
                self.product_no,
                _CoreNaverSeriesCookies(nid_aut=self.nid_aut, nid_ses=self.nid_ses),
                progress=self.progress.emit,
            )
            kb = len(result.cover_bytes) // 1024
            filename = result.source_url.split('/')[-1] if result.source_url else "cover"
            self.progress.emit(
                f"✅ 완료: {kb:,} KB ({filename})"
                + (f" | 작가: {result.author}" if result.author else "")
            )
            ext = result.ext or "jpg"
            if not ext.startswith('.'):
                ext = f".{ext}"
            self.finished.emit(result.cover_bytes, ext, result.title, result.author)
        except Exception as ex:
            if _core_format_naver_fetch_error:
                self.failed.emit(_core_format_naver_fetch_error(ex))
            else:
                self.failed.emit(_format_worker_error(ex))


__all__ = [
    "ScanWorker",
    "StripOnlyWorker",
    "MergeWorker",
    "TxtEpubWorker",
    "EpubTxtWorker",
    "NaverSeriesFetchThread",
]
