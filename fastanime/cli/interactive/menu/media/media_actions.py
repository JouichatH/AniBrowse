from typing import Callable, Dict

from rich.console import Console

from .....libs.media_api.params import UpdateUserMediaListEntryParams
from .....libs.media_api.types import UserMediaListStatus
from .....libs.player.params import PlayerParams
from ...session import Context, session
from ...state import InternalDirective, MenuName, State

MenuAction = Callable[[], State | InternalDirective]


@session.menu
def media_actions(ctx: Context, state: State) -> State | InternalDirective:
    feedback = ctx.service.feedback

    icons = ctx.config.general.icons

    media_item = state.media_api.media_item

    if not media_item:
        feedback.error("Media item is not in state")
        return InternalDirective.BACK

    # TODO: Add 'Recommendations' and 'Relations' here later.
    # TODO: Add media list management
    # TODO: cross reference for none implemented features
    options: Dict[str, MenuAction] = {
        f"{'▶️ ' if icons else ''}Stream": _stream(ctx, state),
        f"{'📼 ' if icons else ''}Watch Trailer": _watch_trailer(ctx, state),
        f"{'➕ ' if icons else ''}Add/Update List": _manage_user_media_list(ctx, state),
        f"{'⭐ ' if icons else ''}Score Anime": _score_anime(ctx, state),
        f"{'ℹ️ ' if icons else ''}View Info": _view_info(ctx, state),
        f"{'🔙 ' if icons else ''}Back to Results": lambda: InternalDirective.BACK,
    }

    choice = ctx.selector.choose(
        prompt="Select Action",
        choices=list(options.keys()),
    )

    if choice and choice in options:
        return options[choice]()

    return InternalDirective.BACK


def _stream(ctx: Context, state: State) -> MenuAction:
    def action():
        return State(menu_name=MenuName.PROVIDER_SEARCH, media_api=state.media_api)

    return action


def _watch_trailer(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.service.feedback
        media_item = state.media_api.media_item

        if not media_item:
            return InternalDirective.RELOAD

        if not media_item.trailer or not media_item.trailer.id:
            feedback.warning(
                "No trailer available for this anime",
                "This anime doesn't have a trailer link in the database",
            )
        else:
            trailer_url = f"https://www.youtube.com/watch?v={media_item.trailer.id}"

            ctx.player.play(PlayerParams(url=trailer_url, title=""))

        return InternalDirective.RELOAD

    return action


def _manage_user_media_list(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.service.feedback
        media_item = state.media_api.media_item

        if not media_item:
            return InternalDirective.RELOAD

        if not ctx.media_api.is_authenticated():
            feedback.warning(
                "You are not authenticated",
            )
            return InternalDirective.RELOAD

        status = ctx.selector.choose(
            "Select list status:", choices=[t.value for t in UserMediaListStatus]
        )
        if status:
            # local
            ctx.service.media_registry.update_media_index_entry(
                media_id=media_item.id,
                media_item=media_item,
                status=UserMediaListStatus(status),
            )
            # remote
            ctx.media_api.update_list_entry(
                UpdateUserMediaListEntryParams(
                    media_item.id, status=UserMediaListStatus(status)
                )
            )
        return InternalDirective.RELOAD

    return action


def _score_anime(ctx: Context, state: State) -> MenuAction:
    def action():
        feedback = ctx.service.feedback
        media_item = state.media_api.media_item

        if not media_item:
            return InternalDirective.RELOAD

        if not ctx.media_api.is_authenticated():
            return InternalDirective.RELOAD

        score_str = ctx.selector.ask("Enter score (0.0 - 10.0):")
        try:
            score = float(score_str) if score_str else 0.0
            if not 0.0 <= score <= 10.0:
                raise ValueError("Score out of range.")
            # local
            ctx.service.media_registry.update_media_index_entry(
                media_id=media_item.id, media_item=media_item, score=score
            )
            # remote
            ctx.media_api.update_list_entry(
                UpdateUserMediaListEntryParams(media_id=media_item.id, score=score)
            )
        except (ValueError, TypeError):
            feedback.error(
                "Invalid score entered", "Please enter a number between 0.0 and 10.0"
            )
        return InternalDirective.RELOAD

    return action


def _view_info(ctx: Context, state: State) -> MenuAction:
    def action():
        media_item = state.media_api.media_item

        if not media_item:
            return InternalDirective.RELOAD

        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        from ....utils import image

        # TODO: make this look nicer plus add other fields
        console = Console()
        title = Text(
            media_item.title.english or media_item.title.romaji or "", style="bold cyan"
        )
        description = Text(media_item.description or "NO description")
        genres = Text(f"Genres: {', '.join([v.value for v in media_item.genres])}")

        panel_content = f"{genres}\n\n{description}"

        console.clear()
        if cover_image := media_item.cover_image:
            image.render_image(cover_image.large)

        console.print(Panel(panel_content, title=title, box=box.ROUNDED, expand=True))
        ctx.selector.ask("Press Enter to continue...")
        return InternalDirective.RELOAD

    return action
