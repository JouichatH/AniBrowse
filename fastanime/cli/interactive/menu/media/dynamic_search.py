import json
import logging
import os
import tempfile

from .....core.constants import APP_CACHE_DIR, SCRIPTS_DIR
from .....libs.media_api.params import MediaSearchParams
from ...session import Context, session
from ...state import InternalDirective, MediaApiState, MenuName, State

logger = logging.getLogger(__name__)

SEARCH_CACHE_DIR = APP_CACHE_DIR / "search"
SEARCH_RESULTS_FILE = SEARCH_CACHE_DIR / "current_search_results.json"
FZF_SCRIPTS_DIR = SCRIPTS_DIR / "fzf"
SEARCH_TEMPLATE_SCRIPT = (FZF_SCRIPTS_DIR / "search.template.sh").read_text(
    encoding="utf-8"
)


@session.menu
def dynamic_search(ctx: Context, state: State) -> State | InternalDirective:
    """Dynamic search menu that provides real-time search results."""
    feedback = ctx.feedback
    feedback.clear_console()

    # Ensure cache directory exists
    SEARCH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Read the GraphQL search query
    from .....libs.media_api.anilist import gql

    search_query = gql.SEARCH_MEDIA.read_text(encoding="utf-8")
    # Properly escape the GraphQL query for JSON
    search_query_escaped = json.dumps(search_query)

    # Prepare the search script
    auth_header = ""
    if ctx.media_api.is_authenticated() and hasattr(ctx.media_api, "token"):
        auth_header = f"Bearer {ctx.media_api.token}"

    # Create a temporary search script
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False
    ) as temp_script:
        script_content = SEARCH_TEMPLATE_SCRIPT

        replacements = {
            "GRAPHQL_ENDPOINT": "https://graphql.anilist.co",
            "GRAPHQL_QUERY": search_query_escaped,
            "CACHE_DIR": str(SEARCH_CACHE_DIR),
            "SEARCH_RESULTS_FILE": str(SEARCH_RESULTS_FILE),
            "AUTH_HEADER": auth_header,
        }

        for key, value in replacements.items():
            script_content = script_content.replace(f"{{{key}}}", str(value))

        temp_script.write(script_content)
        temp_script_path = temp_script.name

    try:
        # Make the script executable
        os.chmod(temp_script_path, 0o755)

        # Use the selector's search functionality
        try:
            # Prepare preview functionality
            preview_command = None
            if ctx.config.general.preview != "none":
                from ....utils.preview import create_preview_context

                with create_preview_context() as preview_ctx:
                    preview_command = preview_ctx.get_dynamic_anime_preview(ctx.config)

                    choice = ctx.selector.search(
                        prompt="Search Anime",
                        search_command=f"bash {temp_script_path} {{q}}",
                        preview=preview_command,
                        header="Type to search for anime dynamically",
                    )
            else:
                choice = ctx.selector.search(
                    prompt="Search Anime",
                    search_command=f"bash {temp_script_path} {{q}}",
                    header="Type to search for anime dynamically",
                )
        except NotImplementedError:
            feedback.error("Dynamic search is not supported by your current selector")
            feedback.info(
                "Please use the regular search option or switch to fzf selector"
            )
            return InternalDirective.MAIN

        if not choice:
            return InternalDirective.MAIN

        # Read the cached search results
        if not SEARCH_RESULTS_FILE.exists():
            logger.error("Search results file not found")
            return InternalDirective.MAIN

        try:
            with open(SEARCH_RESULTS_FILE, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            # Transform the raw data into MediaSearchResult
            search_result = ctx.media_api.transform_raw_search_data(raw_data)

            if not search_result or not search_result.media:
                feedback.info("No results found")
                return InternalDirective.MAIN

            # Find the selected media item by matching the choice with the displayed format
            selected_media = None
            for media_item in search_result.media:
                title = (
                    media_item.title.english
                    or media_item.title.romaji
                    or media_item.title.native
                    or "Unknown"
                )
                year = (
                    media_item.start_date.year if media_item.start_date else "Unknown"
                )
                status = media_item.status.value if media_item.status else "Unknown"
                genres = (
                    ", ".join([genre.value for genre in media_item.genres[:3]])
                    if media_item.genres
                    else "Unknown"
                )

                display_format = f"{title} ({year}) [{status}] - {genres}"

                if choice.strip() == display_format.strip():
                    selected_media = media_item
                    break

            if not selected_media:
                logger.error(f"Could not find selected media for choice: {choice}")
                return InternalDirective.MAIN

            # Navigate to media actions with the selected item
            return State(
                menu_name=MenuName.MEDIA_ACTIONS,
                media_api=MediaApiState(
                    search_result={selected_media.id: selected_media},
                    media_id=selected_media.id,
                    search_params=MediaSearchParams(),
                    page_info=search_result.page_info,
                ),
            )

        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.error(f"Error processing search results: {e}")
            feedback.error("Failed to process search results")
            return InternalDirective.MAIN

    finally:
        # Clean up the temporary script
        try:
            os.unlink(temp_script_path)
        except OSError:
            pass
