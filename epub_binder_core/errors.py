from __future__ import annotations

import urllib.error


class CoreError(Exception):
    """Base exception for core-layer failures."""


class InvalidEpubError(CoreError):
    """Raised when EPUB bytes or paths cannot be read as a valid EPUB."""


class MissingMetadataError(CoreError):
    """Raised when required EPUB metadata is unavailable."""


class CoverNotFoundError(CoreError):
    """Raised when no usable cover image can be found."""


class NaverFetchError(CoreError):
    """Raised when a Naver Series fetch operation cannot complete."""


def format_worker_error(exc: BaseException) -> str:
    """Convert an unexpected worker exception into the legacy user message form."""

    return f"오류: {exc}"


def format_naver_fetch_error(exc: BaseException) -> str:
    """Convert Naver Series fetch failures into user-facing legacy messages."""

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code == 403:
            return (
                "HTTP 403 — 쿠키가 만료됐거나 잘못되었습니다.\n"
                "🍪 쿠키 설정에서 NID_AUT / NID_SES를 갱신해주세요."
            )
        return f"HTTP 오류 {exc.code}: {exc.reason}"
    return format_worker_error(exc)
