from pathlib import Path
import importlib
import ast
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_app_settings_constants_import_without_pyqt():
    from epub_binder_app import settings

    assert settings.APP_EXPIRATION_DATE.isoformat() == "2026-07-31"
    assert settings.DEFAULT_FONT_FAMILY == "맑은 고딕"
    assert settings.DEFAULT_FONT_SIZE == 10
    assert settings.SETTINGS_ORG == "EpubBinder"
    assert settings.SETTINGS_APP == "EpubBinder"
    assert settings.APP_COLORS["accent"] == "#2272d8"


def test_app_package_and_ui_namespace_import_smoke():
    app_pkg = importlib.import_module("epub_binder_app")
    ui_pkg = importlib.import_module("epub_binder_app.ui")
    workers = importlib.import_module("epub_binder_app.workers")
    widgets = importlib.import_module("epub_binder_app.ui.widgets")
    dialogs = importlib.import_module("epub_binder_app.ui.dialogs")
    helpers = importlib.import_module("epub_binder_app.ui.helpers")
    style = importlib.import_module("epub_binder_app.ui.style")
    main_window = importlib.import_module("epub_binder_app.ui.main_window")

    assert app_pkg.DEFAULT_FONT_SIZE == 10
    assert ui_pkg.__name__ == "epub_binder_app.ui"
    assert workers.MergeWorker.__name__ == "MergeWorker"
    assert widgets.FileListWidget.__name__ == "FileListWidget"
    assert dialogs.CoverPickerDialog.__name__ == "CoverPickerDialog"
    assert helpers.human_size(1024) == "1.0 KB"
    assert helpers.safe_title("a:b") == "a b"
    assert "QMainWindow" in style.QSS
    assert main_window.EPUBMergerGUI.__name__ == "EPUBMergerGUI"


def test_main_window_toc_helpers_are_core_implementations():
    from epub_binder_app.ui import main_window
    from epub_binder_core import toc
    from epub_binder_core import txt_epub

    assert main_window.extract_chapter_title is toc.extract_chapter_title
    assert main_window.extract_all_subheadings is toc.extract_all_subheadings
    assert main_window.inject_subheading_anchors is toc.inject_subheading_anchors
    assert main_window._toc_label_from_filename is toc.toc_label_from_filename
    assert main_window._prefer_filename_toc_title is toc.prefer_filename_toc_title
    assert main_window.build_txt_epub is txt_epub.build_txt_epub


def test_main_window_reuses_shared_worker_classes():
    from epub_binder_app import workers
    from epub_binder_app.ui import main_window

    assert main_window.MergeWorker is workers.MergeWorker
    assert main_window.StripOnlyWorker is workers.StripOnlyWorker
    assert main_window.ScanWorker is workers.ScanWorker
    assert main_window.TxtEpubWorker is workers.TxtEpubWorker
    assert main_window.EpubTxtWorker is workers.EpubTxtWorker
    assert main_window.NaverSeriesFetchThread is workers.NaverSeriesFetchThread


def test_main_window_reuses_shared_widget_and_dialog_classes():
    from epub_binder_app.ui import dialogs, main_window, widgets

    assert main_window.FileListWidget is widgets.FileListWidget
    assert main_window.CoverPickerDialog is dialogs.CoverPickerDialog


def test_main_window_no_longer_defines_shared_worker_duplicates():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "class StripOnlyWorker" not in source
    assert "class ScanWorker" not in source
    assert "class TxtEpubWorker" not in source
    assert "class EpubTxtWorker" not in source
    assert "class NaverSeriesFetchThread" not in source
    assert "class MergeWorker" not in source


def test_main_window_no_longer_defines_shared_widget_dialog_duplicates():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "class FileListWidget" not in source
    assert "class CoverPickerDialog" not in source


def test_build_script_includes_app_package_hidden_imports():
    build_script = Path(__file__).resolve().parents[1] / "epub_binder_bulid.bat"
    text = build_script.read_text(encoding="utf-8")

    assert 'set "SCRIPT=epub_binder4.3.4.py"' in text
    assert "--add-data=%ICON%;config/icon" in text
    assert "--hidden-import=epub_binder_app" in text
    assert "--hidden-import=epub_binder_app.settings" in text
    assert "--hidden-import=epub_binder_app.workers" in text
    assert "--hidden-import=epub_binder_app.ui" in text
    assert "--hidden-import=epub_binder_app.ui.widgets" in text
    assert "--hidden-import=epub_binder_app.ui.dialogs" in text
    assert "--hidden-import=epub_binder_app.ui.helpers" in text
    assert "--hidden-import=epub_binder_app.ui.style" in text
    assert "--hidden-import=epub_binder_app.ui.main_window" in text
    assert "--hidden-import=epub_binder_core.title_metadata" in text


def test_entrypoint_uses_app_package_directly():
    entry_path = Path(__file__).resolve().parents[1] / "epub_binder4.3.4.py"
    text = entry_path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    old_entrypoint = "epub_binder4" + ".3.py"
    assert old_entrypoint not in text
    assert "load_compat_module" not in text
    assert "load_legacy_module" not in text

    imported_names = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module == "epub_binder_app.ui.main_window"
        for alias in node.names
    }
    assert "EPUBMergerGUI" in imported_names


def test_missing_cover_prompt_runs_when_cover_scan_fails(monkeypatch, tmp_path):
    from epub_binder_app.ui import main_window

    gui = main_window.EPUBMergerGUI.__new__(main_window.EPUBMergerGUI)
    gui._custom_cover = None
    gui._missing_cover_prompted = set()
    prompted = []

    def fake_prompt(path, title):
        prompted.append((path, title))
        return True

    gui._show_missing_cover_search_prompt = fake_prompt
    missing = tmp_path / "missing.epub"

    assert gui._maybe_prompt_missing_cover_search(str(missing), "작품") is True
    assert prompted == [(str(missing), "작품")]


def test_missing_cover_prompt_skips_when_cover_already_set(monkeypatch, tmp_path):
    from epub_binder_app.ui import main_window

    gui = main_window.EPUBMergerGUI.__new__(main_window.EPUBMergerGUI)
    gui._custom_cover = b"cover"
    gui._missing_cover_prompted = set()

    def fail_prompt(path, title):
        raise AssertionError("prompt should not be shown when a cover is set")

    gui._show_missing_cover_search_prompt = fail_prompt

    assert gui._maybe_prompt_missing_cover_search(str(tmp_path / "book.epub"), "작품") is False


def test_merge_worker_cover_missing_signal_is_connected():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert "cover_missing_signal.connect" in source
    assert "_on_worker_cover_missing" in source


def test_main_window_merge_worker_defines_cover_missing_signal():
    from epub_binder_app import workers
    from epub_binder_app.ui import main_window

    assert main_window.MergeWorker is workers.MergeWorker
    assert hasattr(main_window.MergeWorker, "cover_missing_signal")


def test_merge_complete_setting_is_not_cleared_by_filename_autodetect():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")
    auto_title_start = source.index("# 완결 자동 감지")
    auto_title_end = source.index("auto_name  = _safe_title(auto_name)", auto_title_start)
    auto_title_block = source[auto_title_start:auto_title_end]

    assert "self.chk_complete.setChecked(has_complete)" not in auto_title_block
    assert "if self.chk_complete.isChecked():" in auto_title_block


def test_epub_to_txt_combine_label_is_txt_merge():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert 'QCheckBox("txt 합치기")' in source
    assert 'QCheckBox("하나로 합치기")' not in source


def test_duplicate_cleanup_tab_is_registered():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert 'self.tab_widget.addTab(dedupe_tab, "중복 정리")' in source
    assert "def _build_dedupe_tab" in source
    assert "move_duplicate_candidates_to_trash" in source


def test_duplicate_cleanup_table_uses_soft_badge_palette():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")
    render_start = source.index("    def _dedupe_render_table")
    render_end = source.index("    def _dedupe_group_is_safe", render_start)
    render_block = source[render_start:render_end]

    assert "_dedupe_row_palette" in render_block
    assert "badge_bg" in render_block
    assert "setFont" in render_block
    for harsh_color in ("#e9f7ef", "#fff6d8", "#ffe7d6"):
        assert harsh_color not in render_block


def test_duplicate_cleanup_table_groups_rows_and_uses_action_badges():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")
    render_start = source.index("    def _dedupe_render_table")
    render_end = source.index("    def _dedupe_group_is_safe", render_start)
    render_block = source[render_start:render_end]

    assert "self._dedupe_row_palette(group, decision, default_select, index)" in render_block
    assert "self._dedupe_action_label(decision, default_select)" in render_block
    assert 'select_item.setText("남김")' not in render_block
    assert "item.setText(self._dedupe_action_label_for_path(path_value, checked=item.checkState() == Qt.CheckState.Checked))" in source
    assert "delete_badge_bg" in source
    assert "keep_badge_bg" in source


def test_duplicate_cleanup_action_badges_use_red_delete_orange_review_green_keep():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")

    assert '"keep_badge_bg": "#2f855a"' in source
    assert '"delete_badge_bg": "#dc2626"' in source
    assert '"review_badge_bg": "#d97706"' in source
    assert 'QColor("#dc2626")' in source
    assert 'QColor("#d97706")' in source
    assert 'QColor("#64748b")' not in source


def test_duplicate_cleanup_table_hides_group_column_and_uses_compact_centered_selection():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")
    setup_start = source.index("        self.dedupe_table = QTableWidget(0, 6)")
    setup_end = source.index("        self.dedupe_table.itemChanged.connect", setup_start)
    setup_block = source[setup_start:setup_end]

    assert "self.dedupe_table.setColumnHidden(0, True)" in setup_block
    assert "header.resizeSection(1, 34)" in setup_block
    assert "header.resizeSection(2, 58)" in setup_block
    assert "self.dedupe_table.setItemDelegateForColumn(1, CenteredCheckBoxDelegate(self.dedupe_table))" in setup_block
    assert "class CenteredCheckBoxDelegate" in source


def test_duplicate_cleanup_restore_checked_paths_keeps_status_badge_in_sync():
    source = (
        Path(__file__).resolve().parents[1]
        / "epub_binder_app"
        / "ui"
        / "main_window.py"
    ).read_text(encoding="utf-8")
    restore_start = source.index("    def _dedupe_restore_checked_paths")
    restore_end = source.index("    def _dedupe_run", restore_start)
    restore_block = source[restore_start:restore_end]

    assert "status_item = self.dedupe_table.item(row, 2)" in restore_block
    assert "status_item.setText(self._dedupe_action_label_for_path(path_value, checked=checked))" in restore_block
    assert 'status_item.setBackground(QColor("#dc2626" if checked else "#d97706"))' in restore_block
    assert 'status_item.setForeground(QColor("#ffffff"))' in restore_block
