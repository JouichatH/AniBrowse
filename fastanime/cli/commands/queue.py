"""
Queue command for manual download queue management.
"""

import logging
import uuid
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

if TYPE_CHECKING:
    from fastanime.core.config import AppConfig

from ..utils.download_queue import DownloadJob, DownloadStatus, QueueManager
from ..utils.feedback import create_feedback_manager

logger = logging.getLogger(__name__)


@click.command(
    help="Manage the download queue",
    short_help="Download queue management",
    epilog="""
\b
\b\bExamples:
    # Show queue status
    fastanime queue

    # Add anime to download queue
    fastanime queue --add "Attack on Titan" --episode "1"

    # Add with specific quality and priority
    fastanime queue --add "Demon Slayer" --episode "5" --quality "720" --priority 2

    # Clear completed jobs
    fastanime queue --clean

    # Remove specific job
    fastanime queue --remove <job-id>

    # Show detailed queue information
    fastanime queue --detailed
""",
)
@click.option(
    "--add", "-a",
    help="Add anime to download queue (anime title)"
)
@click.option(
    "--episode", "-e",
    help="Episode number to download (required with --add)"
)
@click.option(
    "--quality", "-q",
    type=click.Choice(["360", "480", "720", "1080"]),
    default="1080",
    help="Video quality preference"
)
@click.option(
    "--priority", "-p",
    type=click.IntRange(1, 10),
    default=5,
    help="Download priority (1=highest, 10=lowest)"
)
@click.option(
    "--translation-type", "-t",
    type=click.Choice(["sub", "dub"]),
    default="sub",
    help="Audio/subtitle preference"
)
@click.option(
    "--remove", "-r",
    help="Remove job from queue by ID"
)
@click.option(
    "--clean", "-c",
    is_flag=True,
    help="Remove completed/failed jobs older than 7 days"
)
@click.option(
    "--detailed", "-d",
    is_flag=True,
    help="Show detailed queue information"
)
@click.option(
    "--cancel",
    help="Cancel a specific job by ID"
)
@click.pass_obj
def queue(
    config: "AppConfig", 
    add: str, 
    episode: str, 
    quality: str, 
    priority: int, 
    translation_type: str,
    remove: str,
    clean: bool,
    detailed: bool,
    cancel: str
):
    """Manage the download queue for automated and manual downloads."""
    
    console = Console()
    feedback = create_feedback_manager(config.general.icons)
    queue_manager = QueueManager()
    
    try:
        # Add new job to queue
        if add:
            if not episode:
                feedback.error("Episode number is required when adding to queue", 
                             "Use --episode to specify the episode number")
                raise click.Abort()
            
            job_id = str(uuid.uuid4())
            job = DownloadJob(
                id=job_id,
                anime_title=add,
                episode=episode,
                quality=quality,
                translation_type=translation_type,
                priority=priority,
                auto_added=False
            )
            
            success = queue_manager.add_job(job)
            if success:
                feedback.success(
                    f"Added to queue: {add} Episode {episode}",
                    f"Job ID: {job_id[:8]}... Priority: {priority}"
                )
            else:
                feedback.error("Failed to add job to queue", "Check logs for details")
                raise click.Abort()
            return
        
        # Remove job from queue
        if remove:
            # Allow partial job ID matching
            matching_jobs = [
                job_id for job_id in queue_manager.queue.jobs.keys()
                if job_id.startswith(remove)
            ]
            
            if not matching_jobs:
                feedback.error(f"No job found with ID starting with: {remove}")
                raise click.Abort()
            elif len(matching_jobs) > 1:
                feedback.error(f"Multiple jobs match ID: {remove}", 
                             f"Be more specific. Matches: {[job_id[:8] for job_id in matching_jobs]}")
                raise click.Abort()
            
            job_id = matching_jobs[0]
            job = queue_manager.get_job_by_id(job_id)
            success = queue_manager.remove_job(job_id)
            
            if success:
                feedback.success(
                    f"Removed from queue: {job.anime_title} Episode {job.episode}",
                    f"Job ID: {job_id[:8]}..."
                )
            else:
                feedback.error("Failed to remove job from queue", "Check logs for details")
                raise click.Abort()
            return
        
        # Cancel job
        if cancel:
            # Allow partial job ID matching
            matching_jobs = [
                job_id for job_id in queue_manager.queue.jobs.keys()
                if job_id.startswith(cancel)
            ]
            
            if not matching_jobs:
                feedback.error(f"No job found with ID starting with: {cancel}")
                raise click.Abort()
            elif len(matching_jobs) > 1:
                feedback.error(f"Multiple jobs match ID: {cancel}", 
                             f"Be more specific. Matches: {[job_id[:8] for job_id in matching_jobs]}")
                raise click.Abort()
            
            job_id = matching_jobs[0]
            job = queue_manager.get_job_by_id(job_id)
            success = queue_manager.update_job_status(job_id, DownloadStatus.CANCELLED)
            
            if success:
                feedback.success(
                    f"Cancelled job: {job.anime_title} Episode {job.episode}",
                    f"Job ID: {job_id[:8]}..."
                )
            else:
                feedback.error("Failed to cancel job", "Check logs for details")
                raise click.Abort()
            return
        
        # Clean old completed jobs
        if clean:
            with Progress() as progress:
                task = progress.add_task("Cleaning old jobs...", total=None)
                cleaned_count = queue_manager.clean_completed_jobs()
                progress.update(task, completed=True)
            
            if cleaned_count > 0:
                feedback.success(f"Cleaned {cleaned_count} old jobs from queue")
            else:
                feedback.info("No old jobs to clean")
            return
        
        # Show queue status (default action)
        _display_queue_status(console, queue_manager, detailed, config.general.icons)
        
    except Exception as e:
        feedback.error("An error occurred while managing the queue", str(e))
        logger.error(f"Queue command error: {e}")
        raise click.Abort()


def _display_queue_status(console: Console, queue_manager: QueueManager, detailed: bool, icons: bool):
    """Display the current queue status."""
    
    stats = queue_manager.get_queue_stats()
    
    # Display summary
    console.print()
    console.print(f"{'📥 ' if icons else ''}[bold cyan]Download Queue Status[/bold cyan]")
    console.print()
    
    summary_table = Table(title="Queue Summary")
    summary_table.add_column("Status", style="cyan")
    summary_table.add_column("Count", justify="right", style="green")
    
    summary_table.add_row("Total Jobs", str(stats["total"]))
    summary_table.add_row("Pending", str(stats["pending"]))
    summary_table.add_row("Downloading", str(stats["downloading"]))
    summary_table.add_row("Completed", str(stats["completed"]))
    summary_table.add_row("Failed", str(stats["failed"]))
    summary_table.add_row("Cancelled", str(stats["cancelled"]))
    
    console.print(summary_table)
    console.print()
    
    if detailed or stats["total"] > 0:
        _display_detailed_queue(console, queue_manager, icons)


def _display_detailed_queue(console: Console, queue_manager: QueueManager, icons: bool):
    """Display detailed information about jobs in the queue."""
    
    jobs = queue_manager.get_all_jobs()
    if not jobs:
        console.print(f"{'ℹ️ ' if icons else ''}[dim]No jobs in queue[/dim]")
        return
    
    # Sort jobs by status and creation time
    jobs.sort(key=lambda x: (x.status.value, x.created_at))
    
    table = Table(title="Job Details")
    table.add_column("ID", width=8)
    table.add_column("Anime", style="cyan")
    table.add_column("Episode", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Priority", justify="center")
    table.add_column("Quality", justify="center")
    table.add_column("Type", justify="center")
    table.add_column("Created", style="dim")
    
    status_colors = {
        DownloadStatus.PENDING: "yellow",
        DownloadStatus.DOWNLOADING: "blue",
        DownloadStatus.COMPLETED: "green",
        DownloadStatus.FAILED: "red",
        DownloadStatus.CANCELLED: "dim"
    }
    
    for job in jobs:
        status_color = status_colors.get(job.status, "white")
        auto_marker = f"{'🤖' if icons else 'A'}" if job.auto_added else f"{'👤' if icons else 'M'}"
        
        table.add_row(
            job.id[:8],
            job.anime_title[:30] + "..." if len(job.anime_title) > 30 else job.anime_title,
            job.episode,
            f"[{status_color}]{job.status.value}[/{status_color}]",
            str(job.priority),
            job.quality,
            f"{auto_marker} {job.translation_type}",
            job.created_at.strftime("%m-%d %H:%M")
        )
    
    console.print(table)
    
    if icons:
        console.print()
        console.print("[dim]🤖 = Auto-added, 👤 = Manual[/dim]")
