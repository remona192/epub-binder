# -*- coding: utf-8 -*-
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem

from epub_binder_app.settings import APP_COLORS as C


class FileListWidget(QListWidget):
    """파일 목록 표시 + 외부 파일 드래그앤드롭 수신 + 안내 텍스트 통합"""
    files_dropped = pyqtSignal(list)   # 외부 파일 드롭 시그널
    order_changed = pyqtSignal()       # 내부 순서 변경 시그널

    _PLACEHOLDER = "📂  EPUB / ZIP / 7z 파일을 여기에 드래그하거나 위 [파일 열기] 버튼을 눌러주세요"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setFixedHeight(150)
        self._external_drag = False   # 외부 드래그 중 여부
        self._show_placeholder()

    # ── 안내 텍스트 ──────────────────────────
    def _show_placeholder(self):
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        item = QListWidgetItem(self._PLACEHOLDER)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setForeground(
            __import__('PyQt6.QtGui', fromlist=['QColor']).QColor(C['text3']))
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.addItem(item)

    def _clear_placeholder(self):
        if (self.count() == 1
                and self.item(0).text() == self._PLACEHOLDER):
            self.clear()

    def set_has_files(self, has: bool):
        """파일 있을 때/없을 때 드래그 모드 전환"""
        if not has:
            self.clear()
            self._show_placeholder()   # DragDrop 모드 유지됨
        # 파일 있을 때 드래그 모드는 _on_manual_toggle 에서 제어

    # ── 외부 파일/폴더 드래그 이벤트 ──────────
    def _is_external(self, e):
        return e.mimeData().hasUrls()

    def dragEnterEvent(self, e):
        if self._is_external(e):
            self._external_drag = True
            e.acceptProposedAction()
            self.setStyleSheet(
                f"QListWidget{{background:#e8f7ee;"
                f"border:2px dashed {C['green']};border-radius:6px;}}")
        else:
            self._external_drag = False
            super().dragEnterEvent(e)

    def dragLeaveEvent(self, e):
        if self._external_drag:
            self._external_drag = False
            self.setStyleSheet("")
        else:
            super().dragLeaveEvent(e)

    def dragMoveEvent(self, e):
        if self._is_external(e):
            e.acceptProposedAction()
        else:
            super().dragMoveEvent(e)

    def dropEvent(self, e):
        if self._is_external(e):
            self._external_drag = False
            self.setStyleSheet("")
            # 파일 + 폴더 모두 emit
            urls = [u.toLocalFile() for u in e.mimeData().urls()]
            if urls: self.files_dropped.emit(urls)
            e.acceptProposedAction()
        else:
            # 내부 순서 변경 (수동 모드)
            super().dropEvent(e)
            self.order_changed.emit()


__all__ = ["FileListWidget"]
