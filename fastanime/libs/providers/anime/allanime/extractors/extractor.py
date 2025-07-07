from abc import ABC, abstractmethod
from logging import getLogger

from ...types import Server
from ..types import AllAnimeEpisode, AllAnimeSource
from ..utils import one_digit_symmetric_xor
from .ak import AkExtractor
from .dropbox import SakExtractor
from .filemoon import FmHlsExtractor, OkExtractor
from .gogoanime import Lufmp4Extractor
from .mp4_upload import Mp4Extractor
from .sharepoint import Smp4Extractor
from .streamsb import SsHlsExtractor
from .vid_mp4 import VidMp4Extractor
from .we_transfer import KirExtractor
from .wixmp import DefaultExtractor
from .yt_mp4 import YtExtractor

logger = getLogger(__name__)


class BaseExtractor(ABC):
    @abstractmethod
    @classmethod
    def extract(cls, url, client, episode_number, episode, source) -> Server:
        pass


AVAILABLE_SOURCES = {
    "Sak": SakExtractor,
    "S-mp4": Smp4Extractor,
    "Luf-mp4": Lufmp4Extractor,
    "Default": DefaultExtractor,
    "Yt-mp4": YtExtractor,
    "Kir": KirExtractor,
    "Mp4": Mp4Extractor,
}
OTHER_SOURCES = {
    "Ak": AkExtractor,
    "Vid-mp4": VidMp4Extractor,
    "Ok": OkExtractor,
    "Ss-Hls": SsHlsExtractor,
    "Fm-Hls": FmHlsExtractor,
}


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
