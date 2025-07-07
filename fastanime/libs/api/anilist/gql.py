from ....core.constants import APP_DIR

_ANILIST_PATH = APP_DIR / "libs" / "api" / "anilist"
_QUERIES_PATH = _ANILIST_PATH / "queries"
_MUTATIONS_PATH = _ANILIST_PATH / "mutations"


GET_AIRING_SCHEDULE = _QUERIES_PATH / "airing.gql"
GET_ANIME_DETAILS = _QUERIES_PATH / "anime.gql"
GET_CHARACTERS = _QUERIES_PATH / "character.gql"
GET_FAVOURITES = _QUERIES_PATH / "favourite.gql"
GET_MEDIA_LIST_ITEM = _QUERIES_PATH / "get-medialist-item.gql"
GET_LOGGED_IN_USER = _QUERIES_PATH / "logged-in-user.gql"
GET_USER_MEDIA_LIST = _QUERIES_PATH / "media-list.gql"
GET_MEDIA_RELATIONS = _QUERIES_PATH / "media-relations.gql"
GET_NOTIFICATIONS = _QUERIES_PATH / "notifications.gql"
GET_POPULAR = _QUERIES_PATH / "popular.gql"
GET_RECENTLY_UPDATED = _QUERIES_PATH / "recently-updated.gql"
GET_RECOMMENDATIONS = _QUERIES_PATH / "recommended.gql"
GET_REVIEWS = _QUERIES_PATH / "reviews.gql"
GET_SCORES = _QUERIES_PATH / "score.gql"
SEARCH_MEDIA = _QUERIES_PATH / "search.gql"
GET_TRENDING = _QUERIES_PATH / "trending.gql"
GET_UPCOMING = _QUERIES_PATH / "upcoming.gql"
GET_USER_INFO = _QUERIES_PATH / "user-info.gql"


DELETE_MEDIA_LIST_ENTRY = _MUTATIONS_PATH / "delete-list-entry.gql"
MARK_NOTIFICATIONS_AS_READ = _MUTATIONS_PATH / "mark-read.gql"
SAVE_MEDIA_LIST_ENTRY = _MUTATIONS_PATH / "media-list.gql"
