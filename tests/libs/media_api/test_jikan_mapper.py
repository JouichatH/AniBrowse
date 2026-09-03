"""Tests for the Jikan (MyAnimeList) backend.

Jikan is the fallback when AniList is unreachable. MAL's payloads differ from
AniList's in ways that used to be fatal - most importantly MAL ships genres our
enum has never heard of, which raised inside the pydantic model and lost the
whole results page rather than one field.
"""

from viu_media.libs.media_api.jikan import mapper
from viu_media.libs.media_api.jikan.api import _ORDER_BY, _TOP_FILTERS, JikanApi
from viu_media.libs.media_api.params import MediaSearchParams
from viu_media.libs.media_api.types import MediaFormat, MediaSort, MediaStatus


def _entry(**overrides):
    base = {
        "mal_id": 52991,
        "title": "Sousou no Frieren",
        "titles": [
            {"type": "Default", "title": "Sousou no Frieren"},
            {"type": "English", "title": "Frieren: Beyond Journey's End"},
            {"type": "Japanese", "title": "葬送のフリーレン"},
            {"type": "Synonym", "title": "Frieren at the Funeral"},
        ],
        "type": "TV",
        "status": "Finished Airing",
        "episodes": 28,
        "duration": "24 min per ep",
        "score": 9.3,
        "members": 1000,
        "favorites": 50,
        "synopsis": "...",
        "images": {"jpg": {"large_image_url": "https://x/large.jpg", "image_url": "https://x/s.jpg"}},
        "genres": [{"mal_id": 1, "name": "Adventure"}],
        "studios": [{"mal_id": 11, "name": "Madhouse"}],
        "aired": {"from": "2023-09-29T00:00:00+00:00", "to": None},
    }
    base.update(overrides)
    return base


def _page(*entries):
    return {
        "data": list(entries),
        "pagination": {
            "current_page": 1,
            "has_next_page": True,
            "items": {"total": 100, "per_page": 25},
        },
    }


def _result(page):
    """Map a page and assert it succeeded, so tests read without None-guards."""
    result = mapper.to_generic_search_result(page)
    assert result is not None
    return result


# ---- mapping -------------------------------------------------------------


def test_maps_the_core_fields():
    item = _result(_page(_entry())).media[0]
    assert item.id == 52991 and item.id_mal == 52991
    assert item.title.english == "Frieren: Beyond Journey's End"
    assert item.title.romaji == "Sousou no Frieren"
    assert item.episodes == 28
    assert item.status is MediaStatus.FINISHED
    assert item.format is MediaFormat.TV
    assert item.average_score == 9.3
    assert item.cover_image is not None and item.cover_image.large == "https://x/large.jpg"
    assert item.start_date is not None and item.start_date.year == 2023


def test_unknown_mal_genres_are_dropped_not_fatal():
    """MAL ships "Award Winning"/"Suspense"; our enum has neither. Passing one
    to the model raises and would lose the entire page."""
    entry = _entry(
        genres=[
            {"mal_id": 1, "name": "Adventure"},
            {"mal_id": 46, "name": "Award Winning"},
            {"mal_id": 41, "name": "Suspense"},
        ]
    )
    result = _result(_page(entry))
    assert len(result.media) == 1
    assert [g.value for g in result.media[0].genres] == ["Adventure"]


def test_themes_and_demographics_contribute_known_genres():
    entry = _entry(genres=[], themes=[{"mal_id": 2, "name": "Music"}], demographics=[])
    item = _result(_page(entry)).media[0]
    assert [g.value for g in item.genres] == ["Music"]


def test_synonyms_are_carried_for_the_provider_fallback():
    """provider_search retries with synonyms when the main title finds nothing."""
    item = _result(_page(_entry())).media[0]
    assert "Frieren at the Funeral" in item.synonymns
    assert "葬送のフリーレン" in item.synonymns


def test_duration_prose_becomes_minutes():
    assert _result(_page(_entry())).media[0].duration == 24
    odd = _entry(duration="Unknown")
    assert _result(_page(odd)).media[0].duration is None


def test_entry_without_mal_id_is_skipped_not_fatal():
    result = _result(_page(_entry(), {"title": "broken"}))
    assert [m.id for m in result.media] == [52991]


def test_pagination_is_carried():
    info = _result(_page(_entry())).page_info
    assert info.total == 100 and info.has_next_page is True


def test_single_entity_payload_is_wrapped():
    """/anime/{id} returns an object where list endpoints return an array."""
    result = _result({"data": _entry()})
    assert len(result.media) == 1


def test_missing_data_key_returns_none():
    assert mapper.to_generic_search_result({"error": "boom"}) is None


def test_malformed_images_do_not_raise():
    item = _result(_page(_entry(images=None))).media[0]
    assert item.cover_image is not None and item.cover_image.large == ""


# ---- endpoint routing ----------------------------------------------------


def _route(**kwargs):
    api = JikanApi.__new__(JikanApi)  # no HTTP client needed for routing
    return api._route(MediaSearchParams(**kwargs))


def test_each_browse_category_routes_to_a_distinct_endpoint():
    """Every category used to return one identical list because the sort was
    dropped on the floor."""
    assert _route(sort=MediaSort.TRENDING_DESC) == ("/top/anime", {"filter": "airing"})
    assert _route(sort=MediaSort.POPULARITY_DESC) == (
        "/top/anime",
        {"filter": "bypopularity"},
    )
    assert _route(sort=MediaSort.FAVOURITES_DESC) == (
        "/top/anime",
        {"filter": "favorite"},
    )
    # SCORE_DESC is /top/anime's own default ordering, so it sends no filter.
    assert _route(sort=MediaSort.SCORE_DESC) == ("/top/anime", {})


def test_upcoming_routes_by_status():
    assert _route(
        sort=MediaSort.POPULARITY_DESC, status=MediaStatus.NOT_YET_RELEASED
    ) == ("/top/anime", {"filter": "upcoming"})


def test_text_query_always_uses_plain_search():
    """/top/anime ignores q, so a query must never be routed there."""
    assert _route(query="frieren", sort=MediaSort.TRENDING_DESC) == ("/anime", {})


def test_unmapped_sort_falls_back_to_an_explicit_ordering():
    endpoint, extra = _route(sort=MediaSort.UPDATED_AT_DESC)
    assert endpoint == "/anime"
    assert extra == {"order_by": "start_date", "sort": "desc"}


def test_random_ids_become_a_random_page():
    endpoint, extra = _route(id_in=[1, 2, 3])
    assert endpoint == "/anime" and extra["order_by"] == "members"
    assert 1 <= extra["page"] <= 300


def test_sort_tables_only_reference_real_sorts():
    for sort in list(_TOP_FILTERS) + list(_ORDER_BY):
        assert isinstance(sort, MediaSort)
