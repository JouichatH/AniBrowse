"""Tests for nyaa's pure parsing/ranking logic (no network).

The network boundary is ``Nyaa._items_for`` / ``_fetch``; everything else -
query-variant generation, the episode/batch regexes, group ranking, episode
collation and the ``episode_streams`` candidate sort - is pure and tested here
by feeding synthetic item dicts.
"""

import pytest

from viu_media.libs.provider.anime.nyaa.provider import (
    _BATCH_RE,
    _EP_RE,
    Nyaa,
)
from viu_media.libs.provider.anime.params import EpisodeStreamsParams, SearchParams


@pytest.fixture
def nyaa():
    # No httpx client: these tests never touch the network.
    return Nyaa(client=None)  # type: ignore[arg-type]


# ---- _search_variants ----------------------------------------------------


def test_variants_roman_numeral_season():
    variants = Nyaa._search_variants("Mushoku Tensei III: Isekai Ittara Honki Dasu")
    assert variants[0] == "Mushoku Tensei S3"
    assert "Mushoku Tensei Season 3" in variants
    # The ": subtitle" suffix is dropped for the base form.
    assert "Mushoku Tensei III" in variants


def test_variants_numeric_season_and_part():
    assert Nyaa._search_variants("Spy x Family Season 2")[0] == "Spy x Family S2"
    assert Nyaa._search_variants("Attack on Titan Part 2")[0] == "Attack on Titan S2"


def test_variants_plain_title_is_single():
    assert Nyaa._search_variants("One Piece") == ["One Piece"]


def test_variants_are_deduped_case_insensitively():
    variants = Nyaa._search_variants("Naruto")
    assert len(variants) == len({v.lower() for v in variants})


# ---- regexes -------------------------------------------------------------


@pytest.mark.parametrize(
    "title, ep",
    [
        ("[SubsPlease] Foo - 03 (1080p) [ABCD].mkv", "3"),
        ("[Erai-raws] Bar - 12v2 [720p]", "12"),
        ("[Grp] Baz S3 - 05 (1080p)", "5"),
        ("[Y] Show - 5.5 (720p)", "5.5"),
    ],
)
def test_ep_regex_extracts_and_strips_leading_zeros(title, ep):
    m = _EP_RE.search(title)
    assert m and m.group(1) == ep


def test_batch_regex_matches_season_pack():
    assert _BATCH_RE.search("[X] Movie (01-12) [1080p]")
    assert _BATCH_RE.search("[X] Show [01~24] 1080p")
    assert not _BATCH_RE.search("[SubsPlease] Foo - 03 (1080p)")


# ---- _group_rank ---------------------------------------------------------


def test_group_rank_prefers_listed_groups_case_insensitively():
    assert Nyaa._group_rank("SubsPlease") == 0
    assert Nyaa._group_rank("subsplease") == 0
    assert Nyaa._group_rank("Erai-raws") == 1
    # Unknown groups rank last.
    assert Nyaa._group_rank("Nobody") == len(
        __import__(
            "viu_media.libs.provider.anime.nyaa.provider",
            fromlist=["PREFERRED_GROUPS"],
        ).PREFERRED_GROUPS
    )


# ---- _episodes -----------------------------------------------------------


def test_episodes_deduped_sorted_numeric_dropping_none():
    items = [{"ep": "3"}, {"ep": "1"}, {"ep": "10"}, {"ep": None}, {"ep": "2"}, {"ep": "1"}]
    assert Nyaa._episodes(items) == ["1", "2", "3", "10"]


# ---- episode_streams sort ------------------------------------------------


def _item(group, res, seeders, ep="1", hash="abc"):
    return {
        "title": f"[{group}] Show - {ep} ({res}p)",
        "hash": hash,
        "seeders": seeders,
        "group": group,
        "res": res,
        "ep": ep,
        "batch": False,
    }


def test_episode_streams_ranks_group_then_quality_then_seeders(nyaa, monkeypatch):
    items = [
        _item("Nobody", "1080", 500, hash="h1"),      # unknown group
        _item("SubsPlease", "720", 5, hash="h2"),      # best group, wrong quality
        _item("SubsPlease", "1080", 10, hash="h3"),    # best group, right quality
        _item("SubsPlease", "1080", 99, hash="h4"),    # best group, right quality, most seeders
        _item("2", "1080", 1000, ep="2", hash="h5"),   # different episode - excluded
    ]
    monkeypatch.setattr(nyaa, "_items_for", lambda q: items)

    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="1", translation_type="sub", quality="1080"
    )
    servers = list(nyaa.episode_streams(params) or [])

    # Only episode-1 candidates, best-ranked first.
    assert servers, "should yield servers for episode 1"
    assert "SubsPlease" in servers[0].name
    # h4 (right group+quality, most seeders) wins.
    assert "urn:btih:h4" in servers[0].links[0].link
    # The other-episode item never appears.
    assert all("urn:btih:h5" not in s.links[0].link for s in servers)


def test_episode_streams_none_when_episode_absent(nyaa, monkeypatch):
    monkeypatch.setattr(nyaa, "_items_for", lambda q: [_item("SubsPlease", "1080", 5)])
    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="99", translation_type="sub", quality="1080"
    )
    assert nyaa.episode_streams(params) is None


def test_episode_streams_none_for_non_numeric_episode(nyaa, monkeypatch):
    monkeypatch.setattr(nyaa, "_items_for", lambda q: [_item("SubsPlease", "1080", 5)])
    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="Special", translation_type="sub", quality="1080"
    )
    assert nyaa.episode_streams(params) is None


def test_search_returns_episode_list(nyaa, monkeypatch):
    items = [_item("SubsPlease", "1080", 5, ep="1"), _item("Erai-raws", "1080", 3, ep="2")]
    monkeypatch.setattr(nyaa, "_items_for", lambda q: items)
    result = nyaa.search(SearchParams(query="show"))
    assert result and result.results
    assert result.results[0].episodes.sub == ["1", "2"]
