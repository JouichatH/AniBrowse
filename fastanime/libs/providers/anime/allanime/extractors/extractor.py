from abc import ABC, abstractmethod
from logging import getLogger

from ...types import Server
from ..types import AllAnimeEpisode, AllAnimeSource
from ..utils import one_digit_symmetric_xor
from .ak import AkExtractor

logger = getLogger(__name__)


class BaseExtractor(ABC):
    @abstractmethod
    @classmethod
    def extract(cls, url, client, episode_number, episode, source) -> Server:
        pass


AVAILABLE_SOURCES = {
    "Sak": AkExtractor,
    "S-mp4": AkExtractor,
    "Luf-mp4": AkExtractor,
    "Default": AkExtractor,
    "Yt-mp4": AkExtractor,
    "Kir": AkExtractor,
    "Mp4": AkExtractor,
}
OTHER_SOURCES = {"Ak": AkExtractor, "Vid-mp4": "", "Ok": "", "Ss-Hls": "", "Fm-Hls": ""}


def extract_server(
    client, episode_number: str, episode: AllAnimeEpisode, source: AllAnimeSource
) -> Server | None:
    url = source.get("sourceUrl")
    if not url:
        logger.debug(f"Url not found in source: {source}")
        return

    if url.startswith("--"):
        url = one_digit_symmetric_xor(56, url[2:])

        logger.debug(f"Decrypting url for source: {source['sourceName']}")
    if source["sourceName"] in OTHER_SOURCES:
        logger.debug(f"Found  {source['sourceName']} but ignoring")
        return

    if source["sourceName"] not in AVAILABLE_SOURCES:
        logger.debug(
            f"Found  {source['sourceName']} but did not expect it, its time to scrape lol"
        )
        return
    logger.debug(f"Found  {source['sourceName']}")

    return AVAILABLE_SOURCES[source["sourceName"]].extract(
        url, client, episode_number, episode, source
    )
