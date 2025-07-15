"""
Background service for automated download queue processing and episode monitoring.
"""

import json
import logging
import signal
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Set, cast, Literal

import click
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig
    from fastanime.libs.api.base import BaseApiClient
    from fastanime.libs.api.types import MediaItem

from ..utils.download_queue import DownloadJob, DownloadStatus, QueueManager
from ..utils.feedback import create_feedback_manager

logger = logging.getLogger(__name__)


class DownloadService:
    """Background service for processing download queue and monitoring new episodes."""
    
    def __init__(self, config: "AppConfig"):
        self.config = config
        self.queue_manager = QueueManager()
        self.console = Console()
        self.feedback = create_feedback_manager(config.general.icons)
        self._running = False
        self._shutdown_event = threading.Event()
        
        # Service state
        self.last_watchlist_check = datetime.now() - timedelta(hours=1)  # Force initial check
        self.known_episodes: Dict[int, Set[str]] = {}  # media_id -> set of episode numbers
        self.last_notification_check = datetime.now() - timedelta(minutes=10)
        
        # Configuration
        self.watchlist_check_interval = self.config.service.watchlist_check_interval * 60  # Convert to seconds
        self.queue_process_interval = self.config.service.queue_process_interval * 60  # Convert to seconds  
        self.notification_check_interval = 2 * 60  # 2 minutes in seconds
        self.max_concurrent_downloads = self.config.service.max_concurrent_downloads
        
        # State file for persistence
        from fastanime.core.constants import APP_DATA_DIR
        self.state_file = APP_DATA_DIR / "service_state.json"
    
    def _load_state(self):
        """Load service state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.known_episodes = {
                        int(k): set(v) for k, v in data.get('known_episodes', {}).items()
                    }
                    self.last_watchlist_check = datetime.fromisoformat(
                        data.get('last_watchlist_check', datetime.now().isoformat())
                    )
                logger.info("Service state loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load service state: {e}")
    
    def _save_state(self):
        """Save service state to file."""
        try:
            data = {
                'known_episodes': {
                    str(k): list(v) for k, v in self.known_episodes.items()
                },
                'last_watchlist_check': self.last_watchlist_check.isoformat(),
                'last_saved': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save service state: {e}")
    
    def start(self):
        """Start the background service."""
        logger.info("Starting FastAnime download service...")
        self.console.print(f"{'🚀 ' if self.config.general.icons else ''}[bold green]Starting FastAnime Download Service[/bold green]")
        
        # Load previous state
        self._load_state()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._running = True
        
        # Start worker threads
        watchlist_thread = threading.Thread(target=self._watchlist_monitor, daemon=True)
        queue_thread = threading.Thread(target=self._queue_processor, daemon=True)
        
        watchlist_thread.start()
        queue_thread.start()
        
        self.console.print(f"{'✅ ' if self.config.general.icons else ''}Service started successfully")
        self.console.print(f"{'📊 ' if self.config.general.icons else ''}Monitoring watchlist every {self.watchlist_check_interval // 60} minutes")
        self.console.print(f"{'⚙️ ' if self.config.general.icons else ''}Processing queue every {self.queue_process_interval} seconds")
        self.console.print(f"{'🛑 ' if self.config.general.icons else ''}Press Ctrl+C to stop")
        
        try:
            # Main loop - just wait for shutdown
            while self._running and not self._shutdown_event.wait(timeout=10):
                self._save_state()  # Periodic state saving
                
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False
        self._shutdown_event.set()
    
    def _shutdown(self):
        """Gracefully shutdown the service."""
        logger.info("Shutting down download service...")
        self.console.print(f"{'🛑 ' if self.config.general.icons else ''}[yellow]Shutting down service...[/yellow]")
        
        self._running = False
        self._shutdown_event.set()
        
        # Save final state
        self._save_state()
        
        # Cancel any running downloads
        active_jobs = self.queue_manager.get_active_jobs()
        for job in active_jobs:
            self.queue_manager.update_job_status(job.id, DownloadStatus.CANCELLED)
        
        self.console.print(f"{'✅ ' if self.config.general.icons else ''}Service stopped")
        logger.info("Download service shutdown complete")
    
    def _watchlist_monitor(self):
        """Monitor user's AniList watching list for new episodes."""
        logger.info("Starting watchlist monitor thread")
        
        while self._running:
            try:
                if (datetime.now() - self.last_watchlist_check).total_seconds() >= self.watchlist_check_interval:
                    self._check_for_new_episodes()
                    self.last_watchlist_check = datetime.now()
                
                # Check for notifications (like the existing notifier)
                if (datetime.now() - self.last_notification_check).total_seconds() >= self.notification_check_interval:
                    self._check_notifications()
                    self.last_notification_check = datetime.now()
                
            except Exception as e:
                logger.error(f"Error in watchlist monitor: {e}")
            
            # Sleep with check for shutdown
            if self._shutdown_event.wait(timeout=60):
                break
        
        logger.info("Watchlist monitor thread stopped")
    
    def _queue_processor(self):
        """Process the download queue."""
        logger.info("Starting queue processor thread")
        
        while self._running:
            try:
                self._process_download_queue()
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
            
            # Sleep with check for shutdown
            if self._shutdown_event.wait(timeout=self.queue_process_interval):
                break
        
        logger.info("Queue processor thread stopped")
    
    def _check_for_new_episodes(self):
        """Check user's watching list for newly released episodes."""
        try:
            logger.info("Checking for new episodes in watchlist...")
            
            # Get authenticated API client
            from fastanime.libs.api.factory import create_api_client
            from fastanime.libs.api.params import UserListParams
            
            api_client = create_api_client(self.config.general.api_client, self.config)
            
            # Check if user is authenticated
            user_profile = api_client.get_viewer_profile()
            if not user_profile:
                logger.warning("User not authenticated, skipping watchlist check")
                return
            
            # Fetch currently watching anime
            with Progress() as progress:
                task = progress.add_task("Checking watchlist...", total=None)
                
                list_params = UserListParams(
                    status="CURRENT",  # Currently watching
                    page=1,
                    per_page=50
                )
                user_list = api_client.fetch_user_list(list_params)
                progress.update(task, completed=True)
            
            if not user_list or not user_list.media:
                logger.info("No anime found in watching list")
                return
            
            new_episodes_found = 0
            
            for media_item in user_list.media:
                try:
                    media_id = media_item.id
                    
                    # Get available episodes from provider
                    available_episodes = self._get_available_episodes(media_item)
                    if not available_episodes:
                        continue
                    
                    # Check if we have new episodes
                    known_eps = self.known_episodes.get(media_id, set())
                    new_episodes = set(available_episodes) - known_eps
                    
                    if new_episodes:
                        logger.info(f"Found {len(new_episodes)} new episodes for {media_item.title.romaji or media_item.title.english}")
                        
                        # Add new episodes to download queue
                        for episode in sorted(new_episodes, key=lambda x: float(x) if x.isdigit() else 0):
                            self._add_episode_to_queue(media_item, episode)
                            new_episodes_found += 1
                        
                        # Update known episodes
                        self.known_episodes[media_id] = set(available_episodes)
                    else:
                        # Update known episodes even if no new ones (in case some were removed)
                        self.known_episodes[media_id] = set(available_episodes)
                
                except Exception as e:
                    logger.error(f"Error checking episodes for {media_item.title.romaji}: {e}")
            
            if new_episodes_found > 0:
                logger.info(f"Added {new_episodes_found} new episodes to download queue")
                self.console.print(f"{'📺 ' if self.config.general.icons else ''}Found {new_episodes_found} new episodes, added to queue")
            else:
                logger.info("No new episodes found")
                
        except Exception as e:
            logger.error(f"Error checking for new episodes: {e}")
    
    def _get_available_episodes(self, media_item: "MediaItem") -> List[str]:
        """Get available episodes for a media item from the provider."""
        try:
            from fastanime.libs.providers.anime.provider import create_provider
            from fastanime.libs.providers.anime.params import AnimeParams, SearchParams
            from httpx import Client
            
            client = Client()
            provider = create_provider(self.config.general.provider)
            
            # Search for the anime
            search_results = provider.search(SearchParams(
                query=media_item.title.romaji or media_item.title.english or "Unknown",
                translation_type=self.config.stream.translation_type
            ))
            
            if not search_results or not search_results.results:
                return []
            
            # Get the first result (should be the best match)
            anime_result = search_results.results[0]
            
            # Get anime details
            anime = provider.get(AnimeParams(id=anime_result.id))
            if not anime or not anime.episodes:
                return []
            
            # Get episodes for the configured translation type
            episodes = getattr(anime.episodes, self.config.stream.translation_type, [])
            return sorted(episodes, key=lambda x: float(x) if x.replace('.', '').isdigit() else 0)
            
        except Exception as e:
            logger.error(f"Error getting available episodes: {e}")
            return []
    
    def _add_episode_to_queue(self, media_item: "MediaItem", episode: str):
        """Add an episode to the download queue."""
        try:
            job_id = str(uuid.uuid4())
            job = DownloadJob(
                id=job_id,
                anime_title=media_item.title.romaji or media_item.title.english or "Unknown",
                episode=episode,
                media_id=media_item.id,
                quality=self.config.stream.quality,
                translation_type=self.config.stream.translation_type,
                priority=1,  # High priority for auto-added episodes
                auto_added=True
            )
            
            success = self.queue_manager.add_job(job)
            if success:
                logger.info(f"Auto-queued: {job.anime_title} Episode {episode}")
            
        except Exception as e:
            logger.error(f"Error adding episode to queue: {e}")
    
    def _check_notifications(self):
        """Check for AniList notifications (similar to existing notifier)."""
        try:
            # This is similar to the existing notifier functionality
            # We can reuse the notification logic here if needed
            pass
        except Exception as e:
            logger.error(f"Error checking notifications: {e}")
    
    def _process_download_queue(self):
        """Process pending downloads in the queue."""
        try:
            # Get currently active downloads
            active_jobs = self.queue_manager.get_active_jobs()
            available_slots = max(0, self.max_concurrent_downloads - len(active_jobs))
            
            if available_slots == 0:
                return  # All slots busy
            
            # Get pending jobs
            pending_jobs = self.queue_manager.get_pending_jobs(limit=available_slots)
            if not pending_jobs:
                return  # No pending jobs
            
            logger.info(f"Processing {len(pending_jobs)} download jobs")
            
            # Process jobs concurrently
            with ThreadPoolExecutor(max_workers=available_slots) as executor:
                futures = {
                    executor.submit(self._download_episode, job): job 
                    for job in pending_jobs
                }
                
                for future in as_completed(futures):
                    job = futures[future]
                    try:
                        success = future.result()
                        if success:
                            logger.info(f"Successfully downloaded: {job.anime_title} Episode {job.episode}")
                        else:
                            logger.error(f"Failed to download: {job.anime_title} Episode {job.episode}")
                    except Exception as e:
                        logger.error(f"Error downloading {job.anime_title} Episode {job.episode}: {e}")
                        self.queue_manager.update_job_status(job.id, DownloadStatus.FAILED, str(e))
        
        except Exception as e:
            logger.error(f"Error processing download queue: {e}")
    
    def _download_episode(self, job: DownloadJob) -> bool:
        """Download a specific episode."""
        try:
            logger.info(f"Starting download: {job.anime_title} Episode {job.episode}")
            
            # Update job status to downloading
            self.queue_manager.update_job_status(job.id, DownloadStatus.DOWNLOADING)
            
            # Import download functionality
            from fastanime.libs.providers.anime.provider import create_provider
            from fastanime.libs.providers.anime.params import AnimeParams, SearchParams, EpisodeStreamsParams
            from fastanime.libs.selectors.selector import create_selector
            from fastanime.libs.players.player import create_player
            from fastanime.core.downloader.downloader import create_downloader
            from httpx import Client
            
            # Create required components
            client = Client()
            provider = create_provider(self.config.general.provider)
            selector = create_selector(self.config)
            player = create_player(self.config)
            downloader = create_downloader(self.config.downloads)
            
            # Search for anime
            translation_type = cast(Literal["sub", "dub"], job.translation_type if job.translation_type in ["sub", "dub"] else "sub")
            search_results = provider.search(SearchParams(
                query=job.anime_title,
                translation_type=translation_type
            ))
            
            if not search_results or not search_results.results:
                raise Exception("No search results found")
            
            # Get anime details
            anime_result = search_results.results[0]
            anime = provider.get(AnimeParams(id=anime_result.id))
            
            if not anime:
                raise Exception("Failed to get anime details")
            
            # Get episode streams
            # Ensure translation_type is valid Literal type
            valid_translation = cast(Literal["sub", "dub"], 
                                   job.translation_type if job.translation_type in ["sub", "dub"] else "sub")
            
            streams = provider.episode_streams(EpisodeStreamsParams(
                anime_id=anime.id,
                episode=job.episode,
                translation_type=valid_translation
            ))
            
            if not streams:
                raise Exception("No streams found")
            
            # Get the first available server
            server = next(streams, None)
            if not server:
                raise Exception("No server available")
            
            # Download using the first available link
            if server.links:
                link = server.links[0]
                logger.info(f"Starting download: {link.link} for {job.anime_title} Episode {job.episode}")
                
                # Import downloader
                from fastanime.core.downloader import create_downloader, DownloadParams
                
                # Create downloader with config
                downloader = create_downloader(self.config.downloads)
                
                # Prepare download parameters
                download_params = DownloadParams(
                    url=link.link,
                    anime_title=job.anime_title,
                    episode_title=f"Episode {job.episode}",
                    silent=True,  # Run silently in background
                    headers=server.headers,  # Use server headers
                    subtitles=[sub.url for sub in server.subtitles],  # Extract subtitle URLs
                    merge=False,  # Default to false
                    clean=False,  # Default to false
                    prompt=False,  # No prompts in background service
                    force_ffmpeg=False,  # Default to false
                    hls_use_mpegts=False,  # Default to false
                    hls_use_h264=False  # Default to false
                )
                
                # Download the episode
                try:
                    downloader.download(download_params)
                    logger.info(f"Successfully downloaded: {job.anime_title} Episode {job.episode}")
                    self.queue_manager.update_job_status(job.id, DownloadStatus.COMPLETED)
                    return True
                except Exception as download_error:
                    error_msg = f"Download failed: {str(download_error)}"
                    raise Exception(error_msg)
            else:
                raise Exception("No download links available")
            
        except Exception as e:
            logger.error(f"Download failed for {job.anime_title} Episode {job.episode}: {e}")
            
            # Handle retry logic
            job.retry_count += 1
            if job.retry_count < self.queue_manager.queue.auto_retry_count:
                # Reset to pending for retry
                self.queue_manager.update_job_status(job.id, DownloadStatus.PENDING, f"Retry {job.retry_count}: {str(e)}")
            else:
                # Mark as failed after max retries
                self.queue_manager.update_job_status(job.id, DownloadStatus.FAILED, f"Max retries exceeded: {str(e)}")
            
            return False


@click.command(
    help="Run background service for automated downloads and episode monitoring",
    short_help="Background download service",
    epilog="""
\b
\b\bExamples:
    # Start the service
    fastanime service

    # Run in the background (Linux/macOS)
    nohup fastanime service > /dev/null 2>&1 &

    # Run with logging
    fastanime --log service

    # Run with file logging
    fastanime --log-to-file service
""",
)
@click.option(
    "--watchlist-interval",
    type=int,
    help="Minutes between watchlist checks (default from config)"
)
@click.option(
    "--queue-interval", 
    type=int,
    help="Minutes between queue processing (default from config)"
)
@click.option(
    "--max-concurrent",
    type=int,
    help="Maximum concurrent downloads (default from config)"
)
@click.pass_obj
def service(config: "AppConfig", watchlist_interval: Optional[int], queue_interval: Optional[int], max_concurrent: Optional[int]):
    """
    Run the FastAnime background service for automated downloads.
    
    The service will:
    - Monitor your AniList watching list for new episodes
    - Automatically queue new episodes for download
    - Process the download queue
    - Provide notifications for new episodes
    """
    
    try:
        # Update configuration with command line options if provided
        service_instance = DownloadService(config)
        if watchlist_interval is not None:
            service_instance.watchlist_check_interval = watchlist_interval * 60
        if queue_interval is not None:
            service_instance.queue_process_interval = queue_interval * 60
        if max_concurrent is not None:
            service_instance.max_concurrent_downloads = max_concurrent
        
        # Start the service
        service_instance.start()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console = Console()
        console.print(f"[red]Service error: {e}[/red]")
        logger.error(f"Service error: {e}")
        sys.exit(1)
