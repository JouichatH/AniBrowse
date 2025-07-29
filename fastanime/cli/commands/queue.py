import click
from fastanime.core.config import AppConfig
from fastanime.core.exceptions import FastAnimeError
from fastanime.libs.media_api.params import MediaSearchParams


@click.command(help="Queue episodes for the background worker to download.")
@click.option(
    "--title", "-t", required=True, multiple=True, help="Anime title to queue."
)
@click.option(
    "--episode-range", "-r", required=True, help="Range of episodes (e.g., '1-10')."
)
@click.pass_obj
def queue(config: AppConfig, title: tuple, episode_range: str):
    """
    Searches for an anime and adds the specified episodes to the download queue.
    The background worker must be running for the downloads to start.
    """
    from fastanime.cli.service.download.service import DownloadService
    from fastanime.cli.service.feedback import FeedbackService
    from fastanime.cli.service.registry import MediaRegistryService
    from fastanime.cli.utils.parser import parse_episode_range
    from fastanime.libs.media_api.api import create_api_client
    from fastanime.libs.provider.anime.provider import create_provider

    feedback = FeedbackService(config)
    media_api = create_api_client(config.general.media_api, config)
    provider = create_provider(config.general.provider)
    registry = MediaRegistryService(config.general.media_api, config.media_registry)
    download_service = DownloadService(config, registry, media_api, provider)

    for anime_title in title:
        try:
            feedback.info(f"Searching for '{anime_title}'...")
            search_result = media_api.search_media(
                MediaSearchParams(query=anime_title, per_page=1)
            )

            if not search_result or not search_result.media:
                feedback.warning(f"Could not find '{anime_title}' on AniList.")
                continue

            media_item = search_result.media[0]
            available_episodes = [str(i + 1) for i in range(media_item.episodes or 0)]
            episodes_to_queue = list(
                parse_episode_range(episode_range, available_episodes)
            )

            queued_count = 0
            for ep in episodes_to_queue:
                if download_service.add_to_queue(media_item, ep):
                    queued_count += 1

            feedback.success(
                f"Successfully queued {queued_count} episodes for '{media_item.title.english}'."
            )

        except FastAnimeError as e:
            feedback.error(f"Failed to queue '{anime_title}'", str(e))
        except Exception as e:
            feedback.error("An unexpected error occurred", str(e))
