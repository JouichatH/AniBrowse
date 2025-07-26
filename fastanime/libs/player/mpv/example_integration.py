"""
Example integration of IPC MPV Player with FastAnime.

This shows how to use the updated PlayerParams with IPC-specific parameters
for episode navigation features. The IPC player is automatically used when
mpv.use_ipc is enabled and the required parameters are provided.
"""

from typing import List, Literal, Optional

from ....libs.player.params import PlayerParams
from ....libs.provider.anime.base import BaseAnimeProvider
from ....libs.provider.anime.types import Anime


def create_ipc_player_params(
    url: str,
    title: str,
    provider: BaseAnimeProvider,
    anime: Anime,
    current_episode: str,
    translation_type: Literal["sub", "dub"] = "sub",
    subtitles: Optional[List[str]] = None,
    headers: Optional[dict] = None,
    start_time: Optional[str] = None
) -> PlayerParams:
    """
    Create PlayerParams with IPC player dependencies for episode navigation.
    
    Args:
        url: Stream URL
        title: Episode title
        provider: Anime provider for fetching episode streams
        anime: Current anime object
        current_episode: Current episode number
        translation_type: Translation type ("sub" or "dub")
        subtitles: List of subtitle URLs
        headers: HTTP headers for streaming
        start_time: Start time for playback
    
    Returns:
        PlayerParams configured for IPC player
    """
    # Get available episodes for the translation type
    available_episodes: List[str] = getattr(anime.episodes, translation_type, [])
    
    return PlayerParams(
        url=url,
        title=title,
        subtitles=subtitles,
        headers=headers,
        start_time=start_time,
        # IPC-specific parameters
        anime_provider=provider,
        current_anime=anime,
        available_episodes=available_episodes,
        current_episode=current_episode,
        current_anime_id=anime.id,
        current_anime_title=anime.title,
        current_translation_type=translation_type
    )


def example_usage():
    """Example of how to use the IPC player in an interactive session."""
    # This would typically be called from within the servers.py menu
    # when the IPC player is enabled
    
    # Updated integration example:
    """
    # In servers.py, around line 82:
    
    if config.mpv.use_ipc and state.provider.anime:
        # Get available episodes for current translation type
        available_episodes = getattr(
            state.provider.anime.episodes, 
            config.stream.translation_type, 
            []
        )
        
        # Create player params with IPC dependencies
        player_result = ctx.player.play(
            PlayerParams(
                url=stream_link_obj.link,
                title=final_title,
                subtitles=[sub.url for sub in selected_server.subtitles],
                headers=selected_server.headers,
                start_time=state.provider.start_time,
                # IPC-specific parameters
                anime_provider=provider,
                current_anime=state.provider.anime,
                available_episodes=available_episodes,
                current_episode=episode_number,
                current_anime_id=state.provider.anime.id,
                current_anime_title=state.provider.anime.title,
                current_translation_type=config.stream.translation_type
            )
        )
    else:
        # Use regular player without IPC features
        player_result = ctx.player.play(
            PlayerParams(
                url=stream_link_obj.link,
                title=final_title,
                subtitles=[sub.url for sub in selected_server.subtitles],
                headers=selected_server.headers,
                start_time=state.provider.start_time,
            )
        )
    """
    pass


# Key features enabled by IPC player:
# 
# 1. Episode Navigation:
#    - Shift+N: Next episode
#    - Shift+P: Previous episode
#    - Shift+R: Reload current episode
# 
# 2. Quality/Server switching:
#    - Script message: select-quality 720
#    - Script message: select-server gogoanime
# 
# 3. Episode jumping:
#    - Script message: select-episode 5
# 
# 4. Translation type switching:
#    - Shift+T: Toggle between sub/dub
# 
# 5. Auto-next episode (when implemented):
#    - Automatically plays next episode when current one ends
#
# To send script messages from MPV console (` key):
# script-message select-episode 5
# script-message select-quality 1080  
# script-message select-server top
#
# Configuration:
# To enable IPC player, set in config: mpv.use_ipc = true
#
# The IPC player will automatically be used when:
# 1. mpv.use_ipc is enabled in config
# 2. The required anime provider and episode data is passed in PlayerParams
# 3. MPV executable is available and unix sockets are supported (Linux/macOS)
