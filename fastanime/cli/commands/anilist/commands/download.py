"""AniList download command using the modern download service."""

from typing import TYPE_CHECKING

import click

from .....core.config import AppConfig
from .....core.exceptions import FastAnimeError
from .....libs.media_api.api import create_api_client
from .....libs.media_api.params import MediaSearchParams
from .....libs.media_api.types import (
    MediaFormat,
    MediaGenre,
    MediaSeason,
    MediaSort,
    MediaStatus,
    MediaTag,
    MediaType,
    MediaYear,
)
from .....libs.provider.anime.provider import create_provider
from .....libs.provider.anime.params import SearchParams, AnimeParams
from .....libs.selectors import create_selector
from ....service.download import DownloadService
from ....service.feedback import FeedbackService
from ....service.registry import MediaRegistryService
from ....utils.completion import anime_titles_shell_complete
from ....utils import parse_episode_range
from .. import examples

if TYPE_CHECKING:
    from typing import TypedDict
    from typing_extensions import Unpack

    class DownloadOptions(TypedDict, total=False):
        title: str | None
        episode_range: str | None
        quality: str | None
        force_redownload: bool
        page: int
        per_page: int | None
        season: str | None
        status: tuple[str, ...]
        status_not: tuple[str, ...]
        sort: str | None
        genres: tuple[str, ...]
        genres_not: tuple[str, ...]
        tags: tuple[str, ...]
        tags_not: tuple[str, ...]
        media_format: tuple[str, ...]
        media_type: str | None
        year: str | None
        popularity_greater: int | None
        popularity_lesser: int | None
        score_greater: int | None
        score_lesser: int | None
        start_date_greater: int | None
        start_date_lesser: int | None
        end_date_greater: int | None
        end_date_lesser: int | None
        on_list: bool | None
        max_concurrent: int | None


@click.command(
    help="Download anime episodes using AniList API for search and provider integration",
    short_help="Download anime episodes",
    epilog=examples.download,
)
@click.option(
    "--title",
    "-t",
    shell_complete=anime_titles_shell_complete,
    help="Title of the anime to search for",
)
@click.option(
    "--episode-range",
    "-r",
    help="Range of episodes to download (e.g., '1:5', '3:', ':5', '1:10:2')",
)
@click.option(
    "--quality",
    "-q",
    type=click.Choice(["360", "480", "720", "1080", "best"]),
    help="Preferred download quality",
)
@click.option(
    "--force-redownload",
    "-f",
    is_flag=True,
    help="Force redownload even if episode already exists",
)
@click.option(
    "--page",
    "-p",
    type=click.IntRange(min=1),
    default=1,
    help="Page number for search pagination",
)
@click.option(
    "--per-page",
    type=click.IntRange(min=1, max=50),
    help="Number of results per page (max 50)",
)
@click.option(
    "--season",
    help="The season the media was released",
    type=click.Choice([season.value for season in MediaSeason]),
)
@click.option(
    "--status",
    "-S",
    help="The media status of the anime",
    multiple=True,
    type=click.Choice([status.value for status in MediaStatus]),
)
@click.option(
    "--status-not",
    help="Exclude media with these statuses",
    multiple=True,
    type=click.Choice([status.value for status in MediaStatus]),
)
@click.option(
    "--sort",
    "-s",
    help="What to sort the search results on",
    type=click.Choice([sort.value for sort in MediaSort]),
)
@click.option(
    "--genres",
    "-g",
    multiple=True,
    help="the genres to filter by",
    type=click.Choice([genre.value for genre in MediaGenre]),
)
@click.option(
    "--genres-not",
    multiple=True,
    help="Exclude these genres",
    type=click.Choice([genre.value for genre in MediaGenre]),
)
@click.option(
    "--tags",
    "-T",
    multiple=True,
    help="the tags to filter by",
    type=click.Choice([tag.value for tag in MediaTag]),
)
@click.option(
    "--tags-not",
    multiple=True,
    help="Exclude these tags",
    type=click.Choice([tag.value for tag in MediaTag]),
)
@click.option(
    "--media-format",
    "-F",
    multiple=True,
    help="Media format",
    type=click.Choice([format.value for format in MediaFormat]),
)
@click.option(
    "--media-type",
    help="Media type (ANIME or MANGA)",
    type=click.Choice([media_type.value for media_type in MediaType]),
)
@click.option(
    "--year",
    "-y",
    type=click.Choice([year.value for year in MediaYear]),
    help="the year the media was released",
)
@click.option(
    "--popularity-greater",
    type=click.IntRange(min=0),
    help="Minimum popularity score",
)
@click.option(
    "--popularity-lesser",
    type=click.IntRange(min=0),
    help="Maximum popularity score",
)
@click.option(
    "--score-greater",
    type=click.IntRange(min=0, max=100),
    help="Minimum average score (0-100)",
)
@click.option(
    "--score-lesser",
    type=click.IntRange(min=0, max=100),
    help="Maximum average score (0-100)",
)
@click.option(
    "--start-date-greater",
    type=click.IntRange(min=10000101, max=99991231),
    help="Minimum start date (YYYYMMDD format, e.g., 20240101)",
)
@click.option(
    "--start-date-lesser",
    type=click.IntRange(min=10000101, max=99991231),
    help="Maximum start date (YYYYMMDD format, e.g., 20241231)",
)
@click.option(
    "--end-date-greater",
    type=click.IntRange(min=10000101, max=99991231),
    help="Minimum end date (YYYYMMDD format, e.g., 20240101)",
)
@click.option(
    "--end-date-lesser",
    type=click.IntRange(min=10000101, max=99991231),
    help="Maximum end date (YYYYMMDD format, e.g., 20241231)",
)
@click.option(
    "--on-list/--not-on-list",
    "-L/-no-L",
    help="Whether the anime should be in your list or not",
    type=bool,
)
@click.option(
    "--max-concurrent",
    "-c",
    type=click.IntRange(min=1, max=10),
    help="Maximum number of concurrent downloads",
)
@click.pass_obj
def download(config: AppConfig, **options: "Unpack[DownloadOptions]"):
    """Download anime episodes using AniList search and provider integration."""
    feedback = FeedbackService(config.general.icons)

    try:
        # Extract and validate options
        title = options.get("title")
        episode_range = options.get("episode_range")
        quality = options.get("quality")
        force_redownload = options.get("force_redownload", False)
        max_concurrent = options.get("max_concurrent", config.downloads.max_concurrent)

        _validate_options(options)

        # Initialize services
        feedback.info("Initializing services...")
        api_client, provider, selector, media_registry, download_service = (
            _initialize_services(config)
        )
        feedback.info(f"Using provider: {provider.__class__.__name__}")
        feedback.info(f"Using media API: {config.general.media_api}")
        feedback.info(f"Translation type: {config.stream.translation_type}")

        # Search for anime
        search_params = _build_search_params(options, config)
        search_result = _search_anime(api_client, search_params, feedback)

        # Let user select anime (single or multiple)
        selected_anime_list = _select_anime(search_result, selector, feedback)
        if not selected_anime_list:
            feedback.info("No anime selected. Exiting.")
            return

        # Process each selected anime
        for selected_anime in selected_anime_list:
            feedback.info(
                f"Processing: {selected_anime.title.english or selected_anime.title.romaji}"
            )
            feedback.info(f"AniList ID: {selected_anime.id}")

            # Get available episodes from provider
            episodes_result = _get_available_episodes(
                provider, selected_anime, config, feedback
            )
            if not episodes_result:
                feedback.warning(
                    f"No episodes found for {selected_anime.title.english or selected_anime.title.romaji}"
                )
                _suggest_alternatives(selected_anime, provider, config, feedback)
                continue

            # Unpack the result
            if len(episodes_result) == 2:
                available_episodes, provider_anime_data = episodes_result
            else:
                # Fallback for backwards compatibility
                available_episodes = episodes_result
                provider_anime_data = None

            # Determine episodes to download
            episodes_to_download = _determine_episodes_to_download(
                episode_range, available_episodes, selector, feedback
            )
            if not episodes_to_download:
                feedback.warning("No episodes selected for download")
                continue

            feedback.info(
                f"About to download {len(episodes_to_download)} episodes: {', '.join(episodes_to_download)}"
            )

            # Test stream availability before attempting download (using provider anime data)
            if episodes_to_download and provider_anime_data:
                test_episode = episodes_to_download[0]
                feedback.info(
                    f"Testing stream availability for episode {test_episode}..."
                )
                success = _test_episode_stream_availability(
                    provider, provider_anime_data, test_episode, config, feedback
                )
                if not success:
                    feedback.warning(f"Stream test failed for episode {test_episode}.")
                    feedback.info("Possible solutions:")
                    feedback.info("1. Try a different provider (check your config)")
                    feedback.info("2. Check if the episode number is correct")
                    feedback.info("3. Try a different translation type (sub/dub)")
                    feedback.info(
                        "4. The anime might not be available on this provider"
                    )

                    # Ask user if they want to continue anyway
                    continue_anyway = (
                        input("\nContinue with download anyway? (y/N): ")
                        .strip()
                        .lower()
                    )
                    if continue_anyway not in ["y", "yes"]:
                        feedback.info("Download cancelled by user")
                        continue

            # Download episodes (using provider anime data if available, otherwise AniList data)
            anime_for_download = (
                provider_anime_data if provider_anime_data else selected_anime
            )
            _download_episodes(
                download_service,
                anime_for_download,
                episodes_to_download,
                quality,
                force_redownload,
                max_concurrent,
                feedback,
            )

        # Show final statistics
        _show_final_statistics(download_service, feedback)

    except FastAnimeError as e:
        feedback.error("Download failed", str(e))
        raise click.Abort()
    except Exception as e:
        feedback.error("Unexpected error occurred", str(e))
        raise click.Abort()


def _validate_options(options: "DownloadOptions") -> None:
    """Validate command line options."""
    score_greater = options.get("score_greater")
    score_lesser = options.get("score_lesser")
    popularity_greater = options.get("popularity_greater")
    popularity_lesser = options.get("popularity_lesser")
    start_date_greater = options.get("start_date_greater")
    start_date_lesser = options.get("start_date_lesser")
    end_date_greater = options.get("end_date_greater")
    end_date_lesser = options.get("end_date_lesser")

    # Score validation
    if (
        score_greater is not None
        and score_lesser is not None
        and score_greater > score_lesser
    ):
        raise FastAnimeError("Minimum score cannot be higher than maximum score")

    # Popularity validation
    if (
        popularity_greater is not None
        and popularity_lesser is not None
        and popularity_greater > popularity_lesser
    ):
        raise FastAnimeError(
            "Minimum popularity cannot be higher than maximum popularity"
        )

    # Date validation
    if (
        start_date_greater is not None
        and start_date_lesser is not None
        and start_date_greater > start_date_lesser
    ):
        raise FastAnimeError("Minimum start date cannot be after maximum start date")

    if (
        end_date_greater is not None
        and end_date_lesser is not None
        and end_date_greater > end_date_lesser
    ):
        raise FastAnimeError("Minimum end date cannot be after maximum end date")


def _initialize_services(config: AppConfig) -> tuple:
    """Initialize all required services."""
    api_client = create_api_client(config.general.media_api, config)
    provider = create_provider(config.general.provider)
    selector = create_selector(config)
    media_registry = MediaRegistryService(
        config.general.media_api, config.media_registry
    )
    download_service = DownloadService(config, media_registry, provider)

    return api_client, provider, selector, media_registry, download_service


def _build_search_params(
    options: "DownloadOptions", config: AppConfig
) -> MediaSearchParams:
    """Build MediaSearchParams from command options."""
    return MediaSearchParams(
        query=options.get("title"),
        page=options.get("page", 1),
        per_page=options.get("per_page") or config.anilist.per_page or 50,
        sort=MediaSort(options.get("sort")) if options.get("sort") else None,
        status_in=[MediaStatus(s) for s in options.get("status", ())]
        if options.get("status")
        else None,
        status_not_in=[MediaStatus(s) for s in options.get("status_not", ())]
        if options.get("status_not")
        else None,
        genre_in=[MediaGenre(g) for g in options.get("genres", ())]
        if options.get("genres")
        else None,
        genre_not_in=[MediaGenre(g) for g in options.get("genres_not", ())]
        if options.get("genres_not")
        else None,
        tag_in=[MediaTag(t) for t in options.get("tags", ())]
        if options.get("tags")
        else None,
        tag_not_in=[MediaTag(t) for t in options.get("tags_not", ())]
        if options.get("tags_not")
        else None,
        format_in=[MediaFormat(f) for f in options.get("media_format", ())]
        if options.get("media_format")
        else None,
        type=MediaType(options.get("media_type"))
        if options.get("media_type")
        else None,
        season=MediaSeason(options.get("season")) if options.get("season") else None,
        seasonYear=int(year) if (year := options.get("year")) else None,
        popularity_greater=options.get("popularity_greater"),
        popularity_lesser=options.get("popularity_lesser"),
        averageScore_greater=options.get("score_greater"),
        averageScore_lesser=options.get("score_lesser"),
        startDate_greater=options.get("start_date_greater"),
        startDate_lesser=options.get("start_date_lesser"),
        endDate_greater=options.get("end_date_greater"),
        endDate_lesser=options.get("end_date_lesser"),
        on_list=options.get("on_list"),
    )


def _search_anime(api_client, search_params, feedback):
    """Search for anime using the API client."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    # Check if we have any search criteria at all
    has_criteria = any(
        [
            search_params.query,
            search_params.genre_in,
            search_params.tag_in,
            search_params.status_in,
            search_params.season,
            search_params.seasonYear,
            search_params.format_in,
            search_params.popularity_greater,
            search_params.averageScore_greater,
        ]
    )

    if not has_criteria:
        raise FastAnimeError(
            "Please provide at least one search criterion (title, genre, tag, status, etc.)"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task("Searching for anime...", total=None)
        search_result = api_client.search_media(search_params)

    if not search_result or not search_result.media:
        raise FastAnimeError("No anime found matching your search criteria")

    return search_result


def _select_anime(search_result, selector, feedback):
    """Let user select anime from search results."""
    if len(search_result.media) == 1:
        selected_anime = search_result.media[0]
        feedback.info(
            f"Auto-selected: {selected_anime.title.english or selected_anime.title.romaji}"
        )
        return [selected_anime]

    # Create choice strings with additional info
    choices = []
    for i, anime in enumerate(search_result.media, 1):
        title = anime.title.english or anime.title.romaji or "Unknown"
        year = str(anime.start_date.year) if anime.start_date else "N/A"
        score = f"{anime.average_score}%" if anime.average_score else "N/A"
        status = anime.status.value if anime.status else "N/A"
        choices.append(f"{i:2d}. {title} ({year}) [Score: {score}, Status: {status}]")

    # Use multi-selection
    selected_choices = selector.choose_multiple(
        prompt="Select anime to download",
        choices=choices,
        header="Use TAB to select multiple anime, ENTER to confirm",
    )

    if not selected_choices:
        return []

    # Extract anime objects from selections
    selected_anime_list = []
    for choice in selected_choices:
        # Extract index from choice string (format: "XX. Title...")
        try:
            index = int(choice.split(".")[0].strip()) - 1
            selected_anime_list.append(search_result.media[index])
        except (ValueError, IndexError):
            feedback.error(f"Invalid selection: {choice}")
            continue

    return selected_anime_list


def _get_available_episodes(provider, anime, config, feedback):
    """Get available episodes from provider."""
    try:
        # Search for anime in provider first
        media_title = anime.title.english or anime.title.romaji
        feedback.info(
            f"Searching provider '{provider.__class__.__name__}' for: '{media_title}'"
        )
        feedback.info(f"Using translation type: '{config.stream.translation_type}'")

        provider_search_results = provider.search(
            SearchParams(
                query=media_title, translation_type=config.stream.translation_type
            )
        )

        if not provider_search_results or not provider_search_results.results:
            feedback.warning(
                f"Could not find '{media_title}' on provider '{provider.__class__.__name__}'"
            )
            return []

        feedback.info(
            f"Found {len(provider_search_results.results)} results on provider"
        )

        # Show the first few results for debugging
        for i, result in enumerate(provider_search_results.results[:3]):
            feedback.info(
                f"Result {i + 1}: ID={result.id}, Title='{getattr(result, 'title', 'Unknown')}'"
            )

        # Get the first result (could be enhanced with fuzzy matching)
        first_result = provider_search_results.results[0]
        feedback.info(f"Using first result: ID={first_result.id}")

        # Now get the full anime data using the PROVIDER'S ID, not AniList ID
        provider_anime_data = provider.get(
            AnimeParams(id=first_result.id, query=media_title)
        )

        if not provider_anime_data:
            feedback.warning("Failed to get anime details from provider")
            return []

        # Check all available translation types
        translation_types = ["sub", "dub"]
        for trans_type in translation_types:
            episodes = getattr(provider_anime_data.episodes, trans_type, [])
            feedback.info(
                f"Translation '{trans_type}': {len(episodes)} episodes available"
            )

        available_episodes = getattr(
            provider_anime_data.episodes, config.stream.translation_type, []
        )

        if not available_episodes:
            feedback.warning(f"No '{config.stream.translation_type}' episodes found")
            # Suggest alternative translation type if available
            for trans_type in translation_types:
                if trans_type != config.stream.translation_type:
                    other_episodes = getattr(
                        provider_anime_data.episodes, trans_type, []
                    )
                    if other_episodes:
                        feedback.info(
                            f"Suggestion: Try using translation type '{trans_type}' (has {len(other_episodes)} episodes)"
                        )
            return []

        feedback.info(
            f"Found {len(available_episodes)} episodes available for download"
        )

        # Return both episodes and the provider anime data for later use
        return available_episodes, provider_anime_data

    except Exception as e:
        feedback.error(f"Error getting episodes from provider: {e}")
        import traceback

        feedback.error("Full traceback", traceback.format_exc())
        return []


def _determine_episodes_to_download(
    episode_range, available_episodes, selector, feedback
):
    """Determine which episodes to download based on range or user selection."""
    if not available_episodes:
        feedback.warning("No episodes available to download")
        return []

    if episode_range:
        try:
            episodes_to_download = list(
                parse_episode_range(episode_range, available_episodes)
            )
            feedback.info(
                f"Episodes from range '{episode_range}': {', '.join(episodes_to_download)}"
            )
            return episodes_to_download
        except (ValueError, IndexError) as e:
            feedback.error(f"Invalid episode range '{episode_range}': {e}")
            return []
    else:
        # Let user select episodes
        selected_episodes = selector.choose_multiple(
            prompt="Select episodes to download",
            choices=available_episodes,
            header="Use TAB to select multiple episodes, ENTER to confirm",
        )

        if selected_episodes:
            feedback.info(f"Selected episodes: {', '.join(selected_episodes)}")

        return selected_episodes


def _suggest_alternatives(anime, provider, config, feedback):
    """Suggest alternatives when episodes are not found."""
    feedback.info("Troubleshooting suggestions:")
    feedback.info(f"1. Current provider: {provider.__class__.__name__}")
    feedback.info(f"2. AniList ID being used: {anime.id}")
    feedback.info(f"3. Translation type: {config.stream.translation_type}")

    # Special message for AllAnime provider
    if provider.__class__.__name__ == "AllAnimeProvider":
        feedback.info(
            "4. AllAnime ID mismatch: AllAnime uses different IDs than AniList"
        )
        feedback.info("   The provider searches by title, but episodes use AniList ID")
        feedback.info(
            "   This can cause episodes to not be found even if the anime exists"
        )

    # Check if provider has different ID mapping
    anime_titles = []
    if anime.title.english:
        anime_titles.append(anime.title.english)
    if anime.title.romaji:
        anime_titles.append(anime.title.romaji)
    if anime.title.native:
        anime_titles.append(anime.title.native)

    feedback.info(f"5. Available titles: {', '.join(anime_titles)}")
    feedback.info("6. Possible solutions:")
    feedback.info("   - Try a different provider (GogoAnime, 9anime, etc.)")
    feedback.info("   - Check provider configuration")
    feedback.info("   - Try different translation type (sub/dub)")
    feedback.info("   - Manual search on the provider website")
    feedback.info("   - Check if anime is available in your region")


def _download_episodes(
    download_service,
    anime,
    episodes,
    quality,
    force_redownload,
    max_concurrent,
    feedback,
):
    """Download the specified episodes."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from rich.console import Console
    from rich.progress import (
        BarColumn,
        MofNCompleteColumn,
        Progress,
        SpinnerColumn,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
    )
    import logging

    console = Console()
    anime_title = anime.title.english or anime.title.romaji

    console.print(f"\n[bold green]Starting downloads for: {anime_title}[/bold green]")

    # Set up logging capture to get download errors
    log_messages = []

    class ListHandler(logging.Handler):
        def emit(self, record):
            log_messages.append(self.format(record))

    handler = ListHandler()
    handler.setLevel(logging.ERROR)
    logger = logging.getLogger("fastanime")
    logger.addHandler(handler)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("Downloading episodes...", total=len(episodes))

            if max_concurrent == 1:
                # Sequential downloads
                results = {}
                for episode in episodes:
                    progress.update(
                        task, description=f"Downloading episode {episode}..."
                    )

                    # Clear previous log messages for this episode
                    log_messages.clear()

                    try:
                        success = download_service.download_episode(
                            media_item=anime,
                            episode_number=episode,
                            quality=quality,
                            force_redownload=force_redownload,
                        )
                        results[episode] = success

                        if not success:
                            # Try to get more detailed error from registry
                            error_msg = _get_episode_error_details(
                                download_service, anime, episode
                            )
                            if error_msg:
                                feedback.error(f"Episode {episode}", error_msg)
                            elif log_messages:
                                # Show any log messages that were captured
                                for msg in log_messages[
                                    -3:
                                ]:  # Show last 3 error messages
                                    feedback.error(f"Episode {episode}", msg)
                            else:
                                feedback.error(
                                    f"Episode {episode}",
                                    "Download failed - check logs for details",
                                )

                    except Exception as e:
                        results[episode] = False
                        feedback.error(f"Episode {episode} failed", str(e))
                    progress.advance(task)
            else:
                # Concurrent downloads
                results = {}
                with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                    # Submit all download tasks
                    future_to_episode = {
                        executor.submit(
                            download_service.download_episode,
                            media_item=anime,
                            episode_number=episode,
                            server=None,
                            quality=quality,
                            force_redownload=force_redownload,
                        ): episode
                        for episode in episodes
                    }

                    # Process completed downloads
                    for future in as_completed(future_to_episode):
                        episode = future_to_episode[future]
                        try:
                            success = future.result()
                            results[episode] = success
                            if not success:
                                # Try to get more detailed error from registry
                                error_msg = _get_episode_error_details(
                                    download_service, anime, episode
                                )
                                if error_msg:
                                    feedback.error(f"Episode {episode}", error_msg)
                                else:
                                    feedback.error(
                                        f"Episode {episode}",
                                        "Download failed - check logs for details",
                                    )
                        except Exception as e:
                            results[episode] = False
                            feedback.error(
                                f"Download failed for episode {episode}", str(e)
                            )

                        progress.advance(task)
    finally:
        # Remove the log handler
        logger.removeHandler(handler)

    # Display results
    _display_download_results(console, results, anime)


def _get_episode_error_details(download_service, anime, episode_number):
    """Get detailed error information from the registry for a failed episode."""
    try:
        # Get the media record from registry
        media_record = download_service.media_registry.get_record(anime.id)
        if not media_record:
            return None

        # Find the episode in the record
        for episode_record in media_record.episodes:
            if episode_record.episode_number == episode_number:
                if episode_record.error_message:
                    error_msg = episode_record.error_message

                    # Provide more helpful error messages for common issues
                    if "Failed to get server for episode" in error_msg:
                        return f"Episode {episode_number} not available on current provider. Try a different provider or check episode number."
                    elif "NoneType" in error_msg or "not subscriptable" in error_msg:
                        return f"Episode {episode_number} data not found on provider (API returned null). Episode may not exist or be accessible."
                    else:
                        return error_msg
                elif episode_record.download_status:
                    return f"Download status: {episode_record.download_status.value}"
                break

        return None
    except Exception:
        return None


def _test_episode_stream_availability(
    provider, anime, episode_number, config, feedback
):
    """Test if streams are available for a specific episode."""
    try:
        from .....libs.provider.anime.params import EpisodeStreamsParams

        media_title = anime.title.english or anime.title.romaji
        feedback.info(
            f"Testing stream availability for '{media_title}' episode {episode_number}"
        )

        # Test episode streams
        streams = provider.episode_streams(
            EpisodeStreamsParams(
                anime_id=str(anime.id),
                query=media_title,
                episode=episode_number,
                translation_type=config.stream.translation_type,
            )
        )

        if not streams:
            feedback.warning(f"No streams found for episode {episode_number}")
            return False

        # Convert to list to check actual availability
        stream_list = list(streams)
        if not stream_list:
            feedback.warning(
                f"No stream servers available for episode {episode_number}"
            )
            return False

        feedback.info(
            f"Found {len(stream_list)} stream server(s) for episode {episode_number}"
        )

        # Show details about the first server for debugging
        first_server = stream_list[0]
        feedback.info(
            f"First server: name='{first_server.name}', type='{type(first_server).__name__}'"
        )

        return True

    except TypeError as e:
        if "'NoneType' object is not subscriptable" in str(e):
            feedback.warning(
                f"Episode {episode_number} not available on provider (API returned null)"
            )
            feedback.info(
                "This usually means the episode doesn't exist on this provider or isn't accessible"
            )
            return False
        else:
            feedback.error(f"Type error testing stream availability: {e}")
            return False
    except Exception as e:
        feedback.error(f"Error testing stream availability: {e}")
        import traceback

        feedback.error("Stream test traceback", traceback.format_exc())
        return False


def _display_download_results(console, results: dict[str, bool], anime):
    """Display download results in a formatted table."""
    from rich.table import Table

    table = Table(
        title=f"Download Results for {anime.title.english or anime.title.romaji}"
    )
    table.add_column("Episode", justify="center", style="cyan")
    table.add_column("Status", justify="center")

    for episode, success in sorted(results.items(), key=lambda x: float(x[0])):
        status = "[green]✓ Success[/green]" if success else "[red]✗ Failed[/red]"
        table.add_row(episode, status)

    console.print(table)

    # Summary
    total = len(results)
    successful = sum(results.values())
    failed = total - successful

    if failed == 0:
        console.print(
            f"\n[bold green]All {total} episodes downloaded successfully![/bold green]"
        )
    else:
        console.print(
            f"\n[yellow]Download complete: {successful}/{total} successful, {failed} failed[/yellow]"
        )


def _show_final_statistics(download_service, feedback):
    """Show final download statistics."""
    from rich.console import Console

    console = Console()
    stats = download_service.get_download_statistics()

    if stats:
        console.print("\n[bold blue]Overall Download Statistics:[/bold blue]")
        console.print(f"Total episodes tracked: {stats.get('total_episodes', 0)}")
        console.print(f"Successfully downloaded: {stats.get('downloaded', 0)}")
        console.print(f"Failed downloads: {stats.get('failed', 0)}")
        console.print(f"Queued downloads: {stats.get('queued', 0)}")

        if stats.get("total_size_bytes", 0) > 0:
            size_mb = stats["total_size_bytes"] / (1024 * 1024)
            if size_mb > 1024:
                console.print(f"Total size: {size_mb / 1024:.2f} GB")
            else:
                console.print(f"Total size: {size_mb:.2f} MB")
