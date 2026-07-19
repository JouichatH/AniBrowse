import logging
from typing import Dict

from .....libs.media_api.types import MediaItem
from ...session import Context, session
from ...state import InternalDirective, MediaApiState, MenuName, State
from ._cursor import remembered_choose

logger = logging.getLogger(__name__)


@session.menu
def downloads(ctx: Context, state: State) -> State | InternalDirective:
    """The offline library: only shows that actually have downloaded episodes.

    This used to mirror every registry category ("Trending (Local)" etc.),
    which listed anything the user had merely *watched* and offered online
    streaming from a page called Downloads. Now it lists downloaded shows
    only, and picking one opens its downloaded-episode list for offline
    playback. With nothing downloaded it explains how to start instead of
    presenting an empty maze.
    """
    from ....service.registry.models import DownloadStatus

    icons = ctx.config.general.icons
    feedback = ctx.feedback
    feedback.clear_console()

    library: list[tuple[MediaItem, int]] = []
    in_progress = 0
    for record in ctx.media_registry.get_all_media_records():
        completed = sum(
            1
            for ep in record.media_episodes
            if ep.download_status == DownloadStatus.COMPLETED
            and ep.file_path
            and ep.file_path.exists()
        )
        in_progress += sum(
            1
            for ep in record.media_episodes
            if ep.download_status
            in (DownloadStatus.QUEUED, DownloadStatus.DOWNLOADING)
        )
        if completed:
            library.append((record.media_item, completed))

    if not library:
        if in_progress:
            feedback.info(
                f"{in_progress} episode download(s) still in progress",
                "They will appear here once finished.",
            )
        else:
            feedback.info(
                "Your downloads library is empty",
                "Open any show (Search, Trending, Continue Watching...) and "
                "choose 'Download' to save episodes here for offline watching.",
            )
        feedback.pause_for_user()
        return InternalDirective.BACK

    def _title(item: MediaItem) -> str:
        return item.title.english or item.title.romaji or f"Media {item.id}"

    library.sort(key=lambda pair: _title(pair[0]).lower())

    by_label: Dict[str, MediaItem] = {}
    for item, count in library:
        plural = "s" if count != 1 else ""
        label = f"{'💿 ' if icons else ''}{_title(item)} ({count} episode{plural} downloaded)"
        by_label[label] = item

    back_label = f"{'↩️ ' if icons else ''}Back to Main"
    exit_label = f"{'❌ ' if icons else ''}Exit"
    choices = [*by_label.keys(), back_label, exit_label]

    if in_progress:
        feedback.info(f"{in_progress} episode download(s) still in progress.")

    choice = remembered_choose(
        ctx.selector,
        "downloads",
        prompt="Downloads Library",
        choices=choices,
    )
    if not choice:
        return InternalDirective.RELOAD
    if choice == back_label:
        return InternalDirective.BACK
    if choice == exit_label:
        return InternalDirective.EXIT

    media_item = by_label[choice]
    # Always surface the downloaded-episode list: from a library page the user
    # should see exactly what's on disk, not be auto-played into an episode.
    ctx.switch.force_episodes_menu()
    return State(
        menu_name=MenuName.PLAY_DOWNLOADS,
        media_api=MediaApiState(
            search_result={media_item.id: media_item},
            media_id=media_item.id,
        ),
    )
