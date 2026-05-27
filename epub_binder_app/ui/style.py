# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

from epub_binder_app.settings import APP_COLORS as C

_check_svg = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 14 14">'
    '<polyline points="2,7 5.5,11 12,3" stroke="white" stroke-width="2" '
    'fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>')
_exe_dir = os.path.dirname(
    sys.executable if getattr(sys, 'frozen', False) else os.path.abspath(__file__))
_check_svg_path = os.path.join(_exe_dir, '_check.svg').replace('\\', '/')
try:
    with open(_check_svg_path, 'w') as _f:
        _f.write(_check_svg)
except Exception:
    pass

QSS = f"""
QMainWindow, QWidget#central {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 #eef1f8, stop:1 {C['bg']});
}}
QLabel {{
    color: {C['text']}; font-family: '맑은 고딕'; font-size: 12px;
    background: transparent; font-weight: 400;
}}
QFrame#card {{
    background: {C['surface']}; border: 1px solid {C['border']}; border-radius: 10px;
}}
QFrame#card_header {{
    background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #f0f3fa, stop:1 #e8ecf4); border-bottom: 1px solid {C['border']};
    border-top-left-radius: 10px; border-top-right-radius: 10px;
}}
QLineEdit {{
    background: {C['surface2']}; border: 1px solid {C['border']}; border-radius: 6px;
    padding: 0px 8px; font-family: '맑은 고딕'; font-size: 12px; color: {C['text']};
    min-height: 26px; max-height: 26px;
}}
QLineEdit:focus {{ border: 1.5px solid {C['accent']}; }}
QLineEdit:hover {{ border-color: {C['accent']}; }}
QPushButton {{
    font-family: '맑은 고딕'; font-size: 12px; font-weight: 400;
    border-radius: 6px; padding: 5px 10px; border: none;
}}
QPushButton#btn_green {{ background: {C['green']}; color: white; font-weight: 600; }}
QPushButton#btn_green:hover {{ background: #16b87a; }}
QPushButton#btn_green:disabled {{ background: #a8d8c4; color: #ddf0ea; }}
QPushButton#btn_blue {{
    background: rgba(34,114,216,0.08); color: {C['accent']};
    border: 1px solid rgba(34,114,216,0.25);
}}
QPushButton#btn_blue:hover {{ background: rgba(34,114,216,0.15); }}
QPushButton#btn_gray {{
    background: {C['surface']}; color: {C['text2']}; border: 1px solid {C['border']};
}}
QPushButton#btn_gray:hover {{ background: {C['bg2']}; }}
QPushButton#btn_danger {{
    background: rgba(201,53,53,0.08); color: {C['red']};
    border: 1px solid rgba(201,53,53,0.25);
}}
QPushButton#btn_danger:hover {{ background: rgba(201,53,53,0.15); }}
QCheckBox {{
    font-family: '맑은 고딕'; font-size: 12px; font-weight: 400;
    color: {C['text2']}; spacing: 6px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    background: {C['surface2']}; border: 1.5px solid {C['border']};
}}
QCheckBox::indicator:checked {{
    background: {C['accent']}; border: 2px solid {C['accent']};
    border-radius: 2px; image: url({_check_svg_path});
}}
QCheckBox::indicator:hover {{ border-color: {C['accent']}; }}
QProgressBar {{
    background: {C['bg3']}; border: none; border-radius: 3px;
    height: 6px; font-size: 1px; color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
        stop:0 {C['green']}, stop:1 #2de49a);
    border-radius: 3px;
}}
QTextEdit#log_area {{
    background: #f8f9fc; border: 1px solid {C['border']}; border-radius: 6px;
    color: {C['text']}; font-family: 'Consolas','D2Coding',monospace;
    font-size: 11px; padding: 8px;
}}
QScrollBar:vertical {{
    background: transparent; width: 6px; border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {C['border']}; border-radius: 3px; min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {C['text3']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QListWidget {{
    background: {C['surface2']}; border: 1px solid {C['border']};
    border-radius: 6px; outline: none;
    font-family: '맑은 고딕'; font-size: 12px; color: {C['text']};
}}
QListWidget::item {{
    padding: 5px 8px; border-bottom: 1px solid {C['border']}; color: {C['text']};
}}
QListWidget::item:selected {{ background: rgba(34,114,216,0.1); color: {C['accent']}; }}
QListWidget::item:hover {{ background: {C['bg2']}; }}
QTabWidget::pane {{
    border: 1px solid {C['border']}; border-radius: 8px;
    background: transparent; margin-top: -1px;
}}
QTabBar::tab {{
    background: {C['bg2']}; border: 1px solid {C['border']};
    padding: 6px 18px; font-family: '맑은 고딕'; font-size: 12px; color: {C['text2']};
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {C['surface']}; color: {C['accent']};
    border-bottom: 1px solid {C['surface']}; font-weight: 600;
}}
QTabBar::tab:hover {{ color: {C['text']}; background: {C['bg3']}; }}
"""

CHECK_SVG_PATH = _check_svg_path

__all__ = ["QSS", "CHECK_SVG_PATH"]
