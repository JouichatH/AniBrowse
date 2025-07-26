from ..config.model import DownloadsConfig
from ..exceptions import FastAnimeError
from .base import BaseDownloader

DOWNLOADERS = ["auto", "default", "yt-dlp"]


class DownloadFactory:
    @staticmethod
    def create(config: DownloadsConfig) -> BaseDownloader:
        """
        Factory to create a downloader instance based on the configuration.
        """
        downloader_name = config.downloader
        if downloader_name not in DOWNLOADERS:
            raise FastAnimeError(
                f"Unsupported selector: '{downloader_name}'.Available selectors are: {DOWNLOADERS}"
            )

        if downloader_name == "yt-dlp":
            from .yt_dlp import YtDLPDownloader

            return YtDLPDownloader(config)
        elif downloader_name == "default":
            from .default import DefaultDownloader

            return DefaultDownloader(config)
        elif downloader_name == "auto":
            # Auto mode: prefer yt-dlp if available, fallback to default
            try:
                import yt_dlp
                from .yt_dlp import YtDLPDownloader

                return YtDLPDownloader(config)
            except ImportError:
                from .default import DefaultDownloader

                return DefaultDownloader(config)
        else:
            raise FastAnimeError("Downloader not implemented")


# Simple alias for ease of use
create_downloader = DownloadFactory.create
