"""An outage must reach the screen, not vanish into a DEBUG log line."""

import httpx

from viu_media.core.config import AppConfig
from viu_media.libs.media_api.anidb.api import AniDBApi
from viu_media.libs.media_api.params import MediaSearchParams


def _api(handler) -> AniDBApi:
    transport = httpx.MockTransport(handler)
    return AniDBApi(AppConfig().anilist, httpx.Client(transport=transport))


def test_maintenance_page_is_explained_in_plain_words():
    api = _api(lambda r: httpx.Response(503, text="<title>Under Maintenance</title>"))

    assert api.search_media(MediaSearchParams()) is None
    assert "down" in api.last_error
    assert "503" in api.last_error
    # It says the outage is not the user's fault, because it isn't.
    assert "Nothing to fix on your end" in api.last_error


def test_rate_limiting_says_so():
    api = _api(lambda r: httpx.Response(429, text="slow down"))
    assert api.search_media(MediaSearchParams()) is None
    assert "rate limiting" in api.last_error


def test_connection_failure_names_the_host():
    def boom(request):
        raise httpx.ConnectError("nodename nor servname provided")

    api = _api(boom)
    assert api.search_media(MediaSearchParams()) is None
    assert "anidb.app" in api.last_error


def test_a_good_response_clears_a_previous_failure():
    api = _api(lambda r: httpx.Response(503, text="down"))
    api.search_media(MediaSearchParams())
    assert api.last_error

    api.http_client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html></html>"))
    )
    api.search_media(MediaSearchParams())
    assert api.last_error is None
