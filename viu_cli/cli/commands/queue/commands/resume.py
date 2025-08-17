import click
from viu_media.core.config import AppConfig


@click.command(
    name="resume", help="Submit any queued or in-progress downloads to the worker."
)
@click.pass_obj
def resume(config: AppConfig):
    from viu_media.cli.service.download.service import DownloadService
    from viu_media.cli.service.feedback import FeedbackService
    from viu_media.cli.service.registry import MediaRegistryService
    from viu_media.libs.media_api.api import create_api_client
    from viu_media.libs.provider.anime.provider import create_provider

    feedback = FeedbackService(config)
    media_api = create_api_client(config.general.media_api, config)
    provider = create_provider(config.general.provider)
    registry = MediaRegistryService(config.general.media_api, config.media_registry)
    download_service = DownloadService(config, registry, media_api, provider)

    download_service.start()
    download_service.resume_unfinished_downloads()
    feedback.success("Submitted queued downloads to background worker.")
