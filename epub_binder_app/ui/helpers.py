# -*- coding: utf-8 -*-
from __future__ import annotations

import re

from PyQt6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from epub_binder_app.settings import APP_COLORS as C


_FORBIDDEN_TITLE_CHARS = re.compile(r'[\\/:*?"<>|]')


def _extra_num(value: str) -> int:
    match = re.search(
        r'\((외전|번외|특전|특별외전|특별\s*외전)\s*(\d+)\)',
        str(value or ""),
        re.IGNORECASE,
    )
    if match:
        return int(match.group(2))
    if re.search(r'\((외전|번외|특전|특별외전|특별\s*외전)\)', str(value or ""), re.IGNORECASE):
        return 0
    return 0


def natural_sort_key(value: str):
    """권·부·화 번호를 정수로 비교하는 legacy UI 정렬 키."""

    text = str(value or "")
    is_complete = bool(re.search(r'\(완결\)|완결', text, re.IGNORECASE))
    is_extra = bool(re.search(r'외전|번외', text))
    extra_num = _extra_num(text)
    volume_match = re.search(r'(\d+)권', text)
    episode_match = re.search(r'(\d+)화', text)
    without_parens = re.sub(r'\([^)]*\)', '', text)
    part_match = re.search(r'(\d+)부', without_parens)
    volume_num = int(volume_match.group(1)) if volume_match else 0
    episode_num = int(episode_match.group(1)) if episode_match else 0
    part_num = int(part_match.group(1)) if part_match else 0
    number = volume_num or episode_num

    tag_match = re.match(r'^(\[[^\]]+\]\s*)', text)
    tag = tag_match.group(1).strip() if tag_match else ''
    text_without_tag = text[tag_match.end():] if tag_match else text
    raw_part_match = re.search(r'(\d+)부', text_without_tag)

    if re.match(r'^제?\s*\d+\s*화\s*[._\s]', text_without_tag):
        series_name = ''
    else:
        series_name = re.sub(r'\s*\d+[권화부]\s*', '', text_without_tag)
        series_name = re.sub(r'\s*[\(（][^\)）]*[\)）]\s*', '', series_name)
        series_name = re.sub(r'[,\s]*(?:특별\s*외전|외전|번외|특전)\s*$', '', series_name)
        series_name = re.sub(r'\.[^.]+$', '', series_name)
        series_name = re.sub(r'[\s_]+\d+\s*$', '', series_name)
        series_name = re.sub(r'\s*[-–—]\s+.*$', '', series_name)
        series_name = re.sub(r'\s+', ' ', series_name).strip()

    if number == 0 and part_num == 0:
        base = re.sub(r'\.[^.]+$', '', text_without_tag)
        base = re.sub(r'\s*[\(\[（【][^\)\]）】]*[\)\]）】]\s*$', '', base).strip()
        tail_match = re.search(r'(\d+)\s*$', base)
        if tail_match:
            number = int(tail_match.group(1))

    is_interview = bool(re.search(r'인터뷰집|인터뷰|작가노트', text))
    complete_flag = 0.5 if is_complete else 0.0
    part_before_volume = bool(
        raw_part_match
        and volume_match
        and raw_part_match.start() < volume_match.start()
    )
    # "1부 10권"은 부 단위 묶음 순서를 우선하고,
    # "17권(2부)"처럼 권 뒤에 붙은 부표기는 권 번호를 우선한다.
    if number:
        if part_before_volume:
            return (series_name, 0, part_num, number, 0, complete_flag, tag, text)
        return (series_name, 1, number, part_num, 0, complete_flag, tag, text)
    if is_interview:
        return (series_name, 2, extra_num or number, part_num, 2, complete_flag, tag, text)
    if is_extra:
        return (series_name, 2, extra_num or number, part_num, 1, complete_flag, tag, text)
    return (series_name, 1, number, part_num, 0, complete_flag, tag, text)


def human_size(size: int | float) -> str:
    value = float(size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def safe_title(value: str) -> str:
    text = str(value or "").replace('\n', ' ').strip()
    text = _FORBIDDEN_TITLE_CHARS.sub(' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def make_card(title: str, dot_color: str = None):
    card = QFrame()
    card.setObjectName("card")
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(0, 0, 0, 0)
    card_layout.setSpacing(0)
    body = QWidget()
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(10, 8, 10, 8)
    body_layout.setSpacing(6)
    card_layout.addWidget(body)
    return card, body, body_layout


def mk_btn(text, style="gray"):
    button = QPushButton(text)
    button.setObjectName(f"btn_{style}")
    return button


def mk_lbl(text, color=None, size=12, bold=False):
    label = QLabel(text)
    css = f"color:{color or C['text2']};font-size:{size}px;background:transparent;"
    if bold:
        css += "font-weight:700;"
    label.setStyleSheet(css)
    return label


__all__ = [
    "human_size",
    "make_card",
    "mk_btn",
    "mk_lbl",
    "natural_sort_key",
    "safe_title",
]
