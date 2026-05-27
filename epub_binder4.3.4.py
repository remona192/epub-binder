# -*- coding: utf-8 -*-
# epub_binder4.3.4.py  — 2026-05-20
from __future__ import annotations

import datetime
from pathlib import Path
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox

from epub_binder_app.settings import (
    APP_EXPIRATION_DATE,
    DEFAULT_FONT_FAMILY,
    DEFAULT_FONT_SIZE,
)
from epub_binder_app.ui.main_window import EPUBMergerGUI

# Keep these direct imports so PyInstaller includes the app/core packages in
# one-file builds.
import epub_binder_core.epub_io  # noqa: F401
import epub_binder_core.naver_series  # noqa: F401
import epub_binder_core.title_parser  # noqa: F401
import epub_binder_core.title_metadata  # noqa: F401
import epub_binder_core.cover  # noqa: F401
import epub_binder_core.duplicate_cleanup  # noqa: F401
import epub_binder_core.duplicate_service  # noqa: F401
import epub_binder_core.epub_archive  # noqa: F401
import epub_binder_core.epub_cleanup  # noqa: F401
import epub_binder_core.epub_text  # noqa: F401
import epub_binder_core.grouping  # noqa: F401
import epub_binder_core.merge  # noqa: F401
import epub_binder_core.merge_plan  # noqa: F401
import epub_binder_core.toc  # noqa: F401
import epub_binder_core.txt_chapters  # noqa: F401
import epub_binder_core.txt_detection  # noqa: F401
import epub_binder_core.txt_epub  # noqa: F401
import epub_binder_core.txt_parser  # noqa: F401
import epub_binder_app.workers  # noqa: F401
import epub_binder_app.ui.widgets  # noqa: F401
import epub_binder_app.ui.dialogs  # noqa: F401
import epub_binder_app.ui.helpers  # noqa: F401
import epub_binder_app.ui.main_window  # noqa: F401


def _resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setFont(QFont(DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE))

    icon_path = _resource_path("config", "icon", "app_icon.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    if datetime.date.today() > APP_EXPIRATION_DATE:
        QMessageBox.critical(
            None,
            "사용 기간 만료",
            f"이 버전의 사용 기간이 만료되었습니다.\n\n만료일: {APP_EXPIRATION_DATE.strftime('%Y년 %m월 %d일')}",
        )
        return 0

    gui = EPUBMergerGUI()
    gui.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
