"""Tests for the nyaa source-fallback helpers (provider mocked)."""

import viu_media.cli.interactive.menu.media._source_fallback as sf
from tests.support.fakes import FakeAnimeProvider, make_server
from viu_media.libs.provider.anime.types import (
    AnimeEpisodes,
    PageInfo,
    SearchResult,
    SearchResults,
)


# ---- _as_float -----------------------------------------------------------


def test_as_float_parses_and_defaults_to_zero():
    assert sf._as_float("12") == 12.0
    assert sf._as_float("5.5") == 5.5
    assert sf._as_float("garbage") == 0.0
    assert sf._as_float(None) == 0.0  # type: ignore[arg-type]


# ---- merge_episodes ------------------------------------------------------


def test_merge_episodes_union_sorted_numeric():
    assert sf.merge_episodes(["1", "2", "10"], ["3", "2", "11"]) == [
        "1", "2", "3", "10", "11",
    ]


def test_merge_episodes_dedupes_against_base():
    assert sf.merge_episodes(["1", "2"], ["2", "3"]) == ["1", "2", "3"]


def test_merge_episodes_empty_extra_returns_base_sorted():
    assert sf.merge_episodes(["10", "2", "1"], []) == ["1", "2", "10"]


# ---- nyaa_servers --------------------------------------------------------


def test_nyaa_servers_returns_list(monkeypatch):
    provider = FakeAnimeProvider(
        servers={"3": [make_server(name="TOP", link="magnet:ep3")]}
    )
    monkeypatch.setattr(sf, "_nyaa", lambda: provider)

    servers = sf.nyaa_servers("show", "3")
    assert [s.links[0].link for s in servers] == ["magnet:ep3"]


def test_nyaa_servers_swallows_errors(monkeypatch):
    class Boom:
        def episode_streams(self, params):
            raise RuntimeError("nyaa down")

    monkeypatch.setattr(sf, "_nyaa", lambda: Boom())
    assert sf.nyaa_servers("show", "3") == []


def test_nyaa_servers_empty_when_iterator_none(monkeypatch):
    provider = FakeAnimeProvider(servers={})  # episode_streams -> None
    monkeypatch.setattr(sf, "_nyaa", lambda: provider)
    assert sf.nyaa_servers("show", "99") == []


# ---- nyaa_extra_episodes -------------------------------------------------


def _search_results(*eps):
    return SearchResults(
        page_info=PageInfo(total=1),
        results=[
            SearchResult(
                id="show", title="show", episodes=AnimeEpisodes(sub=list(eps))
            )
        ],
    )


def test_nyaa_extra_episodes_only_new_and_within_last_aired(monkeypatch):
    class Prov:
        def search(self, params):
            return _search_results("1", "2", "3", "4", "5")

    monkeypatch.setattr(sf, "_nyaa", lambda: Prov())

    # Have 1-3 already; nyaa has up to 5; last aired is 4.
    extra = sf.nyaa_extra_episodes("show", ["1", "2", "3"], last_aired=4)
    assert extra == ["4"]  # 5 is beyond last_aired, 1-3 already present


def test_nyaa_extra_episodes_empty_when_no_results(monkeypatch):
    class Prov:
        def search(self, params):
            return None

    monkeypatch.setattr(sf, "_nyaa", lambda: Prov())
    assert sf.nyaa_extra_episodes("show", ["1"], last_aired=12) == []


def test_nyaa_extra_episodes_swallows_errors(monkeypatch):
    class Prov:
        def search(self, params):
            raise RuntimeError("down")

    monkeypatch.setattr(sf, "_nyaa", lambda: Prov())
    assert sf.nyaa_extra_episodes("show", ["1"], last_aired=12) == []
