import click
from fastanime.core.config import AppConfig


@click.command(name="resume", help="Submit any queued or in-progress downloads to the worker.")
@click.pass_obj
def resume(config: AppConfig):
    from fastanime.cli.service.download.service import DownloadService
    from fastanime.cli.service.feedback import FeedbackService
    from fastanime.cli.service.registry import MediaRegistryService
    from fastanime.libs.media_api.api import create_api_client
    from fastanime.libs.provider.anime.provider import create_provider

    feedback = FeedbackService(config)
    media_api = create_api_client(config.general.media_api, config)
    provider = create_provider(config.general.provider)
    registry = MediaRegistryService(config.general.media_api, config.media_registry)
    download_service = DownloadService(config, registry, media_api, provider)

    download_service.start()
    download_service.resume_unfinished_downloads()
    feedback.success("Submitted queued downloads to background worker.")
