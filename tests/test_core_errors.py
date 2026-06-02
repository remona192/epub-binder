from pathlib import Path
import sys
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub_binder_core.errors import (  # noqa: E402
    CoreError,
    CoverNotFoundError,
    format_naver_fetch_error,
    format_worker_error,
    InvalidEpubError,
    MissingMetadataError,
    NaverFetchError,
)


def test_core_error_subclasses_share_common_base():
    for error_type in (
        InvalidEpubError,
        MissingMetadataError,
        CoverNotFoundError,
        NaverFetchError,
    ):
        assert issubclass(error_type, CoreError)
        assert isinstance(error_type("message"), CoreError)


def test_format_worker_error_preserves_legacy_prefix():
    assert format_worker_error(RuntimeError("boom")) == "오류: boom"


def test_format_naver_fetch_error_special_cases_http_errors():
    err_403 = urllib.error.HTTPError(
        "https://series.naver.com/",
        403,
        "Forbidden",
        {},
        None,
    )
    assert "HTTP 403" in format_naver_fetch_error(err_403)
    assert "NID_AUT / NID_SES" in format_naver_fetch_error(err_403)

    err_500 = urllib.error.HTTPError(
        "https://series.naver.com/",
        500,
        "Server Error",
        {},
        None,
    )
    assert format_naver_fetch_error(err_500) == "HTTP 오류 500: Server Error"
