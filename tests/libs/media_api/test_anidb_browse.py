"""Tests for the anidb.app browse backend (no network).

This backend exists so browsing and playback share one host and cannot fail
independently - the failure mode that took the whole app down when AniList
disabled its API and Jikan degraded to cache-only on the same day.
"""

import pytest

from viu_media.libs.media_api.anidb import mapper
from viu_media.libs.media_api.anidb.api import AniDBApi
from viu_media.libs.media_api.params import MediaSearchParams
from viu_media.libs.media_api.types import (
    MediaFormat,
    MediaGenre,
    MediaSort,
    MediaStatus,
)

BROWSE_HTML = """
<div class="grid">
<a href="https://anidb.app/anime/one-piece-3880" class="anime-card" title="One Piece">
  <img src="https://cdn.xlsbox.com/poster/small/1/3880.jpg" alt="One Piece">
  <span class="badge badge-orange text-[9px]" style="color:#fff">TV</span>
</a>
<a href="https://anidb.app/anime/frieren-beyond-journeys-end-1663" class="anime-card"
   title="Frieren: Beyond Journey&#039;s End">
  <img src="https://cdn.xlsbox.com/poster/small/1/1663.jpg" alt="Frieren">
  <span class="badge badge-orange text-[9px]" style="color:#fff">Movie</span>
</a>
</div>
<nav><a href="https://anidb.app/browse?sort=order_trending&amp;page=2">Next</a></nav>
"""

# anidb's JSON-LD is not valid JSON: it HTML-escapes the apostrophe but keeps
# the backslash, yielding \\&#039; . The mapper must repair that.
DETAIL_HTML = """
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "TVSeries",
    "name": "Frieren: Beyond Journey\\&#039;s End",
    "alternateName": "Sousou no Frieren",
    "description": "During their decade-long quest...",
    "image": "https://cdn.xlsbox.com/poster/small/1/1663.jpg",
    "genre": ["Drama", "Adventure", "Fantasy", "Award Winning"]
}
</script>
<a href="https://myanimelist.net/anime/52991/x">MAL</a>
<span>Status</span><span>Finished Airing</span>
"""


def _page(html=BROWSE_HTML, current_page=1):
    """Map a browse page and assert it parsed, so tests read without None-guards."""
    result = mapper.to_search_result(html, current_page=current_page)
    assert result is not None
    return result


@pytest.fixture
def api():
    return AniDBApi.__new__(AniDBApi)  # routing/parsing need no HTTP client


# ---- card parsing --------------------------------------------------------


def test_cards_become_media_items():
    result = _page()
    assert [m.id for m in result.media] == [3880, 1663]
    assert result.media[0].title.english == "One Piece"
    # HTML entities decoded, else fuzzy matching against the provider fails.
    assert result.media[1].title.english == "Frieren: Beyond Journey's End"
    assert result.media[0].format is MediaFormat.TV
    assert result.media[1].format is MediaFormat.MOVIE


def test_numeric_id_is_the_slug_tail():
    """The trailing number is stable per entry, so it keys the watch registry."""
    assert mapper.numeric_id("frieren-beyond-journeys-end-1663") == 1663
    assert mapper.numeric_id("no-number-here") == 0


def test_card_without_a_numeric_id_is_skipped():
    assert mapper.card_to_media_item({"slug": "broken-slug", "title": "x"}) is None


def test_pagination_survives_html_escaped_hrefs():
    """anidb writes "&amp;page=2"; matching only [?&]page= saw no next page."""
    assert _page(current_page=1).page_info.has_next_page is True
    # No link beyond page 2, so page 2 is the last one.
    assert _page(current_page=2).page_info.has_next_page is False


def test_cloudflare_challenge_is_reported_not_parsed(caplog):
    assert mapper.to_search_result("<title>Just a moment...</title>") is None
    assert "Cloudflare" in caplog.text


# ---- detail enrichment ---------------------------------------------------


def _enriched():
    return mapper.enrich_from_detail(_page().media[1], DETAIL_HTML)


def test_malformed_jsonld_is_repaired_and_used():
    item = _enriched()
    assert item.title.english == "Frieren: Beyond Journey's End"
    assert item.title.romaji == "Sousou no Frieren"
    assert item.description is not None
    assert item.description.startswith("During their decade-long quest")


def test_unknown_genres_are_dropped_not_fatal():
    """"Award Winning" is not in MediaGenre; passing it raises and would lose
    the whole page."""
    assert _enriched().genres == [
        MediaGenre.DRAMA,
        MediaGenre.ADVENTURE,
        MediaGenre.FANTASY,
    ]


def test_status_and_mal_id_are_picked_up():
    item = _enriched()
    assert item.status is MediaStatus.FINISHED
    assert item.id_mal == 52991


def test_romaji_is_offered_as_a_synonym_for_provider_search():
    assert "Sousou no Frieren" in _enriched().synonymns


def test_unparseable_detail_leaves_the_item_untouched():
    """Enrichment is best-effort; the results list is usable without it."""
    item = _page().media[0]
    assert mapper.enrich_from_detail(item, "<html>nothing here</html>") == item


def test_episode_count_is_never_guessed():
    """A recent-episodes widget once gave One Piece 3 episodes; the provider's
    episode list is the only authority."""
    assert _enriched().episodes is None


# ---- query building ------------------------------------------------------


def _q(api, **kwargs):
    return api._query(MediaSearchParams(**kwargs))


def test_each_category_maps_to_a_distinct_anidb_sort(api):
    assert _q(api, sort=MediaSort.TRENDING_DESC) == "sort=order_trending"
    assert _q(api, sort=MediaSort.POPULARITY_DESC) == "sort=order_popular"
    assert _q(api, sort=MediaSort.SCORE_DESC) == "sort=order_top"
    assert _q(api, sort=MediaSort.FAVOURITES_DESC) == "sort=order_favorite"
    assert _q(api, sort=MediaSort.UPDATED_AT_DESC) == "sort=order_updated"


def test_query_and_page_are_carried(api):
    assert _q(api, query="frieren") == "q=frieren"
    assert "page=3" in _q(api, sort=MediaSort.TRENDING_DESC, page=3)
    # Page 1 is the default and stays out of the URL.
    assert "page=" not in _q(api, sort=MediaSort.TRENDING_DESC, page=1)


def test_status_filter_maps_to_anidb_wording(api):
    assert _q(api, status=MediaStatus.RELEASING) == "status=Currently+Airing"
    assert _q(api, status=MediaStatus.FINISHED) == "status=Finished+Airing"


def test_upcoming_falls_back_to_newest_first(api):
    """anidb's catalogue only knows airing vs finished, so "not yet released"
    is approximated rather than silently returning the wrong list."""
    assert _q(api, status=MediaStatus.NOT_YET_RELEASED) == "sort=aired_start"


def test_genre_filter_uses_anidbs_numeric_ids(api):
    assert _q(api, genre_in=[MediaGenre.ACTION]) == "genres=1"
    # A genre anidb has no id for is dropped rather than sent as a name.
    assert _q(api, genre_in=[MediaGenre.MAHOU_SHOUJO]) == ""


def test_sort_list_uses_the_first_entry(api):
    assert _q(api, sort=[MediaSort.POPULARITY_DESC]) == "sort=order_popular"


def test_unknown_sort_is_omitted_rather_than_guessed(api):
    assert _q(api, sort=MediaSort.DURATION) == ""


# ---- account surface -----------------------------------------------------


def test_account_features_degrade_to_none_so_lists_stay_local(api):
    """search_media_list returning None is what makes the menus fall back to
    the on-disk registry."""
    assert api.is_authenticated() is False
    assert api.get_viewer_profile() is None
    assert api.search_media_list(None) is None
    assert api.update_list_entry(None) is False
    assert api.get_notifications() is None
