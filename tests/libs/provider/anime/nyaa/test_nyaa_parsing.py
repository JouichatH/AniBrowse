"""Tests for nyaa's pure parsing/ranking logic (no network).

The network boundary is ``Nyaa._items_for`` / ``_fetch``; everything else -
query-variant generation, the episode/batch regexes, group ranking, episode
collation and the ``episode_streams`` candidate sort - is pure and tested here
by feeding synthetic item dicts.
"""

import pytest

from viu_media.libs.provider.anime.nyaa.provider import (
    _BATCH_RANGE_RE,
    _BATCH_RE,
    _EP_RE,
    Nyaa,
)
from viu_media.libs.provider.anime.params import EpisodeStreamsParams, SearchParams


@pytest.fixture
def nyaa():
    # No httpx client: these tests never touch the network.
    return Nyaa(client=None)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _clear_rss_cache():
    # _fetch caches RSS per query at module level; keep tests independent.
    from viu_media.libs.provider.anime.nyaa import provider as mod

    mod._rss_cache.clear()
    yield
    mod._rss_cache.clear()


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


def test_variants_ordinal_season_title():
    """AniList "X 4th Season" must not produce the unmatchable "X 4th S4"
    (this made a real Slime S4 lookup return nothing), and must include the
    fansub "4th Season" naming plus the bare root (season filter narrows it).
    """
    variants = Nyaa._search_variants("Tensei Shitara Slime Datta Ken 4th Season")
    assert variants[0] == "Tensei Shitara Slime Datta Ken S4"
    assert "Tensei Shitara Slime Datta Ken Season 4" in variants
    assert "Tensei Shitara Slime Datta Ken 4th Season" in variants
    assert "Tensei Shitara Slime Datta Ken" in variants
    assert not any("4th S4" in v for v in variants)


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


# ---- batch torrents ------------------------------------------------------


def _batch(group, res, seeders, start, end, hash="b"):
    return {
        "title": f"[{group}] Show ({start:02d}-{end:02d}) ({res}p) [Batch]",
        "hash": hash,
        "seeders": seeders,
        "group": group,
        "res": res,
        "ep": None,
        "batch": True,
        "batch_start": start,
        "batch_end": end,
    }


def test_batch_range_regex_captures_bounds():
    m = _BATCH_RANGE_RE.search("[X] Show (01-28) (1080p) [Batch]")
    assert m and (int(m.group(1)), int(m.group(2))) == (1, 28)
    m2 = _BATCH_RANGE_RE.search("[X] Show [05~10] 720p")
    assert m2 and (int(m2.group(1)), int(m2.group(2))) == (5, 10)


def test_episodes_expands_batch_ranges_and_merges_singles():
    items = [_batch("SubsPlease", "1080", 100, 1, 3), _item("SubsPlease", "1080", 5, ep="4")]
    # Batch 1-3 expanded, single ep 4 merged, sorted numeric, deduped.
    assert Nyaa._episodes(items) == ["1", "2", "3", "4"]


def test_episode_streams_falls_back_to_batch_with_marker(nyaa, monkeypatch):
    items = [_batch("SubsPlease", "1080", 126, 1, 28, hash="pack")]
    monkeypatch.setattr(nyaa, "_items_for", lambda q: items)
    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="7", translation_type="sub", quality="1080"
    )
    servers = list(nyaa.episode_streams(params) or [])
    assert servers, "batch should cover episode 7"
    assert "batch" in servers[0].name
    # The magnet is tagged so the player streams only episode 7 out of the pack.
    assert "x.aniep=7" in servers[0].links[0].link


def test_episode_streams_prefers_single_over_batch(nyaa, monkeypatch):
    items = [
        _batch("SubsPlease", "1080", 999, 1, 28, hash="pack"),
        _item("SubsPlease", "1080", 5, ep="7", hash="single"),
    ]
    monkeypatch.setattr(nyaa, "_items_for", lambda q: items)
    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="7", translation_type="sub", quality="1080"
    )
    servers = list(nyaa.episode_streams(params) or [])
    # Single-episode torrent wins even with far fewer seeders; no batch marker.
    assert "urn:btih:single" in servers[0].links[0].link
    assert all("x.aniep" not in s.links[0].link for s in servers)


def test_episode_streams_batch_out_of_range_returns_none(nyaa, monkeypatch):
    monkeypatch.setattr(nyaa, "_items_for", lambda q: [_batch("SubsPlease", "1080", 10, 1, 12)])
    params = EpisodeStreamsParams(
        anime_id="show", query="show", episode="20", translation_type="sub", quality="1080"
    )
    assert nyaa.episode_streams(params) is None


def test_search_lists_episodes_for_batch_only_show(nyaa, monkeypatch):
    monkeypatch.setattr(nyaa, "_items_for", lambda q: [_batch("SubsPlease", "1080", 126, 1, 4)])
    result = nyaa.search(SearchParams(query="frieren"))
    assert result and result.results
    assert result.results[0].episodes.sub == ["1", "2", "3", "4"]


# ---- season consistency (E1) ---------------------------------------------


@pytest.mark.parametrize(
    "title, season",
    [
        ("[SubsPlease] Sousou no Frieren S2 (01-10) (1080p) [Batch]", 2),
        ("[Erai-raws] Show 2nd Season - 07 [1080p]", 2),
        ("[X] Show Season 3 - 01 (720p)", 3),
        ("Mushoku Tensei III: Isekai Ittara Honki Dasu", 3),
        ("Spy x Family Part 2", 2),
        ("[SubsPlease] Sousou no Frieren (01-28) (1080p) [Batch]", None),
        ("[X] Show S01E03 something", None),  # S01E03 has no word boundary
    ],
)
def test_season_of(title, season):
    assert Nyaa._season_of(title) == season


def test_items_for_drops_other_season_items(nyaa, monkeypatch):
    """A season-less query must not pick up S2 releases covering the same
    episode NUMBERS (they would play a different season's episode)."""
    rss = [
        _batch("SubsPlease", "1080", 291, 1, 10, hash="s2pack"),
        _item("SubsPlease", "1080", 999, ep="7", hash="s2single"),
        _batch("SubsPlease", "1080", 126, 1, 28, hash="s1pack"),
    ]
    rss[0]["title"] = "[SubsPlease] Sousou no Frieren S2 (01-10) (1080p) [Batch]"
    rss[1]["title"] = "[SubsPlease] Sousou no Frieren S2 - 07 (1080p)"
    rss[2]["title"] = "[SubsPlease] Sousou no Frieren (01-28) (1080p) [Batch]"
    monkeypatch.setattr(nyaa, "_fetch", lambda q: rss)

    items = nyaa._items_for("Sousou no Frieren")
    assert [i["hash"] for i in items] == ["s1pack"]

    # And the S2 query keeps only the S2 items.
    items2 = nyaa._items_for("Sousou no Frieren Season 2")
    assert sorted(i["hash"] for i in items2) == ["s2pack", "s2single"]


def test_items_for_unmarked_counts_as_season_one(nyaa, monkeypatch):
    """A '(Season 1)'-labelled pack still matches a season-less query."""
    rss = [_batch("Judas", "1080", 50, 1, 28, hash="s1labeled")]
    rss[0]["title"] = "[Judas] Sousou no Frieren (Season 1) (01-28) [1080p]"
    monkeypatch.setattr(nyaa, "_fetch", lambda q: rss)
    assert [i["hash"] for i in nyaa._items_for("Sousou no Frieren")] == ["s1labeled"]


# ---- batch range sanity (E4) ---------------------------------------------


def _rss_xml(titles):
    items = "".join(
        f"<item><title>{t}</title>"
        f"<nyaa:infoHash xmlns:nyaa='https://nyaa.si/xmlns/nyaa'>{'a' * 40}</nyaa:infoHash>"
        f"<link>https://nyaa.si/download/1.torrent</link>"
        f"<nyaa:seeders xmlns:nyaa='https://nyaa.si/xmlns/nyaa'>5</nyaa:seeders></item>"
        for t in titles
    )
    return f"<rss><channel>{items}</channel></rss>"


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    def __init__(self, text):
        self._text = text

    def get(self, url, timeout=None):
        return _FakeResp(self._text)


def test_fetch_rejects_year_and_huge_ranges():
    ny = Nyaa(client=_FakeClient(_rss_xml([
        "[X] Show (1999-2023) [BD] (1080p)",     # year span
        "[X] Show (001-500) (1080p) [Batch]",    # implausible span
        "[X] Show (01-28) (1080p) [Batch]",      # legit
    ])))  # type: ignore[arg-type]
    items = ny._fetch("show")
    spans = [(i["batch_start"], i["batch_end"]) for i in items]
    assert spans == [(None, None), (None, None), (1, 28)]


def test_fetch_captures_torrent_url():
    ny = Nyaa(client=_FakeClient(_rss_xml(["[X] Show - 03 (1080p)"])))  # type: ignore[arg-type]
    items = ny._fetch("show")
    assert items[0]["torrent_url"] == "https://nyaa.si/download/1.torrent"


class _CountingClient(_FakeClient):
    def __init__(self, text):
        super().__init__(text)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return super().get(url, timeout)


def test_fetch_caches_rss_per_query(monkeypatch):
    import viu_media.libs.provider.anime.nyaa.provider as mod

    monkeypatch.setattr(mod, "_rss_cache", {})  # isolate from other tests
    client = _CountingClient(_rss_xml(["[X] Show - 03 (1080p)"]))
    ny = Nyaa(client=client)  # type: ignore[arg-type]
    first = ny._fetch("Show")
    again = ny._fetch("show")  # case-insensitive hit
    assert client.calls == 1
    assert again == first
    # Expired entries re-fetch.
    mod._rss_cache["show"] = (mod.time.monotonic() - mod._RSS_TTL - 1, first)
    ny._fetch("show")
    assert client.calls == 2


# ---- magnet construction (O1) --------------------------------------------


def test_magnet_embeds_xs_and_marker():
    mag = Nyaa._magnet(
        "a" * 40, "Show (01-28)", select_ep="7",
        torrent_url="https://nyaa.si/download/123.torrent",
    )
    assert "xs=https%3A%2F%2Fnyaa.si%2Fdownload%2F123.torrent" in mag
    assert "x.aniep=7" in mag


def test_magnet_omits_optional_params():
    mag = Nyaa._magnet("a" * 40, "Show - 03")
    assert "xs=" not in mag and "x.aniep" not in mag
