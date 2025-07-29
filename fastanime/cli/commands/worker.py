import click
from fastanime.core.config import AppConfig


@click.command(help="Run the background worker for notifications and downloads.")
@click.pass_obj
def worker(config: AppConfig):
    """
    Starts the long-running background worker process.
    This process will periodically check for AniList notifications and
    process any queued downloads. It's recommended to run this in the
    background (e.g., 'fastanime worker &') or as a system service.
    """
    from fastanime.cli.service.download.service import DownloadService
    from fastanime.cli.service.feedback import FeedbackService
    from fastanime.cli.service.notification.service import NotificationService
    from fastanime.cli.service.registry.service import MediaRegistryService
    from fastanime.cli.service.worker.service import BackgroundWorkerService
    from fastanime.libs.media_api.api import create_api_client
    from fastanime.libs.provider.anime.provider import create_provider

    feedback = FeedbackService(config)
    if not config.worker.enabled:
        feedback.warning("Worker is disabled in the configuration. Exiting.")
        return

    # Instantiate services
    media_api = create_api_client(config.general.media_api, config)
    provider = create_provider(config.general.provider)
    registry = MediaRegistryService(config.general.media_api, config.media_registry)

    notification_service = NotificationService(media_api)
    download_service = DownloadService(config, registry, media_api, provider)
    worker_service = BackgroundWorkerService(
        config.worker, notification_service, download_service
    )

    feedback.info("Starting background worker...", "Press Ctrl+C to stop.")
    worker_service.run()
