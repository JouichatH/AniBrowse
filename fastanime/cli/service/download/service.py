"""Download service that integrates with the media registry."""

import logging
from pathlib import Path
from typing import Optional

from ....core.config.model import AppConfig, DownloadsConfig
from ....core.downloader.base import BaseDownloader
from ....core.downloader.downloader import create_downloader
from ....core.downloader.params import DownloadParams
from ....core.exceptions import FastAnimeError
from ....libs.media_api.types import MediaItem
from ....libs.provider.anime.base import BaseAnimeProvider
from ....libs.provider.anime.params import EpisodeStreamsParams
from ....libs.provider.anime.types import Server
from ..registry import MediaRegistryService
from ..registry.models import DownloadStatus, MediaEpisode

logger = logging.getLogger(__name__)


class DownloadService:
    """Service for downloading episodes and tracking them in the registry."""

    def __init__(
        self,
        config: AppConfig,
        media_registry: MediaRegistryService,
        provider: BaseAnimeProvider,
    ):
        self.config = config
        self.downloads_config = config.downloads
        self.media_registry = media_registry
        self.provider = provider
        self._downloader: Optional[BaseDownloader] = None

    @property
    def downloader(self) -> BaseDownloader:
        """Lazy initialization of downloader."""
        if self._downloader is None:
            self._downloader = create_downloader(self.downloads_config)
        return self._downloader

    def download_episode(
        self,
        media_item: MediaItem,
        episode_number: str,
        server: Optional[Server] = None,
        quality: Optional[str] = None,
        force_redownload: bool = False,
    ) -> bool:
        """
        Download a specific episode and record it in the registry.
        
        Args:
            media_item: The media item to download
            episode_number: The episode number to download
            server: Optional specific server to use for download
            quality: Optional quality preference
            force_redownload: Whether to redownload if already exists
            
        Returns:
            bool: True if download was successful, False otherwise
        """
        try:
            # Get or create media record
            media_record = self.media_registry.get_or_create_record(media_item)
            
            # Check if episode already exists and is completed
            existing_episode = self._find_episode_in_record(media_record, episode_number)
            if (
                existing_episode 
                and existing_episode.download_status == DownloadStatus.COMPLETED
                and not force_redownload
                and existing_episode.file_path.exists()
            ):
                logger.info(f"Episode {episode_number} already downloaded at {existing_episode.file_path}")
                return True

            # Generate file path
            file_path = self._generate_episode_file_path(media_item, episode_number)

            # Update status to QUEUED
            self.media_registry.update_episode_download_status(
                media_id=media_item.id,
                episode_number=episode_number,
                status=DownloadStatus.QUEUED,
                file_path=file_path,
            )

            # Get episode stream server if not provided
            if server is None:
                server = self._get_episode_server(media_item, episode_number, quality)
                if not server:
                    self.media_registry.update_episode_download_status(
                        media_id=media_item.id,
                        episode_number=episode_number,
                        status=DownloadStatus.FAILED,
                        error_message="Failed to get server for episode",
                    )
                    return False

            # Update status to DOWNLOADING
            self.media_registry.update_episode_download_status(
                media_id=media_item.id,
                episode_number=episode_number,
                status=DownloadStatus.DOWNLOADING,
                provider_name=self.provider.__class__.__name__,
                server_name=server.name,
                quality=quality or self.downloads_config.preferred_quality,
            )

            # Perform the download
            download_result = self._download_from_server(
                media_item, episode_number, server, file_path
            )

            if download_result.success and download_result.video_path:
                # Get file size if available
                file_size = None
                if download_result.video_path.exists():
                    file_size = download_result.video_path.stat().st_size

                # Update episode record with success
                self.media_registry.update_episode_download_status(
                    media_id=media_item.id,
                    episode_number=episode_number,
                    status=DownloadStatus.COMPLETED,
                    file_path=download_result.video_path,
                    file_size=file_size,
                    subtitle_paths=download_result.subtitle_paths,
                )
                
                logger.info(f"Successfully downloaded episode {episode_number} to {download_result.video_path}")
            else:
                # Update episode record with failure
                self.media_registry.update_episode_download_status(
                    media_id=media_item.id,
                    episode_number=episode_number,
                    status=DownloadStatus.FAILED,
                    error_message=download_result.error_message,
                )
                
                logger.error(f"Failed to download episode {episode_number}: {download_result.error_message}")

            return download_result.success

        except Exception as e:
            logger.error(f"Error downloading episode {episode_number}: {e}")
            # Update status to FAILED
            try:
                self.media_registry.update_episode_download_status(
                    media_id=media_item.id,
                    episode_number=episode_number,
                    status=DownloadStatus.FAILED,
                    error_message=str(e),
                )
            except Exception as cleanup_error:
                logger.error(f"Failed to update failed status: {cleanup_error}")
            
            return False

    def download_multiple_episodes(
        self,
        media_item: MediaItem,
        episode_numbers: list[str],
        quality: Optional[str] = None,
        force_redownload: bool = False,
    ) -> dict[str, bool]:
        """
        Download multiple episodes and return success status for each.
        
        Args:
            media_item: The media item to download
            episode_numbers: List of episode numbers to download
            quality: Optional quality preference
            force_redownload: Whether to redownload if already exists
            
        Returns:
            dict: Mapping of episode_number -> success status
        """
        results = {}
        
        for episode_number in episode_numbers:
            success = self.download_episode(
                media_item=media_item,
                episode_number=episode_number,
                quality=quality,
                force_redownload=force_redownload,
            )
            results[episode_number] = success
            
            # Log progress
            logger.info(f"Download progress: {episode_number} - {'✓' if success else '✗'}")
        
        return results

    def get_download_status(self, media_item: MediaItem, episode_number: str) -> Optional[DownloadStatus]:
        """Get the download status for a specific episode."""
        media_record = self.media_registry.get_media_record(media_item.id)
        if not media_record:
            return None
            
        episode_record = self._find_episode_in_record(media_record, episode_number)
        return episode_record.download_status if episode_record else None

    def get_downloaded_episodes(self, media_item: MediaItem) -> list[str]:
        """Get list of successfully downloaded episode numbers for a media item."""
        media_record = self.media_registry.get_media_record(media_item.id)
        if not media_record:
            return []
            
        return [
            episode.episode_number
            for episode in media_record.media_episodes
            if episode.download_status == DownloadStatus.COMPLETED
            and episode.file_path.exists()
        ]

    def remove_downloaded_episode(self, media_item: MediaItem, episode_number: str) -> bool:
        """Remove a downloaded episode file and update registry."""
        try:
            media_record = self.media_registry.get_media_record(media_item.id)
            if not media_record:
                return False
                
            episode_record = self._find_episode_in_record(media_record, episode_number)
            if not episode_record:
                return False
                
            # Remove file if it exists
            if episode_record.file_path.exists():
                episode_record.file_path.unlink()
                
            # Remove episode from record
            media_record.media_episodes = [
                ep for ep in media_record.media_episodes
                if ep.episode_number != episode_number
            ]
            
            # Save updated record
            self.media_registry.save_media_record(media_record)
            
            logger.info(f"Removed downloaded episode {episode_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing episode {episode_number}: {e}")
            return False

    def _find_episode_in_record(self, media_record, episode_number: str) -> Optional[MediaEpisode]:
        """Find an episode record by episode number."""
        for episode in media_record.media_episodes:
            if episode.episode_number == episode_number:
                return episode
        return None

    def _get_episode_server(
        self, media_item: MediaItem, episode_number: str, quality: Optional[str] = None
    ) -> Optional[Server]:
        """Get a server for downloading the episode."""
        try:
            # Use media title for provider search
            media_title = media_item.title.english or media_item.title.romaji
            if not media_title:
                logger.error("Media item has no searchable title")
                return None

            # Get episode streams from provider
            streams = self.provider.episode_streams(
                EpisodeStreamsParams(
                    anime_id=str(media_item.id),
                    query=media_title,
                    episode=episode_number,
                    translation_type=self.config.stream.translation_type,
                )
            )

            if not streams:
                logger.error(f"No streams found for episode {episode_number}")
                return None

            # Convert iterator to list and get first available server
            stream_list = list(streams)
            if not stream_list:
                logger.error(f"No servers available for episode {episode_number}")
                return None

            # Return the first server (could be enhanced with quality/preference logic)
            return stream_list[0]

        except Exception as e:
            logger.error(f"Error getting episode server: {e}")
            return None

    def _download_from_server(
        self,
        media_item: MediaItem,
        episode_number: str,
        server: Server,
        output_path: Path,
    ):
        """Download episode from a specific server."""
        anime_title = media_item.title.english or media_item.title.romaji or "Unknown"
        episode_title = server.episode_title or f"Episode {episode_number}"
        
        try:
            # Get the best quality link from server
            if not server.links:
                raise FastAnimeError("Server has no available links")

            # Use the first link (could be enhanced with quality filtering)
            stream_link = server.links[0]

            # Prepare download parameters
            download_params = DownloadParams(
                url=stream_link.link,
                anime_title=anime_title,
                episode_title=episode_title,
                silent=True,  # Use True by default since there's no verbose in config
                headers=server.headers,
                subtitles=[sub.url for sub in server.subtitles] if server.subtitles else [],
                vid_format=self.downloads_config.preferred_quality,
                force_unknown_ext=True,
            )

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Perform download
            return self.downloader.download(download_params)

        except Exception as e:
            logger.error(f"Error during download: {e}")
            from ....core.downloader.model import DownloadResult
            return DownloadResult(
                success=False,
                error_message=str(e),
                anime_title=anime_title,
                episode_title=episode_title,
            )

    def get_download_statistics(self) -> dict:
        """Get comprehensive download statistics from the registry."""
        return self.media_registry.get_download_statistics()

    def get_failed_downloads(self) -> list[tuple[int, str]]:
        """Get all episodes that failed to download."""
        return self.media_registry.get_episodes_by_download_status(DownloadStatus.FAILED)

    def get_queued_downloads(self) -> list[tuple[int, str]]:
        """Get all episodes queued for download."""
        return self.media_registry.get_episodes_by_download_status(DownloadStatus.QUEUED)

    def retry_failed_downloads(self, max_retries: int = 3) -> dict[str, bool]:
        """Retry all failed downloads up to max_retries."""
        failed_episodes = self.get_failed_downloads()
        results = {}
        
        for media_id, episode_number in failed_episodes:
            # Get the media record to check retry attempts
            media_record = self.media_registry.get_media_record(media_id)
            if not media_record:
                continue
                
            episode_record = self._find_episode_in_record(media_record, episode_number)
            if not episode_record or episode_record.download_attempts >= max_retries:
                logger.info(f"Skipping {media_id}:{episode_number} - max retries exceeded")
                continue
            
            logger.info(f"Retrying download for {media_id}:{episode_number}")
            success = self.download_episode(
                media_item=media_record.media_item,
                episode_number=episode_number,
                force_redownload=True,
            )
            results[f"{media_id}:{episode_number}"] = success
        
        return results

    def cleanup_failed_downloads(self, older_than_days: int = 7) -> int:
        """Clean up failed download records older than specified days."""
        from datetime import datetime, timedelta
        
        cleanup_count = 0
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        try:
            for record in self.media_registry.get_all_media_records():
                episodes_to_remove = []
                
                for episode in record.media_episodes:
                    if (
                        episode.download_status == DownloadStatus.FAILED
                        and episode.download_date < cutoff_date
                    ):
                        episodes_to_remove.append(episode.episode_number)
                
                for episode_number in episodes_to_remove:
                    record.media_episodes = [
                        ep for ep in record.media_episodes
                        if ep.episode_number != episode_number
                    ]
                    cleanup_count += 1
                
                if episodes_to_remove:
                    self.media_registry.save_media_record(record)
            
            logger.info(f"Cleaned up {cleanup_count} failed download records")
            return cleanup_count
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return 0

    def pause_download(self, media_item: MediaItem, episode_number: str) -> bool:
        """Pause a download (change status from DOWNLOADING to PAUSED)."""
        try:
            return self.media_registry.update_episode_download_status(
                media_id=media_item.id,
                episode_number=episode_number,
                status=DownloadStatus.PAUSED,
            )
        except Exception as e:
            logger.error(f"Error pausing download: {e}")
            return False

    def resume_download(self, media_item: MediaItem, episode_number: str) -> bool:
        """Resume a paused download."""
        return self.download_episode(
            media_item=media_item,
            episode_number=episode_number,
            force_redownload=True,
        )

    def get_media_download_progress(self, media_item: MediaItem) -> dict:
        """Get download progress for a specific media item."""
        try:
            media_record = self.media_registry.get_media_record(media_item.id)
            if not media_record:
                return {"total": 0, "downloaded": 0, "failed": 0, "queued": 0, "downloading": 0}
            
            stats = {"total": 0, "downloaded": 0, "failed": 0, "queued": 0, "downloading": 0, "paused": 0}
            
            for episode in media_record.media_episodes:
                stats["total"] += 1
                status = episode.download_status.value.lower()
                if status == "completed":
                    stats["downloaded"] += 1
                elif status == "failed":
                    stats["failed"] += 1
                elif status == "queued":
                    stats["queued"] += 1
                elif status == "downloading":
                    stats["downloading"] += 1
                elif status == "paused":
                    stats["paused"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting download progress: {e}")
            return {"total": 0, "downloaded": 0, "failed": 0, "queued": 0, "downloading": 0}

    def _generate_episode_file_path(self, media_item: MediaItem, episode_number: str) -> Path:
        """Generate the file path for a downloaded episode."""
        # Use the download directory from config
        base_dir = self.downloads_config.downloads_dir
        
        # Create anime-specific directory
        anime_title = media_item.title.english or media_item.title.romaji or "Unknown"
        # Sanitize title for filesystem
        safe_title = "".join(c for c in anime_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        
        anime_dir = base_dir / safe_title
        
        # Generate filename (could use template from config in the future)
        filename = f"Episode_{episode_number:0>2}.mp4"
        
        return anime_dir / filename
