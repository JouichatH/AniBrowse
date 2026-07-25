"""The AA_CRYPTO_STALE fast heal (2026-07-24).

The allanime key/epoch rotate every few minutes, so a request signed from the
(up to 4-min-old) keygen cache can land just past a rotation and get
AA_CRYPTO_STALE back. The provider must re-derive the keygen live and retry
once - NOT fall straight into the (slow, usually Cloudflare-walled) browser
token fallback, which was costing ~90s per episode before the nyaa fallback
could trigger.
"""

import pytest

allanime_provider = pytest.importorskip(
    "viu_media.libs.provider.anime.allanime.provider",
    reason="allanime provider files are wheel-fetched at install time",
)
AllAnime = allanime_provider.AllAnime

from viu_media.libs.provider.anime.params import EpisodeStreamsParams  # noqa: E402

PARAMS = EpisodeStreamsParams(
    anime_id="x", query="x", episode="1", translation_type="sub", quality="1080"
)


def test_rate_limit_detection():
    assert AllAnime._is_rate_limited(
        {"errors": [{"message": "Too many requests, please try again in 5 seconds."}]}
    )
    assert not AllAnime._is_rate_limited({"errors": [{"message": "AA_CRYPTO_STALE"}]})
    assert not AllAnime._is_rate_limited({})


def test_needs_keygen_retry_detection():
    assert AllAnime._needs_keygen_retry({"errors": [{"message": "AA_CRYPTO_STALE"}]})
    assert AllAnime._needs_keygen_retry({"errors": [{"message": "HTTP 403 AA_CRYPTO_REJECT"}]})
    # An encrypted blob that did not yield an episode = stale decrypt key.
    assert AllAnime._needs_keygen_retry({"data": {"tobeparsed": "abc"}})
    assert not AllAnime._needs_keygen_retry({"data": {"episode": {"sourceUrls": []}}})
    assert not AllAnime._needs_keygen_retry({})


def test_stale_rejection_force_refreshes_keygen_and_retries(monkeypatch):
    provider = AllAnime.__new__(AllAnime)  # no client needed; queries are mocked
    responses = [
        {"errors": [{"message": "AA_CRYPTO_STALE"}]},
        {"data": {"episode": {"sourceUrls": [{"sourceName": "Yt"}]}}},
    ]
    monkeypatch.setattr(
        AllAnime,
        "_persisted_episode_query",
        lambda self, params, token_info: responses.pop(0),
    )
    forced = []
    monkeypatch.setattr(
        allanime_provider, "fetch_keygen", lambda force=False: forced.append(force)
    )

    episode = provider._get_episode_payload(PARAMS)

    assert forced == [True], "must re-derive the keygen live before retrying"
    assert episode == {"sourceUrls": [{"sourceName": "Yt"}]}
    assert not responses, "must have retried exactly once"


def test_rate_limited_waits_and_retries(monkeypatch):
    """'Too many requests' (the foreground fetch + two neighbour prefetches
    burst past the endpoint's limit) must wait the server's ask and retry -
    not silently hand the episode to the torrent fallback."""
    provider = AllAnime.__new__(AllAnime)
    limited = {"errors": [{"message": "Too many requests, please try again in 5 seconds."}]}
    good = {"data": {"episode": {"sourceUrls": [{"sourceName": "Yt"}]}}}
    responses = [limited, good]
    monkeypatch.setattr(
        AllAnime,
        "_persisted_episode_query",
        lambda self, params, token_info: responses.pop(0),
    )
    slept = []
    monkeypatch.setattr(allanime_provider, "_sleep", slept.append)
    monkeypatch.setattr(
        allanime_provider,
        "fetch_keygen",
        lambda force=False: pytest.fail("rate limit is not a keygen problem"),
    )

    episode = provider._get_episode_payload(PARAMS)

    assert episode == {"sourceUrls": [{"sourceName": "Yt"}]}
    assert slept == [allanime_provider._RATE_LIMIT_WAIT]


def test_persistent_rate_limit_gives_up_without_browser_fallback(monkeypatch):
    """Still limited after the retries: the token/legacy fallbacks hit the same
    endpoint, so the provider must return None fast (caller -> nyaa)."""
    provider = AllAnime.__new__(AllAnime)
    limited = {"errors": [{"message": "Too many requests, please try again in 5 seconds."}]}
    calls = {"n": 0}

    def query(self, params, token_info):
        calls["n"] += 1
        return limited

    monkeypatch.setattr(AllAnime, "_persisted_episode_query", query)
    monkeypatch.setattr(allanime_provider, "_sleep", lambda s: None)
    monkeypatch.setattr(
        "viu_media.libs.provider.anime.token_capture.get_active_token",
        lambda **k: pytest.fail("must not reach the browser token fallback"),
    )
    monkeypatch.setattr(
        allanime_provider,
        "execute_graphql",
        lambda *a, **k: pytest.fail("must not reach the legacy query"),
    )

    assert provider._get_episode_payload(PARAMS) is None
    assert calls["n"] == 3  # initial + 2 retries


def test_pacing_spaces_out_bursts(monkeypatch):
    """Concurrent episode requests must keep _MIN_EPISODE_REQUEST_SPACING."""
    mod = allanime_provider
    slept = []
    monkeypatch.setattr(mod, "_sleep", slept.append)
    monkeypatch.setattr(mod, "_last_episode_request", 0.0)

    mod._pace_episode_request()  # long-idle: no wait
    assert slept == []
    mod._pace_episode_request()  # immediate follow-up: must wait out the gap
    assert len(slept) == 1 and 0 < slept[0] <= mod._MIN_EPISODE_REQUEST_SPACING


def test_clean_failure_does_not_retry(monkeypatch):
    """A non-crypto failure (e.g. episode genuinely absent) must not burn a
    force-refresh + retry."""
    provider = AllAnime.__new__(AllAnime)
    provider.client = None  # legacy GraphQL fallback passes it to the mock
    calls = {"n": 0}

    def query(self, params, token_info):
        calls["n"] += 1
        return {"data": {"episode": None}}

    monkeypatch.setattr(AllAnime, "_persisted_episode_query", query)
    monkeypatch.setattr(
        allanime_provider,
        "fetch_keygen",
        lambda force=False: pytest.fail("must not force-refresh on a clean miss"),
    )
    # The browser-token fallback must stay quiet for a never-opted-in user.
    monkeypatch.setattr(
        "viu_media.libs.provider.anime.token_capture._user_opted_in", lambda: False
    )
    import httpx

    monkeypatch.setattr(
        allanime_provider,
        "execute_graphql",
        lambda *a, **k: httpx.Response(200, json={"data": {"episode": None}}),
    )

    assert provider._get_episode_payload(PARAMS) is None
    assert calls["n"] == 1
