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
