from typing import Callable, Dict

from rich.console import Console

from ....libs.api.params import UpdateListEntryParams
from ....libs.api.types import MediaItem
from ....libs.players.params import PlayerParams
from ..session import Context, session
from ..state import ControlFlow, ProviderState, State

MenuAction = Callable[[], State | ControlFlow]


@session.menu
def media_actions(ctx: Context, state: State) -> State | ControlFlow:
    icons = ctx.config.general.icons
    anime = state.media_api.anime
    anime_title = anime.title.english or anime.title.romaji if anime else "Unknown"

    # TODO: Add 'Recommendations' and 'Relations' here later.
    # TODO: Add media list management
    # TODO: cross reference for none implemented features
    options: Dict[str, MenuAction] = {
        f"{'▶️ ' if icons else ''}Stream": _stream(ctx, state),
        f"{'📼 ' if icons else ''}Watch Trailer": _watch_trailer(ctx, state),
        f"{'➕ ' if icons else ''}Add/Update List": _add_to_list(ctx, state),
        f"{'⭐ ' if icons else ''}Score Anime": _score_anime(ctx, state),
        f"{'ℹ️ ' if icons else ''}View Info": _view_info(ctx, state),
        f"{'🔙 ' if icons else ''}Back to Results": lambda: ControlFlow.BACK,
    }

    choice_str = ctx.selector.choose(
        prompt="Select Action",
        choices=list(options.keys()),
    )

    if choice_str and choice_str in options:
        return options[choice_str]()

    return ControlFlow.BACK


# --- Action Implementations ---
def _stream(ctx: Context, state: State) -> MenuAction:
    def action():
        return State(
            menu_name="PROVIDER_SEARCH",
            media_api=state.media_api,  # Carry over the existing api state
            provider=ProviderState(),  # Initialize a fresh provider state
        )

    return action


def _watch_trailer(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.services.feedback
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE
        if not anime.trailer or not anime.trailer.id:
            feedback.warning(
                "No trailer available for this anime",
                "This anime doesn't have a trailer link in the database",
            )
        else:
            trailer_url = f"https://www.youtube.com/watch?v={anime.trailer.id}"

            ctx.player.play(PlayerParams(url=trailer_url, title=""))

        return ControlFlow.CONTINUE

    return action


def _add_to_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.services.feedback
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        if not ctx.media_api.is_authenticated():
            return ControlFlow.CONTINUE

        choices = [
            "watching",
            "planning",
            "completed",
            "dropped",
            "paused",
            "repeating",
        ]
        status = ctx.selector.choose("Select list status:", choices=choices)
        if status:
            _update_user_list(
                ctx,
                anime,
                UpdateListEntryParams(media_id=anime.id, status=status),  # pyright:ignore
                feedback,
            )
        return ControlFlow.CONTINUE

    return action


def _score_anime(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.services.feedback
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        # Check authentication before proceeding
        if not ctx.media_api.is_authenticated():
            return ControlFlow.CONTINUE

        score_str = ctx.selector.ask("Enter score (0.0 - 10.0):")
        try:
            score = float(score_str) if score_str else 0.0
            if not 0.0 <= score <= 10.0:
                raise ValueError("Score out of range.")
            _update_user_list(
                ctx,
                anime,
                UpdateListEntryParams(media_id=anime.id, score=score),
                feedback,
            )
        except (ValueError, TypeError):
            feedback.error(
                "Invalid score entered", "Please enter a number between 0.0 and 10.0"
            )
        return ControlFlow.CONTINUE

    return action


def _view_info(ctx: Context, state: State) -> MenuAction:
    def action():
        anime = state.media_api.anime
        if not anime:
            return ControlFlow.CONTINUE

        # TODO: Make this nice and include all other media item fields
        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        from ...utils import image

        console = Console()
        title = Text(anime.title.english or anime.title.romaji or "", style="bold cyan")
        description = Text(anime.description or "NO description")
        genres = Text(f"Genres: {', '.join([v.value for v in anime.genres])}")

        panel_content = f"{genres}\n\n{description}"

        console.clear()
        if cover_image := anime.cover_image:
            image.render_image(cover_image.large)

        console.print(Panel(panel_content, title=title, box=box.ROUNDED, expand=True))
        ctx.selector.ask("Press Enter to continue...")
        return ControlFlow.CONTINUE

    return action


def _update_user_list(
    ctx: Context, anime: MediaItem, params: UpdateListEntryParams, feedback
):
    if ctx.media_api.is_authenticated():
        return ControlFlow.CONTINUE

    ctx.media_api.update_list_entry(params)
