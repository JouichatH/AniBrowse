"""
Downloads management commands for the anilist CLI.

Provides comprehensive download management including listing, status monitoring,
cleanup, and verification operations.
"""

import click
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ....core.config.model import AppConfig
from ...services.downloads import get_download_manager
from ...services.downloads.validator import DownloadValidator


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: Optional[float]) -> str:
    """Format duration in human-readable format."""
    if seconds is None:
        return "Unknown"
    
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.0f}m {seconds%60:.0f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {minutes:.0f}m"


@click.group(name="downloads")
@click.pass_context
def downloads(ctx: click.Context):
    """Manage downloaded anime."""
    pass


@downloads.command()
@click.option("--status", 
              type=click.Choice(["all", "completed", "active", "failed", "paused"]),
              default="all",
              help="Filter by download status")
@click.option("--format", "output_format",
              type=click.Choice(["table", "json", "simple"]), 
              default="table",
              help="Output format")
@click.option("--limit", type=int, help="Limit number of results")
@click.pass_context
def list(ctx: click.Context, status: str, output_format: str, limit: Optional[int]):
    """List all downloads."""
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        # Get download records
        status_filter = None if status == "all" else status
        records = download_manager.list_downloads(status_filter=status_filter, limit=limit)
        
        if not records:
            click.echo("No downloads found")
            return
        
        if output_format == "json":
            # JSON output
            output_data = []
            for record in records:
                output_data.append({
                    "media_id": record.media_item.id,
                    "title": record.display_title,
                    "status": record.status,
                    "episodes_downloaded": record.total_episodes_downloaded,
                    "total_episodes": record.media_item.episodes or 0,
                    "completion_percentage": record.completion_percentage,
                    "total_size_gb": record.total_size_gb,
                    "last_updated": record.last_updated.isoformat()
                })
            
            click.echo(json.dumps(output_data, indent=2))
        
        elif output_format == "simple":
            # Simple text output
            for record in records:
                title = record.display_title
                status_emoji = {
                    "completed": "✓",
                    "active": "⬇",
                    "failed": "✗",
                    "paused": "⏸"
                }.get(record.status, "?")
                
                click.echo(f"{status_emoji} {title} ({record.total_episodes_downloaded}/{record.media_item.episodes or 0} episodes)")
        
        else:
            # Table output (default)
            click.echo()
            click.echo("Downloads:")
            click.echo("=" * 80)
            
            # Header
            header = f"{'Title':<30} {'Status':<10} {'Episodes':<12} {'Size':<10} {'Updated':<15}"
            click.echo(header)
            click.echo("-" * 80)
            
            # Rows
            for record in records:
                title = record.display_title
                if len(title) > 28:
                    title = title[:25] + "..."
                
                status_display = record.status.capitalize()
                
                episodes_display = f"{record.total_episodes_downloaded}/{record.media_item.episodes or '?'}"
                
                size_display = format_size(record.total_size_bytes)
                
                updated_display = record.last_updated.strftime("%Y-%m-%d")
                
                row = f"{title:<30} {status_display:<10} {episodes_display:<12} {size_display:<10} {updated_display:<15}"
                click.echo(row)
            
            click.echo("-" * 80)
            click.echo(f"Total: {len(records)} anime")
    
    except Exception as e:
        click.echo(f"Error listing downloads: {e}", err=True)
        ctx.exit(1)


@downloads.command()
@click.pass_context
def status(ctx: click.Context):
    """Show download queue status and statistics."""
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        # Get statistics
        stats = download_manager.get_download_stats()
        
        click.echo()
        click.echo("Download Statistics:")
        click.echo("=" * 40)
        click.echo(f"Total Anime: {stats.get('total_anime', 0)}")
        click.echo(f"Total Episodes: {stats.get('total_episodes', 0)}")
        click.echo(f"Total Size: {stats.get('total_size_gb', 0):.2f} GB")
        click.echo(f"Queue Size: {stats.get('queue_size', 0)}")
        
        # Show completion stats
        completion_stats = stats.get('completion_stats', {})
        if completion_stats:
            click.echo()
            click.echo("Status Breakdown:")
            click.echo("-" * 20)
            for status, count in completion_stats.items():
                click.echo(f"  {status.capitalize()}: {count}")
        
        # Show active downloads
        queue = download_manager._load_queue()
        if queue.items:
            click.echo()
            click.echo("Download Queue:")
            click.echo("-" * 30)
            for item in queue.items[:5]:  # Show first 5 items
                title = f"Media {item.media_id}"  # Would need to lookup title
                click.echo(f"  Episode {item.episode_number} of {title} ({item.quality_preference})")
            
            if len(queue.items) > 5:
                click.echo(f"  ... and {len(queue.items) - 5} more items")
    
    except Exception as e:
        click.echo(f"Error getting download status: {e}", err=True)
        ctx.exit(1)


@downloads.command()
@click.option("--dry-run", is_flag=True, help="Show what would be cleaned without doing it")
@click.pass_context
def clean(ctx: click.Context, dry_run: bool):
    """Clean up failed downloads and orphaned entries."""
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        if dry_run:
            click.echo("Dry run mode - no changes will be made")
            click.echo()
        
        # Clean up failed downloads
        if not dry_run:
            failed_count = download_manager.cleanup_failed_downloads()
            click.echo(f"Cleaned up {failed_count} failed downloads")
        else:
            click.echo("Would clean up failed downloads older than retention period")
        
        # Clean up orphaned files
        validator = DownloadValidator(download_manager)
        if not dry_run:
            orphaned_count = validator.cleanup_orphaned_files()
            click.echo(f"Cleaned up {orphaned_count} orphaned files")
        else:
            click.echo("Would clean up orphaned files and fix index inconsistencies")
        
        if dry_run:
            click.echo()
            click.echo("Run without --dry-run to perform actual cleanup")
    
    except Exception as e:
        click.echo(f"Error during cleanup: {e}", err=True)
        ctx.exit(1)


@downloads.command()
@click.argument("media_id", type=int, required=False)
@click.option("--all", "verify_all", is_flag=True, help="Verify all downloads")
@click.pass_context
def verify(ctx: click.Context, media_id: Optional[int], verify_all: bool):
    """Verify download integrity for specific anime or all downloads."""
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        validator = DownloadValidator(download_manager)
        
        if verify_all:
            click.echo("Generating comprehensive validation report...")
            report = validator.generate_validation_report()
            
            click.echo()
            click.echo("Validation Report:")
            click.echo("=" * 50)
            click.echo(f"Total Records: {report['total_records']}")
            click.echo(f"Valid Records: {report['valid_records']}")
            click.echo(f"Invalid Records: {report['invalid_records']}")
            click.echo(f"Integrity Issues: {report['integrity_issues']}")
            click.echo(f"Path Issues: {report['path_issues']}")
            click.echo(f"Orphaned Files: {report['orphaned_files']}")
            
            if report['details']['invalid_files']:
                click.echo()
                click.echo("Invalid Files:")
                for file_path in report['details']['invalid_files']:
                    click.echo(f"  - {file_path}")
            
            if report['details']['integrity_failures']:
                click.echo()
                click.echo("Integrity Failures:")
                for failure in report['details']['integrity_failures']:
                    click.echo(f"  - {failure['title']}: Episodes {failure['failed_episodes']}")
        
        elif media_id:
            record = download_manager.get_download_record(media_id)
            if not record:
                click.echo(f"No download record found for media ID {media_id}", err=True)
                ctx.exit(1)
            
            click.echo(f"Verifying downloads for: {record.display_title}")
            
            # Verify integrity
            integrity_results = validator.verify_file_integrity(record)
            
            # Verify paths
            path_issues = validator.validate_file_paths(record)
            
            # Display results
            click.echo()
            click.echo("Episode Verification:")
            click.echo("-" * 30)
            
            for episode_num, episode_download in record.episodes.items():
                status_emoji = "✓" if integrity_results.get(episode_num, False) else "✗"
                click.echo(f"  {status_emoji} Episode {episode_num} ({episode_download.status})")
                
                if not integrity_results.get(episode_num, False):
                    if not episode_download.file_path.exists():
                        click.echo(f"    - File missing: {episode_download.file_path}")
                    elif episode_download.checksum and not episode_download.verify_integrity():
                        click.echo(f"    - Checksum mismatch")
            
            if path_issues:
                click.echo()
                click.echo("Path Issues:")
                for issue in path_issues:
                    click.echo(f"  - {issue}")
        
        else:
            click.echo("Specify --all to verify all downloads or provide a media ID", err=True)
            ctx.exit(1)
    
    except Exception as e:
        click.echo(f"Error during verification: {e}", err=True)
        ctx.exit(1)


@downloads.command()
@click.argument("output_file", type=click.Path())
@click.option("--format", "export_format",
              type=click.Choice(["json", "csv"]),
              default="json",
              help="Export format")
@click.pass_context
def export(ctx: click.Context, output_file: str, export_format: str):
    """Export download list to a file."""
    
    config: AppConfig = ctx.obj
    download_manager = get_download_manager(config.downloads)
    
    try:
        records = download_manager.list_downloads()
        output_path = Path(output_file)
        
        if export_format == "json":
            export_data = []
            for record in records:
                export_data.append({
                    "media_id": record.media_item.id,
                    "title": record.display_title,
                    "status": record.status,
                    "episodes": {
                        str(ep_num): {
                            "episode_number": ep.episode_number,
                            "file_path": str(ep.file_path),
                            "file_size": ep.file_size,
                            "quality": ep.quality,
                            "status": ep.status,
                            "download_date": ep.download_date.isoformat()
                        }
                        for ep_num, ep in record.episodes.items()
                    },
                    "download_path": str(record.download_path),
                    "created_date": record.created_date.isoformat(),
                    "last_updated": record.last_updated.isoformat()
                })
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        elif export_format == "csv":
            import csv
            
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Write header
                writer.writerow([
                    "Media ID", "Title", "Status", "Episodes Downloaded",
                    "Total Episodes", "Total Size (GB)", "Last Updated"
                ])
                
                # Write data
                for record in records:
                    writer.writerow([
                        record.media_item.id,
                        record.display_title,
                        record.status,
                        record.total_episodes_downloaded,
                        record.media_item.episodes or 0,
                        f"{record.total_size_gb:.2f}",
                        record.last_updated.strftime("%Y-%m-%d %H:%M:%S")
                    ])
        
        click.echo(f"Exported {len(records)} download records to {output_path}")
    
    except Exception as e:
        click.echo(f"Error exporting downloads: {e}", err=True)
        ctx.exit(1)
