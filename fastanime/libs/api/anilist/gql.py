# -*- coding: utf-8 -*-
"""
GraphQL Path Registry for the AniList API Client.

This module uses `importlib.resources` to create robust, cross-platform
`pathlib.Path` objects for every .gql file in the `queries` and `mutations`
directories. This provides a single, type-safe source of truth for all
GraphQL operations, making the codebase easier to maintain and validate.

Constants are named to reflect the action they perform, e.g.,
`SEARCH_MEDIA` points to the `search.gql` file.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

# --- Base Paths ---
# Safely access package data directories using the standard library.
_QUERIES_PATH = resources.files("fastanime.libs.api.anilist") / "queries"
_MUTATIONS_PATH = resources.files("fastanime.libs.api.anilist") / "mutations"


# --- Queries ---
# Each constant is a Path object pointing to a specific .gql query file.
GET_AIRING_SCHEDULE: Path = _QUERIES_PATH / "airing.gql"
GET_ANIME_DETAILS: Path = _QUERIES_PATH / "anime.gql"
GET_CHARACTERS: Path = _QUERIES_PATH / "character.gql"
GET_FAVOURITES: Path = _QUERIES_PATH / "favourite.gql"
GET_MEDIA_LIST_ITEM: Path = _QUERIES_PATH / "get-medialist-item.gql"
GET_LOGGED_IN_USER: Path = _QUERIES_PATH / "logged-in-user.gql"
GET_MEDIA_LIST: Path = _QUERIES_PATH / "media-list.gql"
GET_MEDIA_RELATIONS: Path = _QUERIES_PATH / "media-relations.gql"
GET_NOTIFICATIONS: Path = _QUERIES_PATH / "notifications.gql"
GET_POPULAR: Path = _QUERIES_PATH / "popular.gql"
GET_RECENTLY_UPDATED: Path = _QUERIES_PATH / "recently-updated.gql"
GET_RECOMMENDATIONS: Path = _QUERIES_PATH / "recommended.gql"
GET_REVIEWS: Path = _QUERIES_PATH / "reviews.gql"
GET_SCORES: Path = _QUERIES_PATH / "score.gql"
SEARCH_MEDIA: Path = _QUERIES_PATH / "search.gql"
GET_TRENDING: Path = _QUERIES_PATH / "trending.gql"
GET_UPCOMING: Path = _QUERIES_PATH / "upcoming.gql"
GET_USER_INFO: Path = _QUERIES_PATH / "user-info.gql"


# --- Mutations ---
# Each constant is a Path object pointing to a specific .gql mutation file.
DELETE_MEDIA_LIST_ENTRY: Path = _MUTATIONS_PATH / "delete-list-entry.gql"
MARK_NOTIFICATIONS_AS_READ: Path = _MUTATIONS_PATH / "mark-read.gql"
SAVE_MEDIA_LIST_ENTRY: Path = _MUTATIONS_PATH / "media-list.gql"
