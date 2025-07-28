from .....libs.player.params import PlayerParams
from ....service.registry.models import DownloadStatus
from ...session import Context, session
from ...state import InternalDirective, State


@session.menu
def play_downloads(ctx: Context, state: State) -> State | InternalDirective:
    """Menu to select and play locally downloaded episodes."""
    feedback = ctx.feedback
    media_item = state.media_api.media_item
    if not media_item:
        feedback.error("No media item selected.")
        return InternalDirective.BACK

    record = ctx.media_registry.get_media_record(media_item.id)
    if not record or not record.media_episodes:
        feedback.warning("No downloaded episodes found for this anime.")
        return InternalDirective.BACK

    downloaded_episodes = {
        ep.episode_number: ep.file_path
        for ep in record.media_episodes
        if ep.download_status == DownloadStatus.COMPLETED
        and ep.file_path
        and ep.file_path.exists()
    }

    if not downloaded_episodes:
        feedback.warning("No complete downloaded episodes found.")
        return InternalDirective.BACK

    choices = list(downloaded_episodes.keys()) + ["Back"]
    chosen_episode = ctx.selector.choose("Select a downloaded episode to play", choices)

    if not chosen_episode or chosen_episode == "Back":
        return InternalDirective.BACK

    file_path = downloaded_episodes[chosen_episode]

    # Use the player service to play the local file
    title = f"{media_item.title.english or media_item.title.romaji} - Episode {chosen_episode}"
    player_result = ctx.player.play(
        PlayerParams(
            url=str(file_path),
            title=title,
            query=media_item.title.english or media_item.title.romaji or "",
            episode=chosen_episode,
        )
    )

    # Track watch history after playing
    ctx.watch_history.track(media_item, player_result)

    # Stay on this menu to allow playing another downloaded episode
    return InternalDirective.RELOAD
