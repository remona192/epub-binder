from __future__ import annotations

import datetime
import os


def _parse_expiration_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value.strip())
    except ValueError:
        return None


APP_EXPIRATION_DATE = _parse_expiration_date(os.environ.get("EPUB_BINDER_EXPIRES"))
DEFAULT_FONT_FAMILY = "맑은 고딕"
DEFAULT_FONT_SIZE = 10
SETTINGS_ORG = "EpubBinder"
SETTINGS_APP = "EpubBinder"

APP_COLORS = {
    "bg": "#f4f6fb",
    "surface": "#ffffff",
    "surface2": "#ffffff",
    "bg2": "#eef1f6",
    "bg3": "#e4e8f0",
    "border": "#dde2ef",
    "accent": "#2272d8",
    "green": "#18a870",
    "orange": "#d4880a",
    "red": "#c93535",
    "text": "#1a2035",
    "text2": "#4a5470",
    "text3": "#8893b0",
}

__all__ = [
    "APP_COLORS",
    "APP_EXPIRATION_DATE",
    "DEFAULT_FONT_FAMILY",
    "DEFAULT_FONT_SIZE",
    "SETTINGS_APP",
    "SETTINGS_ORG",
]
