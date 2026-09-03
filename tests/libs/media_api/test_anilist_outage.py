"""An unusable AniList response must name its cause, not crash the menu.

AniList disabled its API in 2026-08 and answered every query with a 403 plus an
``errors`` array and no ``data``. The mappers index straight into
``data["data"]["Page"]``, so the whole MAIN menu died with
``'NoneType' object is not subscriptable`` - which tells a user nothing.
"""

import httpx
import pytest

from viu_media.core.exceptions import AniBrowseError
from viu_media.core.utils.graphql import graphql_error_message
from viu_media.libs.media_api.anilist.api import _payload

API_DISABLED = {
    "errors": [
        {
            "message": "The AniList API has been temporarily disabled due to severe stability issues.",
            "status": 403,
        }
    ],
    "data": None,
}


def _response(payload, status=200, text=None):
    request = httpx.Request("POST", "https://graphql.anilist.co")
    if text is not None:
        return httpx.Response(status, text=text, request=request)
    return httpx.Response(status, json=payload, request=request)


# ---- graphql_error_message ----------------------------------------------


def test_healthy_response_has_no_error():
    ok = _response({"data": {"Page": {"media": []}}})
    assert graphql_error_message(ok) is None


def test_partial_errors_alongside_data_are_not_fatal():
    """GraphQL may return both data and per-field errors; that is still usable."""
    partial = _response({"data": {"Page": {"media": []}}, "errors": [{"message": "x"}]})
    assert graphql_error_message(partial) is None


def test_disabled_api_reports_the_servers_own_message():
    message = graphql_error_message(_response(API_DISABLED, status=403))
    assert message == (
        "The AniList API has been temporarily disabled due to severe stability issues."
    )


def test_duplicate_error_messages_are_collapsed():
    payload = {"errors": [{"message": "rate limited"}, {"message": "rate limited"}]}
    assert graphql_error_message(_response(payload, status=429)) == "rate limited"


def test_non_json_error_body_falls_back_to_the_status():
    message = graphql_error_message(_response(None, status=502, text="<html>bad gateway"))
    assert message is not None
    assert "502" in message and "graphql.anilist.co" in message


def test_non_json_success_body_is_not_an_error():
    assert graphql_error_message(_response(None, status=200, text="")) is None


def test_success_with_neither_data_nor_errors_is_reported():
    assert graphql_error_message(_response({})) == "the API returned no data"


# ---- _payload ------------------------------------------------------------


def test_payload_passes_through_a_healthy_body():
    body = {"data": {"Page": {"media": []}}}
    assert _payload(_response(body)) == body


def test_payload_raises_a_readable_error_during_an_outage():
    with pytest.raises(AniBrowseError) as excinfo:
        _payload(_response(API_DISABLED, status=403))
    # The user must see AniList's reason, not a TypeError from the mapper.
    assert "temporarily disabled" in str(excinfo.value)
    assert "NoneType" not in str(excinfo.value)
