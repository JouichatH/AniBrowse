"""
Single download command for the anilist CLI.

Handles downloading specific episodes or continuing from watch history.
"""

import click
from pathlib import Path
from typing import List, Optional

from ....core.config.model import AppConfig
from ....libs.api.types import MediaItem
from ...services.downloads import get_download_manager
from ...services.watch_history.manager import WatchHistoryManager


def parse_episode_range(range_str: str) -> List[int]:
    """Parse episode range string into list of episode numbers."""
    episodes = []
    
    for part in range_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = map(int, part.split('-', 1))
            episodes.extend(range(start, end + 1))
        else:
            episodes.append(int(part))
    
    return sorted(set(episodes))  # Remove duplicates and sort


@click.command(name="download")
@click.argument("query", required=False)
@click.option("--episode", "-e", type=int, help="Specific episode number")
@click.option("--range", "-r", help="Episode range (e.g., 1-12, 5,7,9)")
@click.option("--quality", "-q", 
              type=click.Choice(["360", "480", "720", "1080", "best"]), 
              help="Preferred download quality")
@click.option("--continue", "continue_watch", is_flag=True, 
              help="Continue from watch history")
@click.option("--background", "-b", is_flag=True, 
              help="Download in background")
@click.option("--path", type=click.Path(exists=True, file_okay=False, dir_okay=True), 
              help="Custom download location")
@click.option("--subtitles/--no-subtitles", default=None, 
              help="Include subtitles (overrides config)")
@click.option("--priority", type=int, default=0, 
              help="Download priority (higher number = higher priority)")
@click.pass_context
def download(ctx: click.Context, query: Optional[str], episode: Optional[int], 
             range: Optional[str], quality: Optional[str], continue_watch: bool,
             background: bool, path: Optional[str], subtitles: Optional[bool],
             priority: int):
    """
    Download anime episodes with tracking.
    
    Examples:
    
    \b
    # Download specific episode
    fastanime anilist download "Attack on Titan" --episode 1
    
    \b
    # Download episode range
    fastanime anilist download "Naruto" --range "1-5,10,15-20"
    
    \b
    # Continue from watch history
    fastanime anilist download --continue
    
    \b
    # Download with custom quality
    fastanime anilist download "One Piece" --episode 1000 --quality 720
    """
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        # Handle continue from watch history
        if continue_watch:
            if query:
                click.echo("--continue flag cannot be used with a search query", err=True)
                ctx.exit(1)
            
            # Get current watching anime from history
            watch_manager = WatchHistoryManager()
            current_watching = watch_manager.get_currently_watching()
            
            if not current_watching:
                click.echo("No anime currently being watched found in history", err=True)
                ctx.exit(1)
            
            if len(current_watching) == 1:
                media_item = current_watching[0].media_item
                next_episode = current_watching[0].last_watched_episode + 1
                episodes_to_download = [next_episode]
            else:
                # Multiple anime, let user choose
                click.echo("Multiple anime found in watch history:")
                for i, entry in enumerate(current_watching):
                    title = entry.media_item.title.english or entry.media_item.title.romaji
                    next_ep = entry.last_watched_episode + 1
                    click.echo(f"  {i + 1}. {title} (next episode: {next_ep})")
                
                choice = click.prompt("Select anime to download", type=int)
                if choice < 1 or choice > len(current_watching):
                    click.echo("Invalid selection", err=True)
                    ctx.exit(1)
                
                selected_entry = current_watching[choice - 1]
                media_item = selected_entry.media_item
                next_episode = selected_entry.last_watched_episode + 1
                episodes_to_download = [next_episode]
        
        else:
            # Search for anime
            if not query:
                click.echo("Query is required when not using --continue", err=True)
                ctx.exit(1)
            
            # TODO: Integrate with search functionality
            # For now, this is a placeholder - you'll need to integrate with your existing search system
            click.echo(f"Searching for: {query}")
            click.echo("Note: Search integration not yet implemented in this example")
            ctx.exit(1)
        
        # Determine episodes to download
        if episode:
            episodes_to_download = [episode]
        elif range:
            try:
                episodes_to_download = parse_episode_range(range)
            except ValueError as e:
                click.echo(f"Invalid episode range: {e}", err=True)
                ctx.exit(1)
        elif not continue_watch:
            # Default to episode 1 if nothing specified
            episodes_to_download = [1]
        
        # Validate episodes
        if not episodes_to_download:
            click.echo("No episodes specified for download", err=True)
            ctx.exit(1)
        
        if media_item.episodes and max(episodes_to_download) > media_item.episodes:
            click.echo(f"Episode {max(episodes_to_download)} exceeds total episodes ({media_item.episodes})", err=True)
            ctx.exit(1)
        
        # Use quality from config if not specified
        if not quality:
            quality = config.downloads.preferred_quality
        
        # Add to download queue
        success = download_manager.add_to_queue(
            media_item=media_item,
            episodes=episodes_to_download,
            quality=quality,
            priority=priority
        )
        
        if success:
            title = media_item.title.english or media_item.title.romaji
            episode_text = f"episode {episodes_to_download[0]}" if len(episodes_to_download) == 1 else f"{len(episodes_to_download)} episodes"
            
            click.echo(f"✓ Added {episode_text} of '{title}' to download queue")
            
            if background:
                click.echo("Download will continue in the background")
            else:
                click.echo("Run 'fastanime anilist downloads status' to monitor progress")
        else:
            click.echo("Failed to add episodes to download queue", err=True)
            ctx.exit(1)
    
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(1)
