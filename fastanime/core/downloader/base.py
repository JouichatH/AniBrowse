from abc import ABC, abstractmethod

import httpx

from ..config.model import DownloadsConfig
from .params import DownloadParams


class BaseDownloader(ABC):
    client: httpx.Client

    def __init__(self, config: DownloadsConfig):
        self.config = config

        self.client = httpx.Client()

    @abstractmethod
    def download(self, params: DownloadParams):
        pass
