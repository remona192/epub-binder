# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from PyQt6.QtGui import QPixmap

from epub_binder_app.settings import APP_COLORS as C
from epub_binder_app.ui.helpers import mk_btn, mk_lbl, natural_sort_key
from epub_binder_app.ui.style import CHECK_SVG_PATH as _check_svg_path
from epub_binder_app.workers import NaverSeriesFetchThread
from epub_binder_core.cover import extract_cover_candidates as _core_extract_cover_candidates
from epub_binder_core.naver_series import parse_product_no as _core_parse_product_no


def extract_cover_candidates(epub_bytes: bytes, include_all_images: bool = False):
    return _core_extract_cover_candidates(
        epub_bytes,
        include_all_images=include_all_images,
        sort_key=natural_sort_key,
    )

class TxtPreviewDialog(QDialog):
    """챕터 목록 미리보기 + 제목 편집 + 병합/삭제."""

    def __init__(self, file_dict, parent=None, detect_fn=None):
        super().__init__(parent)
        self.setWindowTitle(f"챕터 미리보기 — {Path(file_dict['path']).name}")
        self.resize(520, 560)
        self._chapters    = [(t, list(ls)) for t, ls in file_dict['chapters']]
        self._raw_text    = file_dict.get('raw_text', '')
        self._detect_fn   = detect_fn  # _txt_detect(text, force_subtitle_style=...)

        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(8, 8, 8, 8)

        # 메타데이터
        meta = QHBoxLayout(); meta.setSpacing(6)
        meta.addWidget(QLabel("제목"))
        self.title_edit = QLineEdit(file_dict['title']); meta.addWidget(self.title_edit, 2)
        meta.addWidget(QLabel("작가"))
        self.author_edit = QLineEdit(file_dict['author']); meta.addWidget(self.author_edit, 1)
        root.addLayout(meta)

        # 챕터 테이블 — [제목, 본문길이] (소제목 열 제거 → 버튼 행 체크박스로 이동)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            ["챕터 제목 (더블클릭 편집)", "본문 길이"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)   # 제목 열 자동 채움
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        hdr.setStretchLastSection(False)
        hdr.setMinimumSectionSize(50)
        self.table.setColumnWidth(1, 90)
        # 좌측 연번(수직 헤더)
        vh = self.table.verticalHeader()
        vh.setStyleSheet(
            "QHeaderView::section {"
            "  background-color: #eef2f7; color: #6b7280;"
            "  border: none; border-right: 1px solid #d6dae0;"
            "  padding: 0 8px; font-weight: 500;"
            "}"
        )
        vh.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self._refresh_table()
        root.addWidget(self.table, 1)

        # 버튼 행 ─────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(6)

        b_merge_up = mk_btn("⬆ 위와 병합", "gray")
        b_merge_up.clicked.connect(self._merge_up)
        b_del = mk_btn("❌ 삭제", "danger")
        b_del.clicked.connect(self._delete_selected)

        # 소제목 체크박스 — 이 파일 전체의 소제목 흡수 ON/OFF
        self.chk_subtitle = QCheckBox("소제목")
        self.chk_subtitle.setChecked(bool(file_dict.get('subtitle_style', False)))
        self.chk_subtitle.setToolTip(
            "체크: 챕터 헤더 뒤 짧은 줄을 소제목으로 흡수\n"
            "해제: 소제목 오탐 방지 — 챕터 제목에 소제목을 붙이지 않음\n"
            "(변경 시 챕터 목록이 재감지됩니다)")
        self.chk_subtitle.setStyleSheet(
            f"QCheckBox {{ color:{C['text']}; font-size:12px; spacing:5px; }}"
            f"QCheckBox::indicator {{ width:15px; height:15px; }}"
            f"QCheckBox::indicator:checked {{ background:{C['accent']}; border:1px solid {C['accent']};"
            f"  border-radius:3px; image: url({_check_svg_path}); }}"
            f"QCheckBox::indicator:unchecked {{ background:white; border:1px solid {C['border']};"
            f"  border-radius:3px; }}"
        )
        self.chk_subtitle.stateChanged.connect(self._on_subtitle_toggle)

        btn_row.addWidget(b_merge_up)
        btn_row.addWidget(b_del)
        btn_row.addWidget(self.chk_subtitle)
        btn_row.addStretch()
        b_ok = mk_btn("✓ 저장", "green"); b_ok.clicked.connect(self.accept)
        b_cancel = mk_btn("취소", "gray"); b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_ok)
        btn_row.addWidget(b_cancel)
        root.addLayout(btn_row)

    # ── 소제목 체크박스 토글 → 재감지 ──────────────────────
    def _on_subtitle_toggle(self, state):
        """소제목 체크 변경 시 raw_text를 재감지해 챕터 목록 갱신."""
        if not self._detect_fn or not self._raw_text:
            return
        force = (state == Qt.CheckState.Checked.value)
        chapters, _ = self._detect_fn(self._raw_text, force_subtitle_style=force)
        self._chapters = [(t, list(ls)) for t, ls in chapters]
        self._refresh_table()

    def _refresh_table(self):
        self.table.setRowCount(len(self._chapters))
        for i, (t, ls) in enumerate(self._chapters):
            it = QTableWidgetItem(t)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, it)
            length = sum(len(x) for x in ls)
            it2 = QTableWidgetItem(f"{length:,} 자")
            it2.setFlags(it2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, it2)

    def _commit_edits(self):
        for i in range(self.table.rowCount()):
            it = self.table.item(i, 0)
            if it and i < len(self._chapters):
                t, ls = self._chapters[i]
                self._chapters[i] = (it.text(), ls)

    def _merge_up(self):
        self._commit_edits()
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        if not rows:
            return
        rows = [r for r in rows if r > 0]
        for r in reversed(rows):
            t, ls = self._chapters.pop(r)
            prev_t, prev_l = self._chapters[r - 1]
            prev_l.append(f"<b>{t}</b>")
            prev_l.extend(ls)
            self._chapters[r - 1] = (prev_t, prev_l)
        self._refresh_table()

    def _delete_selected(self):
        self._commit_edits()
        rows = sorted({i.row() for i in self.table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            if 0 <= r < len(self._chapters):
                self._chapters.pop(r)
        self._refresh_table()

    def get_title(self):    return self.title_edit.text().strip() or "제목 없음"
    def get_author(self):   return self.author_edit.text().strip() or "미상"
    def get_subtitle_style(self): return self.chk_subtitle.isChecked()
    def get_chapters(self):
        self._commit_edits()
        return self._chapters


class RenameBatchDialog(QDialog):
    MODE_REPLACE = "replace"
    MODE_PREFIX = "prefix"
    MODE_REMOVE = "remove"
    MODE_OVERWRITE = "overwrite"

    def __init__(self, parent, total_count: int, selected_count: int):
        super().__init__(parent)
        self.setWindowTitle("🔧 일괄 변경")
        self.setModal(True)
        self.resize(500, 300)
        self.setStyleSheet(parent.styleSheet())

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        guide = mk_lbl(
            "변경될 이름 열에만 적용되며 확장자는 유지됩니다. "
            "선택 행만 또는 전체에 일괄 적용할 수 있습니다.",
            C["text3"], 11)
        guide.setWordWrap(True)
        root.addWidget(guide)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(8)

        self.src_lbl = mk_lbl("찾을 문자열", C["text2"], 11)
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("예: 기존제목")
        form.addWidget(self.src_lbl, 0, 0)
        form.addWidget(self.src_edit, 0, 1, 1, 3)

        self.dst_lbl = mk_lbl("바꿀 문자열", C["text2"], 11)
        self.dst_edit = QLineEdit()
        self.dst_edit.setPlaceholderText("예: [작가] 제목")
        form.addWidget(self.dst_lbl, 1, 0)
        form.addWidget(self.dst_edit, 1, 1, 1, 3)

        form.addWidget(mk_lbl("변경 방식", C["text2"], 11), 2, 0)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        self.rb_replace = QRadioButton("찾아 바꾸기")
        self.rb_prefix = QRadioButton("앞에 추가")
        self.rb_remove = QRadioButton("삭제")
        self.rb_overwrite = QRadioButton("덮어쓰기")
        for rb in (self.rb_replace, self.rb_prefix, self.rb_remove, self.rb_overwrite):
            rb.toggled.connect(self._sync_mode_ui)
            mode_row.addWidget(rb)
        self.rb_replace.setChecked(True)
        mode_row.addStretch()
        form.addLayout(mode_row, 2, 1, 1, 3)

        self.chk_case = QCheckBox("대소문자 구분")
        self.chk_post_episode = QCheckBox("변경 후 화수 보정")
        self.chk_post_episode.setChecked(True)
        self.chk_append_episode = QCheckBox("뒤에 화수 붙이기")
        opt_row = QHBoxLayout()
        opt_row.setSpacing(14)
        opt_row.addWidget(self.chk_case)
        opt_row.addWidget(self.chk_post_episode)
        opt_row.addWidget(self.chk_append_episode)
        opt_row.addStretch()
        form.addWidget(mk_lbl("옵션", C["text2"], 11), 3, 0)
        form.addLayout(opt_row, 3, 1, 1, 3)

        ep_row = QHBoxLayout()
        ep_row.setSpacing(8)
        ep_row.addWidget(mk_lbl("시작 번호", C["text2"], 11))
        self.ep_start_spin = QSpinBox()
        self.ep_start_spin.setRange(1, 99999)
        self.ep_start_spin.setValue(1)
        self.ep_start_spin.setFixedWidth(90)
        ep_row.addWidget(self.ep_start_spin)
        ep_row.addWidget(mk_lbl("증가", C["text2"], 11))
        self.ep_step_spin = QSpinBox()
        self.ep_step_spin.setRange(1, 999)
        self.ep_step_spin.setValue(1)
        self.ep_step_spin.setFixedWidth(70)
        ep_row.addWidget(self.ep_step_spin)
        self.ep_unit_combo = QComboBox()
        self.ep_unit_combo.addItems(["화", "권"])
        self.ep_unit_combo.setFixedWidth(70)
        ep_row.addWidget(self.ep_unit_combo)
        ep_row.addStretch()
        form.addWidget(mk_lbl("화수 입력", C["text2"], 11), 4, 0)
        form.addLayout(ep_row, 4, 1, 1, 3)
        self.chk_append_episode.toggled.connect(lambda on: (
            self.ep_start_spin.setEnabled(on),
            self.ep_step_spin.setEnabled(on),
            self.ep_unit_combo.setEnabled(on)
        ))
        self.chk_append_episode.setChecked(False)
        self.ep_start_spin.setEnabled(False)
        self.ep_step_spin.setEnabled(False)
        self.ep_unit_combo.setEnabled(False)

        self.rb_scope_all = QRadioButton(f"전체 {total_count}개")
        self.rb_scope_selected = QRadioButton(f"선택 {selected_count}개")
        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        self.scope_group.addButton(self.rb_scope_all)
        self.scope_group.addButton(self.rb_scope_selected)
        self.rb_scope_selected.setEnabled(selected_count > 0)
        # 기본값은 항상 전체로 시작해서, 덮어쓰기 시에도 전체 범위를 명확히 선택 가능하게 유지
        self.rb_scope_all.setChecked(True)
        scope_row = QHBoxLayout()
        scope_row.setSpacing(12)
        scope_row.addWidget(self.rb_scope_all)
        scope_row.addWidget(self.rb_scope_selected)
        scope_row.addStretch()
        form.addWidget(mk_lbl("적용 범위", C["text2"], 11), 5, 0)
        form.addLayout(scope_row, 5, 1, 1, 3)
        root.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()
        b_cancel = mk_btn("취소", "gray")
        b_save = mk_btn("✔ 저장", "blue")
        b_cancel.clicked.connect(self.reject)
        b_save.clicked.connect(self._accept_if_valid)
        btn_row.addWidget(b_cancel)
        btn_row.addWidget(b_save)
        root.addLayout(btn_row)

        self._sync_mode_ui()

    def _current_mode(self) -> str:
        if self.rb_prefix.isChecked():
            return self.MODE_PREFIX
        if self.rb_remove.isChecked():
            return self.MODE_REMOVE
        if self.rb_overwrite.isChecked():
            return self.MODE_OVERWRITE
        return self.MODE_REPLACE

    def _sync_mode_ui(self):
        if not all(hasattr(self, attr) for attr in ("src_lbl", "src_edit", "dst_lbl", "dst_edit", "chk_case")):
            return
        mode = self._current_mode()
        show_dst = mode == self.MODE_REPLACE
        self.dst_lbl.setVisible(show_dst)
        self.dst_edit.setVisible(show_dst)
        self.chk_case.setEnabled(mode in (self.MODE_REPLACE, self.MODE_REMOVE))

        if mode == self.MODE_REPLACE:
            self.src_lbl.setText("찾을 문자열")
            self.src_edit.setPlaceholderText("예: 기존제목")
            self.dst_edit.setPlaceholderText("예: [작가] 제목")
        elif mode == self.MODE_PREFIX:
            self.src_lbl.setText("추가 문자열")
            self.src_edit.setPlaceholderText("예: [작가]")
        elif mode == self.MODE_REMOVE:
            self.src_lbl.setText("삭제 문자열")
            self.src_edit.setPlaceholderText("예: 특수문구")
        else:
            self.src_lbl.setText("새 이름")
            self.src_edit.setPlaceholderText("예: [작가] 새 제목")

    def _accept_if_valid(self):
        mode = self._current_mode()
        src = self.src_edit.text().strip()
        # 덮어쓰기 + 뒤에 화수 붙이기만 사용하는 경우에는 새 이름 공란 허용
        if not src and not self.chk_append_episode.isChecked():
            QMessageBox.information(self, "입력 필요", f"{self.src_lbl.text()}을 입력해 주세요.")
            return
        if mode == self.MODE_REPLACE and not self.dst_edit.text() and not self.chk_append_episode.isChecked():
            QMessageBox.information(self, "입력 필요", "바꿀 문자열을 입력해 주세요.")
            return
        self.accept()

    def get_config(self) -> dict:
        return {
            "mode": self._current_mode(),
            "source": self.src_edit.text(),
            "target": self.dst_edit.text(),
            "case_sensitive": self.chk_case.isChecked(),
            "post_episode_fix": self.chk_post_episode.isChecked(),
            "append_episode": self.chk_append_episode.isChecked(),
            "append_episode_start": int(self.ep_start_spin.value()),
            "append_episode_step": int(self.ep_step_spin.value()),
            "append_episode_unit": self.ep_unit_combo.currentText().strip() or "화",
            "scope": "selected" if self.rb_scope_selected.isChecked() else "all",
        }


class TocEditDialog(QDialog):
    """
    _row_meta 각 행: {'kind': 'book'|'chapter', 'book_idx': int, 'chap_idx': int|None}
    kind='book'    → 파일 단위 상위노드 라벨 (편집 가능)
    kind='chapter' → 해당 파일 내 화 제목 (편집 가능, 빈칸=NCX에서 숨김)
    """
    def __init__(self, parent, files: list, toc_titles: list,
                 page_titles: list | None = None):
        """
        page_titles: list of list — files[i] 의 (item_id, href, page_title) 목록
                     None 이면 화 제목 행 없이 권 라벨만 표시 (기존 동작)
        """
        super().__init__(parent)
        self.setWindowTitle("📝 목차 제목 편집")
        self.setMinimumSize(540, 420)
        self.resize(540, 560)
        self.setModal(True)
        self.setStyleSheet(parent.styleSheet())
        self._files       = files
        self._toc_titles  = list(toc_titles)
        self._page_titles = page_titles or [[] for _ in files]
        # 저장용: book_labels / chap_labels
        self._book_labels = list(toc_titles)
        # chap_labels[i] = [(item_id, href, editable_title), ...]
        self._chap_labels = [list(pt) for pt in self._page_titles]
        self._row_meta    = []   # 각 테이블 행 메타

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # 안내
        hint = mk_lbl(
            "더블클릭 또는 F2로 편집  |  빈칸=NCX 숨김  |  Enter 확정  |  Esc 취소",
            C["text3"], 11)
        lay.addWidget(hint)

        # 테이블 행 수 계산 (화 제목 행만 — 권 라벨 행은 표시 안 함)
        row_count = sum(len(self._chap_labels[i]) for i in range(len(files)))

        self.table = QTableWidget(row_count, 2)
        self.table.setHorizontalHeaderLabels(["#", "목차 표시 제목"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 52)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked |
            QAbstractItemView.EditTrigger.SelectedClicked |
            QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setStyleSheet(
            f"QTableWidget{{background:{C['surface2']};border:1px solid {C['border']};"
            f"border-radius:6px;outline:none;gridline-color:{C['border']};"
            f"font-family:'맑은 고딕';font-size:12px;color:{C['text']};}}"
            f"QTableWidget::item{{padding:3px 6px;color:{C['text']};}}"
            f"QTableWidget::item:selected{{background:rgba(34,114,216,0.1);color:{C['accent']};}}"
            f"QTableWidget::item:hover{{background:{C['bg2']};}}"
            f"QHeaderView::section{{background:{C['bg2']};border:none;"
            f"border-bottom:1px solid {C['border']};border-right:1px solid {C['border']};"
            f"padding:4px 8px;color:{C['text2']};font-size:11px;font-family:'맑은 고딕';}}"
        )

        from PyQt6.QtGui import QColor, QFont as _QFont
        row = 0
        chap_seq = 0  # 전체 화 순번
        for i, (path, name, _) in enumerate(files):
            # ── 화 제목 행들만 표시 (권 라벨 행 없음) ──
            for j, (iid, href, ptitle) in enumerate(self._chap_labels[i]):
                chap_seq += 1
                num_item = QTableWidgetItem(str(chap_seq))
                num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                num_item.setForeground(QColor(C["text3"]))
                self.table.setItem(row, 0, num_item)

                sub_title = QTableWidgetItem(ptitle or "")
                sub_title.setForeground(QColor(C["text2"] if ptitle else C["text3"]))
                self.table.setItem(row, 1, sub_title)
                self.table.setRowHeight(row, 26)
                self._row_meta.append({'kind': 'chapter', 'book_idx': i, 'chap_idx': j})
                row += 1

        lay.addWidget(self.table)

        # 버튼 행
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        b_delete = mk_btn("❌ 선택 행 삭제", "danger")
        b_delete.clicked.connect(self._delete_selected_rows)
        b_reset = mk_btn("↺ 파일명으로 초기화", "gray")
        b_reset.clicked.connect(self._reset)
        b_ok    = mk_btn("✔ 저장", "green"); b_ok.setMinimumWidth(90)
        b_ok.clicked.connect(self._save)
        b_cancel = mk_btn("취소", "gray"); b_cancel.setMinimumWidth(70)
        b_cancel.clicked.connect(self.reject)
        btn_row.addWidget(b_delete)
        btn_row.addWidget(b_reset)
        btn_row.addStretch()
        btn_row.addWidget(b_ok); btn_row.addWidget(b_cancel)
        lay.addLayout(btn_row)

    def _reset(self):
        """화 제목 초기화 (빈칸으로 — NCX 원본값 복원)"""
        for row, meta in enumerate(self._row_meta):
            if meta['kind'] == 'chapter':
                item = self.table.item(row, 1)
                if item:
                    item.setText("")

    def _delete_selected_rows(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for row in rows:
            if 0 <= row < len(self._row_meta):
                meta = self._row_meta.pop(row)
                if meta['kind'] == 'chapter':
                    bi = meta['book_idx']
                    ci = meta['chap_idx']
                    if 0 <= bi < len(self._chap_labels) and 0 <= ci < len(self._chap_labels[bi]):
                        self._chap_labels[bi].pop(ci)
                self.table.removeRow(row)

        chapter_rows = [m for m in self._row_meta if m['kind'] == 'chapter']
        new_meta = []
        chap_seq = 0
        for row, meta in enumerate(chapter_rows):
            bi = meta['book_idx']
            ci = len([m for m in new_meta if m['kind'] == 'chapter' and m['book_idx'] == bi])
            new_meta.append({'kind': 'chapter', 'book_idx': bi, 'chap_idx': ci})
            chap_seq += 1
            num_item = self.table.item(row, 0)
            if num_item:
                num_item.setText(str(chap_seq))
        self._row_meta = new_meta

    def _save(self):
        """테이블 값을 읽어 chap_labels 갱신 (권 라벨은 자동 유지)"""
        for row, meta in enumerate(self._row_meta):
            item = self.table.item(row, 1)
            text = item.text().strip() if item else ""
            bi = meta['book_idx']
            if meta['kind'] == 'chapter':
                ci = meta['chap_idx']
                iid, href, _ = self._chap_labels[bi][ci]
                self._chap_labels[bi][ci] = (iid, href, text)
        self.accept()

    def get_titles(self):
        """기존 호환: 권 라벨 리스트 반환"""
        return self._book_labels

    def get_chap_labels(self):
        """화 제목 리스트 반환: list of list of (iid, href, title)"""
        return self._chap_labels


class CoverPickerDialog(QDialog):
    """
    candidates: list of dict (extract_cover_candidates 반환값)
        각 dict 키: filename, data, ext, size, source, is_default, label
    show_apply_to_all: '시리즈 전체 적용' 체크박스 노출 여부
    show_browse_toggle: '모든 이미지 보기' 토글 노출 여부 (수동 호출 시)
    epub_bytes: 토글 ON 시 모든 이미지를 다시 추출하기 위한 원본 바이트 (수동 호출시)
    all_epub_files: [(path, display_label), ...] — 권별 전환용 전체 파일 목록
    """
    def __init__(self, parent, candidates: list,
                 show_apply_to_all: bool = True,
                 show_browse_toggle: bool = False,
                 epub_bytes: bytes = None,
                 file_label: str = '',
                 all_epub_files: list = None):
        super().__init__(parent)
        self.setWindowTitle("표지 선택")
        self.setModal(True)
        self.setMinimumSize(660, 520)
        self._candidates         = candidates
        self._epub_bytes         = epub_bytes
        self._chosen_idx         = None      # 선택한 후보 인덱스
        self._apply_all          = False     # 시리즈 전체 적용 여부
        self._show_all_mode      = False     # 모든 이미지 표시 상태
        self._deleted_by_vol     = {}        # {vol_path: set(filename)} 권별 삭제 목록
        self._delete_checks      = []        # [(QCheckBox, filename), ...] 현재 렌더 기준
        self._show_browse_toggle = show_browse_toggle
        # 권별 전환: [(path, label), ...] — 2개 이상일 때만 콤보박스 표시
        self._all_epub_files     = all_epub_files or []
        self._current_vol_path   = (all_epub_files[0][0]
                                    if all_epub_files else None)

        from PyQt6.QtWidgets import (
            QVBoxLayout, QHBoxLayout, QScrollArea, QWidget, QFrame,
            QLabel, QPushButton, QCheckBox, QRadioButton, QButtonGroup, QSizePolicy)
        from PyQt6.QtGui import QPixmap

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # 헤더
        hdr_text = f"표지 후보 {len(candidates)}개 발견"
        if file_label:
            hdr_text += f"  ·  {file_label}"
        hdr = QLabel(hdr_text)
        hdr.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:bold;background:transparent;")
        self._hdr_label = hdr   # 권 전환 시 업데이트용
        root.addWidget(hdr)

        sub = QLabel("썸네일을 클릭해 사용할 표지를 선택하세요. "
                     "기본값(★)은 OPF 메타데이터 우선순위에 따른 자동 선택입니다.")
        sub.setStyleSheet(f"color:{C['text3']};font-size:11px;background:transparent;")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # 권별 전환 콤보박스 (2개 이상 파일 있을 때)
        if len(self._all_epub_files) > 1:
            vol_row = QHBoxLayout(); vol_row.setSpacing(6)
            vol_lbl = QLabel("권 선택:")
            vol_lbl.setStyleSheet(f"color:{C['text2']};font-size:11px;background:transparent;")
            vol_row.addWidget(vol_lbl)
            self._vol_combo = QComboBox()
            self._vol_combo.setMaximumWidth(420)
            for _, lbl in self._all_epub_files:
                self._vol_combo.addItem(lbl)
            self._vol_combo.setCurrentIndex(0)
            self._vol_combo.setStyleSheet(
                f"QComboBox{{font-size:11px;padding:2px 6px;"
                f"border:1px solid {C['border']};border-radius:4px;"
                f"background:{C['surface']};color:{C['text']};}}"
                f"QComboBox::drop-down{{border:none;}}")
            self._vol_combo.currentIndexChanged.connect(self._on_volume_changed)
            vol_row.addWidget(self._vol_combo, 1)
            vol_row.addStretch()
            root.addLayout(vol_row)

        # 토글 (모든 이미지 보기)
        if show_browse_toggle and epub_bytes is not None:
            self.chk_show_all = QCheckBox("EPUB 내부의 모든 이미지 표시 (삽화 포함)")
            self.chk_show_all.setStyleSheet(
                f"QCheckBox{{color:{C['text']};font-size:11px;background:transparent;}}"
                f"QCheckBox::indicator{{width:14px;height:14px;border:1.5px solid {C['border']};"
                f"border-radius:3px;background:{C['surface']};}}"
                f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}")
            self.chk_show_all.toggled.connect(self._on_show_all_toggled)
            root.addWidget(self.chk_show_all)

        # 썸네일 그리드 (스크롤 — 마우스 휠로 가로 스크롤 지원)
        from PyQt6.QtCore import QEvent
        class _HScrollArea(QScrollArea):
            """마우스 휠을 가로 스크롤로 전환하는 커스텀 스크롤 영역."""
            def wheelEvent(self, e):
                hbar = self.horizontalScrollBar()
                delta = e.angleDelta().y()
                hbar.setValue(hbar.value() - delta)
                e.accept()
        self.scroll = _HScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet(
            f"QScrollArea{{background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;}}")
        self.grid_host = QWidget()
        self.grid_host.setStyleSheet(f"background:{C['bg2']};")
        self.grid_lay  = QHBoxLayout(self.grid_host)
        self.grid_lay.setContentsMargins(10, 10, 10, 10)
        self.grid_lay.setSpacing(10)
        self.grid_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        root.addWidget(self.scroll, 1)

        self._radio_group = QButtonGroup(self)
        self._radio_group.setExclusive(True)
        self._render_thumbs(self._candidates)

        # 하단 옵션 + 버튼
        bot = QHBoxLayout(); bot.setSpacing(8)
        if show_apply_to_all:
            self.chk_apply_all = QCheckBox("이 선택을 시리즈 전체에 적용")
            self.chk_apply_all.setChecked(True)
            self.chk_apply_all.setToolTip(
                "체크 시: 1권에서 고른 표지를 합본 결과에 그대로 사용합니다.\n"
                "체크 해제 시: 1권만 자동 선택, 다른 권은 영향 없음 (현재 워크플로상 의미 동일).")
            self.chk_apply_all.setStyleSheet(
                f"QCheckBox{{color:{C['text']};font-size:11px;background:transparent;}}"
                f"QCheckBox::indicator{{width:14px;height:14px;border:1.5px solid {C['border']};"
                f"border-radius:3px;background:{C['surface']};}}"
                f"QCheckBox::indicator:checked{{background:{C['accent']};border:1.5px solid {C['accent']};}}")
            bot.addWidget(self.chk_apply_all)
        bot.addStretch(1)
        # 선택 삭제 버튼 (모든 이미지 표시 모드에서만 활성)
        self._b_delete = mk_btn("🗑 선택 삭제", "gray")
        self._b_delete.setToolTip("체크한 이미지를 EPUB 파일에서 삭제합니다")
        self._b_delete.setVisible(False)   # show_all 토글 시 표시
        self._b_delete.clicked.connect(self._on_delete_clicked)
        bot.addWidget(self._b_delete)
        b_cancel = mk_btn("취소 (자동 선택)", "gray")
        b_cancel.clicked.connect(self.reject)
        b_ok     = mk_btn("선택 사용", "blue")
        b_ok.clicked.connect(self._on_ok)
        bot.addWidget(b_cancel)
        bot.addWidget(b_ok)
        root.addLayout(bot)

    # 썸네일 렌더링
    def _render_thumbs(self, items: list):
        from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout,
                                     QLabel, QRadioButton, QCheckBox, QSizePolicy)
        from PyQt6.QtGui import QPixmap
        # 기존 위젯 비우기
        while self.grid_lay.count():
            w = self.grid_lay.takeAt(0).widget()
            if w: w.setParent(None)
        # 라디오 그룹 + 체크박스 목록 초기화
        for b in list(self._radio_group.buttons()):
            self._radio_group.removeButton(b)
        self._delete_checks = []

        for i, c in enumerate(items):
            card = QFrame()
            card.setFixedWidth(180)
            card.setStyleSheet(
                f"QFrame{{background:{C['surface']};border:1px solid {C['border']};border-radius:6px;}}")
            cl = QVBoxLayout(card); cl.setContentsMargins(8, 8, 8, 8); cl.setSpacing(4)

            # 삭제 체크박스 (모든 이미지 표시 모드에서만 노출)
            if self._show_all_mode:
                chk_del = QCheckBox("삭제")
                chk_del.setStyleSheet(
                    f"QCheckBox{{color:#c0392b;font-size:10px;background:transparent;}}"
                    f"QCheckBox::indicator{{width:13px;height:13px;"
                    f"border:1.5px solid #c0392b;border-radius:3px;background:{C['surface']};}}"
                    f"QCheckBox::indicator:checked{{background:#c0392b;border:1.5px solid #c0392b;}}")
                self._delete_checks.append((chk_del, c['filename']))
                cl.addWidget(chk_del)

            # 썸네일
            pix = QPixmap()
            pix.loadFromData(c['data'])
            if not pix.isNull():
                pix = pix.scaled(160, 220,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            thumb = QLabel()
            thumb.setPixmap(pix)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(f"background:{C['bg']};border:1px solid {C['border']};border-radius:4px;")
            thumb.setMinimumHeight(220)
            cl.addWidget(thumb)

            # 라디오 + 라벨
            rb = QRadioButton(c['label'])
            rb.setStyleSheet(
                f"QRadioButton{{color:{C['text']};font-size:11px;background:transparent;}}"
                f"QRadioButton::indicator{{width:12px;height:12px;}}")
            if c.get('is_default'):
                rb.setText('★ ' + c['label'])
                rb.setChecked(True)
            self._radio_group.addButton(rb, i)
            cl.addWidget(rb)

            # 메타정보
            kb   = c['size'] // 1024
            meta = QLabel(f"{kb:,} KB  ·  {c['ext'].lstrip('.').upper()}")
            meta.setStyleSheet(f"color:{C['text3']};font-size:10px;background:transparent;")
            cl.addWidget(meta)

            # 썸네일 클릭으로도 라디오 선택
            def _mk_click(idx):
                def _h(_e):
                    btn = self._radio_group.button(idx)
                    if btn: btn.setChecked(True)
                return _h
            thumb.mousePressEvent = _mk_click(i)

            self.grid_lay.addWidget(card)

        if not items:
            empty = QLabel("표지 후보가 없습니다.")
            empty.setStyleSheet(f"color:{C['text3']};font-size:11px;background:transparent;")
            self.grid_lay.addWidget(empty)

    def _on_volume_changed(self, vol_idx: int):
        """권별 콤보박스 변경 — 해당 epub을 읽어 이미지 목록 갱신."""
        if vol_idx < 0 or vol_idx >= len(self._all_epub_files):
            return
        vol_path, vol_label = self._all_epub_files[vol_idx]
        self._current_vol_path = vol_path
        # 로딩 중 표시
        try:
            with open(vol_path, 'rb') as _fv:
                eb = _fv.read()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "오류", f"파일을 읽을 수 없습니다:\n{e}")
            return
        self._epub_bytes = eb
        # 모든 이미지 표시 체크 상태 반영
        cands = extract_cover_candidates(eb, include_all_images=self._show_all_mode)
        # 이 권에서 이미 삭제한 파일 제외
        _del_this_vol = self._deleted_by_vol.get(vol_path, set())
        if _del_this_vol:
            cands = [c for c in cands if c['filename'] not in _del_this_vol]
        if not cands:
            cands = extract_cover_candidates(eb, include_all_images=True)
            cands = [c for c in cands if c['filename'] not in _del_this_vol]
        self._candidates = cands
        self._render_thumbs(self._candidates)
        # 헤더 업데이트
        if hasattr(self, '_hdr_label'):
            self._hdr_label.setText(
                f"이미지 {len(cands)}개  ·  {Path(vol_path).name}")

    def _on_show_all_toggled(self, checked: bool):
        if not self._epub_bytes: return
        self._show_all_mode = checked
        # 삭제 버튼 표시 토글
        if hasattr(self, '_b_delete'):
            self._b_delete.setVisible(checked)
        new_items = extract_cover_candidates(self._epub_bytes, include_all_images=checked)
        # 이미 삭제 확정된 파일은 다시 뜨지 않도록 필터링
        _del_cur = self._deleted_by_vol.get(self._current_vol_path, set())
        if _del_cur:
            new_items = [c for c in new_items if c['filename'] not in _del_cur]
        self._candidates = new_items
        self._render_thumbs(self._candidates)

    def _on_delete_clicked(self):
        """체크된 이미지 목록 확인창 → 확인 시 삭제 확정."""
        from PyQt6.QtWidgets import QMessageBox
        targets = [(chk, fn) for chk, fn in self._delete_checks if chk.isChecked()]
        if not targets:
            QMessageBox.information(self, "알림", "삭제할 이미지를 체크해주세요.")
            return
        names = '\n'.join(f"  • {Path(fn).name}" for _, fn in targets)
        msg = QMessageBox(self)
        msg.setWindowTitle("이미지 삭제 확인")
        msg.setText(f"체크한 이미지 {len(targets)}개를 EPUB 파일에서 삭제하시겠습니까?")
        msg.setInformativeText(names)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        msg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        msg.button(QMessageBox.StandardButton.Ok).setText("삭제")
        msg.button(QMessageBox.StandardButton.Cancel).setText("취소")
        if msg.exec() != QMessageBox.StandardButton.Ok:
            return
        # 삭제 확정: 현재 권의 _deleted_by_vol에 추가 후 재렌더
        vol_key = self._current_vol_path or ''
        if vol_key not in self._deleted_by_vol:
            self._deleted_by_vol[vol_key] = set()
        for _, fn in targets:
            self._deleted_by_vol[vol_key].add(fn)
        _del_cur = self._deleted_by_vol.get(vol_key, set())
        self._candidates = [c for c in self._candidates
                            if c['filename'] not in _del_cur]
        self._render_thumbs(self._candidates)

    def get_deleted_filenames(self) -> set:
        """하위호환: 1권(첫 번째 권) 기준 삭제 filename 집합 반환."""
        if not self._all_epub_files:
            return set()
        first_path = self._all_epub_files[0][0] if self._all_epub_files else None
        return self._deleted_by_vol.get(first_path, set())

    def get_deleted_by_vol(self) -> dict:
        """권별 삭제 파일 dict 반환: {vol_path: set(filename)}."""
        return self._deleted_by_vol

    def _on_ok(self):
        idx = self._radio_group.checkedId()
        if idx < 0:
            self.reject(); return
        self._chosen_idx = idx
        if hasattr(self, 'chk_apply_all'):
            self._apply_all = self.chk_apply_all.isChecked()
        self.accept()

    def get_choice(self):
        """(data, ext, label, apply_all) 반환. 취소면 (None, None, None, False)."""
        if self._chosen_idx is None or self._chosen_idx >= len(self._candidates):
            return None, None, None, False
        c = self._candidates[self._chosen_idx]
        return c['data'], c['ext'], os.path.basename(c['filename']), self._apply_all


class NaverSeriesCoverDialog(QDialog):
    """표지 검색 통합 다이얼로그 — 네이버 시리즈 직접 추출 OR 구글 이미지 검색."""

    def __init__(self, parent, title: str = "", nid_aut: str = "", nid_ses: str = ""):
        super().__init__(parent)
        self.setWindowTitle("표지 검색")
        self.setModal(True)
        self.setMinimumWidth(480)
        self._cover_data   = None
        self._cover_ext    = '.jpg'
        self._fetched_title  = ""
        self._fetched_author = ""
        self._nid_aut    = nid_aut
        self._nid_ses    = nid_ses
        self._fetch_thread = None
        self._title = title

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        # ── 헤더 ─────────────────────────────────────
        hdr = QLabel("📚  네이버 시리즈 표지 가져오기")
        hdr.setStyleSheet(
            f"color:{C['text']};font-size:13px;font-weight:700;background:transparent;")
        root.addWidget(hdr)
        if title:
            sub = QLabel(f"작품: {title}")
            sub.setStyleSheet(
                f"color:{C['text3']};font-size:11px;background:transparent;")
            root.addWidget(sub)

        # ── URL 입력 ──────────────────────────────────
        no_row = QHBoxLayout(); no_row.setSpacing(6)
        no_lbl = QLabel("URL 또는 productNo")
        no_lbl.setStyleSheet(
            f"color:{C['text2']};font-size:11px;background:transparent;")
        no_row.addWidget(no_lbl)
        self.no_edit = QLineEdit()
        self.no_edit.setPlaceholderText(
            "예) 13364647  또는  https://series.naver.com/novel/detail.series?productNo=13364647")
        no_row.addWidget(self.no_edit, 1)
        root.addLayout(no_row)

        cookie_ok = bool(nid_aut and nid_ses)
        if not cookie_ok:
            warn = QLabel("⚠ 쿠키가 설정되지 않았습니다. 상단 [🍪 쿠키 설정]에서 먼저 입력해주세요.")
            warn.setStyleSheet(
                f"color:{C['orange']};font-size:11px;background:transparent;")
            warn.setWordWrap(True)
            root.addWidget(warn)

        self.status_lbl = QLabel("대기 중...")
        self.status_lbl.setStyleSheet(
            f"color:{C['text3']};font-size:11px;background:transparent;")
        self.status_lbl.setWordWrap(True)
        root.addWidget(self.status_lbl)

        self.prog_bar = QProgressBar()
        self.prog_bar.setRange(0, 0)
        self.prog_bar.setVisible(False)
        self.prog_bar.setFixedHeight(6)
        root.addWidget(self.prog_bar)

        # ── 버튼 행 ───────────────────────────────────
        bot = QHBoxLayout(); bot.setSpacing(8)
        bot.addStretch()
        b_close = QPushButton("닫기")
        b_close.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 16px;color:{C['text2']};font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};}}")
        b_close.clicked.connect(self.reject)
        bot.addWidget(b_close)
        b_google = QPushButton("🔍 검색")
        b_google.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:5px 16px;color:#111;font-size:11px;}}"
            f"QPushButton:hover{{background:{C['bg3']};border-color:{C['accent']};color:{C['accent']};}}")
        b_google.clicked.connect(self._open_google)
        bot.addWidget(b_google)
        self.b_fetch = QPushButton("📥 네이버에서 가져오기")
        self.b_fetch.setEnabled(cookie_ok)
        self.b_fetch.setStyleSheet(
            f"QPushButton{{background:{C['accent']};border:none;border-radius:6px;"
            f"padding:6px 18px;color:#fff;font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{background:#1a5fc4;}}"
            f"QPushButton:disabled{{background:{C['bg3']};color:{C['text3']};}}")
        self.b_fetch.clicked.connect(self._start_fetch)
        bot.addWidget(self.b_fetch)
        root.addLayout(bot)

    # ── 내부 헬퍼 ────────────────────────────────────
    def _parse_product_no(self, text: str) -> str:
        if not _core_parse_product_no:
            return ""
        try:
            return _core_parse_product_no(text)
        except Exception:
            return ""

    def _start_fetch(self):
        no = self._parse_product_no(self.no_edit.text())
        if not no:
            self.status_lbl.setText("⚠ 올바른 URL 또는 productNo를 입력해주세요.")
            return

        self.b_fetch.setEnabled(False)
        self.prog_bar.setVisible(True)
        self.status_lbl.setText(f"productNo {no} 로 표지를 가져오는 중...")

        self._fetch_thread = NaverSeriesFetchThread(no, self._nid_aut, self._nid_ses)
        self._fetch_thread.progress.connect(self._on_progress)
        self._fetch_thread.finished.connect(self._on_finished)
        self._fetch_thread.failed.connect(self._on_failed)
        self._fetch_thread.start()

    def _on_progress(self, msg: str):
        self.status_lbl.setText(msg)

    def _on_finished(self, data: bytes, ext: str, title: str, author: str):
        self._cover_data     = data
        self._cover_ext      = ext
        self._fetched_title  = title
        self._fetched_author = author
        self.prog_bar.setVisible(False)
        self.accept()

    def _on_failed(self, msg: str):
        self.status_lbl.setText(f"❌ {msg}")
        self.prog_bar.setVisible(False)
        self.b_fetch.setEnabled(True)

    def _open_google(self):
        import webbrowser
        from urllib.parse import quote_plus
        query = f"{self._title} 표지" if self._title else "표지"
        webbrowser.open(f"https://www.google.com/search?tbm=isch&q={quote_plus(query)}")
        self.status_lbl.setText(f"🔎 구글 검색 열림: {query}")

    def get_cover(self):
        """(data, ext, title, author) 반환. 미완료 시 (None, '.jpg', '', '')."""
        return self._cover_data, self._cover_ext, self._fetched_title, self._fetched_author


__all__ = [
    "TxtPreviewDialog",
    "RenameBatchDialog",
    "TocEditDialog",
    "CoverPickerDialog",
    "NaverSeriesCoverDialog",
]
