"""Browsing survives a metadata backend going down.

anidb.app went to a site-wide maintenance page in 2026-09 while it was BOTH the
browse backend and the streaming provider, so every menu came back empty and -
because an empty result silently redrew the main menu - the app looked frozen.
"""

from viu_media.libs.media_api.failover import FailoverApiClient
from viu_media.libs.media_api.params import MediaSearchParams


class _Backend:
    """Minimal stand-in: answers with `result`, or fails the way named."""

    def __init__(self, result=None, raises=None, last_error=None):
        self._result = result
        self._raises = raises
        self.last_error = last_error
        self.calls = 0

    def search_media(self, params):
        self.calls += 1
        if self._raises:
            raise self._raises
        return self._result

    def get_notifications(self):
        return ["from-active"]


def _client(primary, standbys):
    built = {}

    def factory(name):
        built[name] = standbys[name]
        return standbys[name]

    return FailoverApiClient("primary", primary, list(standbys), factory)


def test_healthy_primary_is_never_bypassed():
    primary = _Backend(result="trending")
    standby = _Backend(result="other")
    api = _client(primary, {"standby": standby})

    assert api.search_media(MediaSearchParams()) == "trending"
    assert standby.calls == 0
    assert api.active_name == "primary"


def test_dead_primary_rolls_over_and_stays_switched():
    primary = _Backend(raises=RuntimeError("503 maintenance"))
    standby = _Backend(result="trending")
    api = _client(primary, {"standby": standby})

    assert api.search_media(MediaSearchParams()) == "trending"
    # Promotion is sticky: media ids are namespaced per backend, so follow-up
    # calls must hit the backend that produced the items on screen.
    assert api.active_name == "standby"
    assert api.get_notifications() == ["from-active"]


def test_a_backend_that_answers_empty_also_fails_over():
    primary = _Backend(result=None, last_error="anidb.app is down (HTTP 503)")
    standby = _Backend(result="trending")
    api = _client(primary, {"standby": standby})

    assert api.search_media(MediaSearchParams()) == "trending"
    assert api.active_name == "standby"


def test_total_outage_reports_every_backend_reason():
    primary = _Backend(result=None, last_error="anidb.app is down (HTTP 503)")
    standby = _Backend(raises=RuntimeError("AniList is unavailable"))
    api = _client(primary, {"standby": standby})

    assert api.search_media(MediaSearchParams()) is None
    # The menus put this on screen instead of bouncing back in silence.
    assert "anidb.app is down (HTTP 503)" in api.last_error
    assert "AniList is unavailable" in api.last_error
