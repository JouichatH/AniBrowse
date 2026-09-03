"""Tests for the anidb.app provider (no network).

The network boundary is ``AniDB._get`` / ``_get_json``; everything above it -
search-card scraping, Cloudflare detection, the episode-number normalisation
that hides anidb's absolute numbering, language selection and master-playlist
parsing - is pure and is exercised here against captured response shapes.
"""

import pytest

from viu_media.libs.provider.anime.anidb.provider import AniDB, _fmt_ep, _nearest_quality
from viu_media.libs.provider.anime.params import (
    AnimeParams,
    EpisodeStreamsParams,
    SearchParams,
)


@pytest.fixture
def anidb():
    # No httpx client: every test stubs the fetch helpers.
    return AniDB(client=None)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _clear_episode_cache():
    from viu_media.libs.provider.anime.anidb import provider as mod

    mod._episodes_cache.clear()
    yield
    mod._episodes_cache.clear()


def _eps(*numbers):
    """An episodes payload with sequential ids, as the API returns it."""
    return {
        "episodes": [
            {"id": 1000 + i, "number": n, "number2": None, "filler": False}
            for i, n in enumerate(numbers)
        ]
    }


# A trimmed but structurally faithful pair of browse cards.
SEARCH_HTML = """
<div class="grid">
<a href="https://anidb.app/anime/frieren-beyond-journeys-end-1663" class="anime-card"
   title="Frieren: Beyond Journey&#039;s End">
  <img src="https://cdn.xlsbox.com/poster/small/1782735600/1663.jpg" alt="Frieren: Beyond Journey&#039;s End">
  <span class="badge badge-orange text-[9px]" style="color:#fff">TV</span>
</a>
<a href="https://anidb.app/anime/frieren-beyond-journeys-end-mini-anime-1664" class="anime-card"
   title="Frieren Mini Anime">
  <img src="https://cdn.xlsbox.com/poster/small/1/1664.jpg" alt="Frieren Mini Anime">
  <span class="badge badge-orange text-[9px]" style="color:#fff">ONA</span>
</a>
</div>
"""

MASTER_M3U8 = """#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=922484,RESOLUTION=1920x1080,CODECS="avc1.640028"
https://hls.anidb.app/stream/tok/index-f1-v1-a1.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=540880,RESOLUTION=1280x720,CODECS="avc1.640028"
https://hls.anidb.app/stream/tok/index-f2-v1-a1.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=229348,RESOLUTION=640x360,CODECS="avc1.640028"
https://hls.anidb.app/stream/tok/index-f3-v1-a1.m3u8
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=160806,RESOLUTION=1920x1080,URI="https://hls.anidb.app/stream/tok/iframes-f1.m3u8"
"""


# ---- helpers -------------------------------------------------------------


def test_numeric_id_takes_trailing_number():
    assert AniDB._numeric_id("frieren-beyond-journeys-end-1663") == "1663"
    assert AniDB._numeric_id("one-piece-3880") == "3880"


def test_nearest_quality_snaps_to_supported_values():
    assert _nearest_quality(1080) == "1080"
    assert _nearest_quality(720) == "720"
    # A rendition height the app has no bucket for lands on the closest one.
    assert _nearest_quality(1440) == "1080"
    assert _nearest_quality(540) == "480"


def test_fmt_ep_drops_trailing_zero():
    assert _fmt_ep(7.0) == "7"
    assert _fmt_ep(24.5) == "24.5"


# ---- search --------------------------------------------------------------


def test_search_parses_cards(anidb, monkeypatch):
    monkeypatch.setattr(anidb, "_get", lambda url: SEARCH_HTML)
    results = anidb.search(SearchParams(query="frieren")).results

    assert [r.id for r in results] == [
        "frieren-beyond-journeys-end-1663",
        "frieren-beyond-journeys-end-mini-anime-1664",
    ]
    # HTML entities in the title are decoded for fuzzy matching to work.
    assert results[0].title == "Frieren: Beyond Journey's End"
    assert results[0].media_type == "TV"
    assert results[1].media_type == "ONA"
    assert results[0].poster.endswith("1663.jpg")


def test_search_leaves_episodes_empty(anidb, monkeypatch):
    """Episode lists cost a request each and nothing reads them off a search
    result - get() fills them in."""
    monkeypatch.setattr(anidb, "_get", lambda url: SEARCH_HTML)
    assert anidb.search(SearchParams(query="frieren")).results[0].episodes.sub == []


def test_search_detects_cloudflare_challenge(anidb, monkeypatch, caplog):
    monkeypatch.setattr(
        anidb, "_get", lambda url: "<title>Just a moment...</title><div id=cf>"
    )
    assert anidb.search(SearchParams(query="frieren")) is None
    assert "Cloudflare" in caplog.text


def test_search_returns_none_on_fetch_failure(anidb, monkeypatch):
    monkeypatch.setattr(anidb, "_get", lambda url: None)
    assert anidb.search(SearchParams(query="frieren")) is None


# ---- episode-number normalisation ---------------------------------------


def test_absolute_numbering_is_shifted_to_start_at_one(anidb, monkeypatch):
    """Frieren S2 is numbered 29-38 on anidb but 1-10 everywhere else."""
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(*range(29, 39)))
    index = anidb._episode_index("frieren-beyond-journeys-end-season-2-1665")

    assert sorted(index, key=float) == [str(n) for n in range(1, 11)]
    # Display "1" must still resolve to the id of the raw episode 29.
    assert index["1"] == 1000
    assert index["10"] == 1009


def test_per_season_numbering_is_left_alone(anidb, monkeypatch):
    """Mushoku Tensei S2 already numbers from 1; nothing should shift."""
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(*range(1, 13)))
    index = anidb._episode_index("mushoku-tensei-jobless-reincarnation-season-2-3567")
    assert sorted(index, key=float) == [str(n) for n in range(1, 13)]
    assert index["1"] == 1000


def test_episode_zero_specials_are_not_shifted_up(anidb, monkeypatch):
    """An entry starting at 0 must keep its episode 0, not become episode 1."""
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(0, 1, 2))
    assert sorted(anidb._episode_index("x-1"), key=float) == ["0", "1", "2"]


def test_fractional_episode_number_survives_the_shift(anidb, monkeypatch):
    """A one-episode digression numbered 24.9 normalises cleanly to "1"
    (float subtraction must not leave 1.0000000000000018)."""
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(24.9))
    assert list(anidb._episode_index("slime-digression-5233")) == ["1"]


def test_long_runner_keeps_absolute_numbering(anidb, monkeypatch):
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(*range(1, 1173)))
    numbers = anidb._episode_numbers("one-piece-3880")
    assert (len(numbers), numbers[0], numbers[-1]) == (1172, "1", "1172")


def test_malformed_episode_entries_are_dropped(anidb, monkeypatch):
    monkeypatch.setattr(
        anidb,
        "_get_json",
        lambda url: {
            "episodes": [
                {"id": 1, "number": 1},
                {"id": None, "number": 2},  # no id
                {"id": 3, "number": None},  # no number
                "junk",
            ]
        },
    )
    assert anidb._episode_index("x-1") == {"1": 1}


def test_episode_list_is_cached_per_show(anidb, monkeypatch):
    calls = []

    def _json(url):
        calls.append(url)
        return _eps(1, 2, 3)

    monkeypatch.setattr(anidb, "_get_json", _json)
    anidb._episode_numbers("x-1")
    anidb._episode_numbers("x-1")
    assert len(calls) == 1


# ---- get -----------------------------------------------------------------


def test_get_offers_the_episode_list_for_sub_and_dub(anidb, monkeypatch):
    """Dub availability is per episode and only visible at stream time, so both
    lists are offered and a missing dub degrades to the nyaa fallback."""
    monkeypatch.setattr(anidb, "_get_json", lambda url: _eps(1, 2, 3))
    anime = anidb.get(AnimeParams(id="x-1", query="X"))
    assert anime.episodes.sub == ["1", "2", "3"]
    assert anime.episodes.dub == anime.episodes.sub
    assert [e.episode for e in anime.episodes_info] == ["1", "2", "3"]


def test_get_returns_none_when_show_has_no_episodes(anidb, monkeypatch):
    monkeypatch.setattr(anidb, "_get_json", lambda url: {"episodes": []})
    assert anidb.get(AnimeParams(id="x-1", query="X")) is None


# ---- streams -------------------------------------------------------------


def _stub_streams(anidb, monkeypatch, languages):
    def _json(url):
        if "/episodes" in url:
            return _eps(*range(29, 39))
        return {"languages": languages}

    monkeypatch.setattr(anidb, "_get_json", _json)
    monkeypatch.setattr(
        anidb,
        "_get",
        lambda url: MASTER_M3U8 if "m3u8" in url else "... file: 'https://h/master.m3u8' ...",
    )


JPN = {"code": "jpn", "name": "Japanese", "embed_url": "https://anidb.app/embed/jp"}
ENG = {"code": "eng", "name": "English", "embed_url": "https://anidb.app/embed/en"}


def test_episode_streams_returns_qualities_best_first(anidb, monkeypatch):
    _stub_streams(anidb, monkeypatch, [ENG, JPN])
    servers = list(
        anidb.episode_streams(
            EpisodeStreamsParams(query="Frieren", anime_id="frieren-1665", episode="1")
        )
    )
    assert len(servers) == 1
    server = servers[0]
    assert server.name == "anidb"
    # Best first: several call sites take links[0] instead of filtering.
    assert [link.quality for link in server.links] == ["1080", "720", "360"]
    assert all(link.hls for link in server.links)
    # The I-FRAME variant is not a playable rendition and must be excluded.
    assert not any("iframes" in link.link for link in server.links)
    assert server.headers["Referer"].startswith("https://anidb.app")


def test_episode_streams_picks_the_language_for_the_translation_type(
    anidb, monkeypatch
):
    seen = []

    def _get(url):
        seen.append(url)
        return MASTER_M3U8 if "m3u8" in url else "file: 'https://h/master.m3u8'"

    _stub_streams(anidb, monkeypatch, [ENG, JPN])
    monkeypatch.setattr(anidb, "_get", _get)

    list(
        anidb.episode_streams(
            EpisodeStreamsParams(
                query="F", anime_id="f-1665", episode="1", translation_type="dub"
            )
        )
    )
    assert seen[0].endswith("/embed/en")

    seen.clear()
    list(
        anidb.episode_streams(
            EpisodeStreamsParams(
                query="F", anime_id="f-1665", episode="1", translation_type="sub"
            )
        )
    )
    assert seen[0].endswith("/embed/jp")


def test_episode_streams_none_when_dub_missing(anidb, monkeypatch):
    """No English track -> no servers, which drops through to nyaa."""
    _stub_streams(anidb, monkeypatch, [JPN])
    assert (
        anidb.episode_streams(
            EpisodeStreamsParams(
                query="F", anime_id="f-1665", episode="1", translation_type="dub"
            )
        )
        is None
    )


def test_episode_streams_none_for_unknown_episode(anidb, monkeypatch):
    _stub_streams(anidb, monkeypatch, [JPN])
    assert (
        anidb.episode_streams(
            EpisodeStreamsParams(query="F", anime_id="f-1665", episode="999")
        )
        is None
    )


def test_episode_streams_none_for_unparsable_episode(anidb, monkeypatch):
    _stub_streams(anidb, monkeypatch, [JPN])
    assert (
        anidb.episode_streams(
            EpisodeStreamsParams(query="F", anime_id="f-1665", episode="latest")
        )
        is None
    )


def test_single_rendition_master_is_used_directly(anidb, monkeypatch):
    """An upload with no variant lines still plays: the master URL is the stream."""

    def _json(url):
        return _eps(1) if "/episodes" in url else {"languages": [JPN]}

    monkeypatch.setattr(anidb, "_get_json", _json)
    monkeypatch.setattr(
        anidb,
        "_get",
        lambda url: "#EXTM3U\n#EXTINF:10\nseg1.ts\n"
        if "m3u8" in url
        else "file: 'https://h/master.m3u8'",
    )
    servers = list(
        anidb.episode_streams(
            EpisodeStreamsParams(query="X", anime_id="x-1", episode="1")
        )
    )
    assert [link.link for link in servers[0].links] == ["https://h/master.m3u8"]


def test_embed_without_master_playlist_yields_no_servers(anidb, monkeypatch):
    def _json(url):
        return _eps(1) if "/episodes" in url else {"languages": [JPN]}

    monkeypatch.setattr(anidb, "_get_json", _json)
    monkeypatch.setattr(anidb, "_get", lambda url: "<html>player unavailable</html>")
    assert (
        anidb.episode_streams(
            EpisodeStreamsParams(query="X", anime_id="x-1", episode="1")
        )
        is None
    )
