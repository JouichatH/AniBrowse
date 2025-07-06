import re
from importlib import resources
from pathlib import Path

SERVERS_AVAILABLE = [
    "sharepoint",
    "dropbox",
    "gogoanime",
    "weTransfer",
    "wixmp",
    "Yt",
    "mp4-upload",
]
API_BASE_URL = "allanime.day"
API_GRAPHQL_REFERER = "https://allanime.to/"
API_GRAPHQL_ENDPOINT = f"https://api.{API_BASE_URL}/api/"

# search constants
DEFAULT_COUNTRY_OF_ORIGIN = "all"
DEFAULT_NSFW = True
DEFAULT_UNKNOWN = True
DEFAULT_PER_PAGE = 40
DEFAULT_PAGE = 1

# regex stuff
MP4_SERVER_JUICY_STREAM_REGEX = re.compile(
    r"video/mp4\",src:\"(https?://.*/video\.mp4)\""
)

# graphql files
GQLS = resources.files("fastanime.libs.anime_provider.allanime")
SEARCH_GQL = Path(str(GQLS / "search.gql"))
ANIME_GQL = Path(str(GQLS / "anime.gql"))
EPISODE_GQL = Path(str(GQLS / "episode.gql"))
