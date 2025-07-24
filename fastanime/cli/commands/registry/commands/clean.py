"""
Registry clean command - clean up orphaned entries and invalid data
"""

import click
from rich.console import Console
from rich.table import Table

from .....core.config import AppConfig
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(help="Clean up orphaned entries and invalid data from registry")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be cleaned without making changes"
)
@click.option(
    "--orphaned",
    is_flag=True,
    help="Remove orphaned media records (index entries without files)"
)
@click.option(
    "--invalid",
    is_flag=True,
    help="Remove invalid or corrupted entries"
)
@click.option(
    "--duplicates",
    is_flag=True,
    help="Remove duplicate entries"
)
@click.option(
    "--old-format",
    is_flag=True,
    help="Clean entries from old registry format versions"
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force cleanup without confirmation prompts"
)
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API registry to clean"
)
@click.pass_obj
def clean(
    config: AppConfig,
    dry_run: bool,
    orphaned: bool,
    invalid: bool,
    duplicates: bool,
    old_format: bool,
    force: bool,
    api: str
):
    """
    Clean up your local media registry.
    
    Can remove orphaned entries, invalid data, duplicates, and entries
    from old format versions. Use --dry-run to preview changes.
    """
    feedback = create_feedback_manager(config.general.icons)
    console = Console()
    
    # Default to all cleanup types if none specified
    if not any([orphaned, invalid, duplicates, old_format]):
        orphaned = invalid = duplicates = old_format = True
    
    try:
        registry_service = MediaRegistryService(api, config.registry)
        
        cleanup_results = {
            "orphaned": [],
            "invalid": [],
            "duplicates": [],
            "old_format": []
        }
        
        # Analyze registry for cleanup opportunities
        _analyze_registry(registry_service, cleanup_results, orphaned, invalid, duplicates, old_format)
        
        # Show cleanup summary
        _display_cleanup_summary(console, cleanup_results, config.general.icons)
        
        # Confirm cleanup if not dry run and not forced
        total_items = sum(len(items) for items in cleanup_results.values())
        if total_items == 0:
            feedback.info("Registry Clean", "No cleanup needed - registry is already clean!")
            return
        
        if not dry_run:
            if not force:
                if not click.confirm(f"Clean up {total_items} items from registry?"):
                    feedback.info("Cleanup Cancelled", "No changes were made")
                    return
            
            # Perform cleanup
            _perform_cleanup(registry_service, cleanup_results, feedback)
            
            feedback.success("Cleanup Complete", f"Cleaned up {total_items} items from registry")
        else:
            feedback.info("Dry Run Complete", f"Would clean up {total_items} items")
        
    except Exception as e:
        feedback.error("Cleanup Error", f"Failed to clean registry: {e}")
        raise click.Abort()


def _analyze_registry(registry_service, results: dict, check_orphaned: bool, check_invalid: bool, check_duplicates: bool, check_old_format: bool):
    """Analyze registry for cleanup opportunities."""
    
    if check_orphaned:
        results["orphaned"] = _find_orphaned_entries(registry_service)
    
    if check_invalid:
        results["invalid"] = _find_invalid_entries(registry_service)
    
    if check_duplicates:
        results["duplicates"] = _find_duplicate_entries(registry_service)
    
    if check_old_format:
        results["old_format"] = _find_old_format_entries(registry_service)


def _find_orphaned_entries(registry_service) -> list:
    """Find index entries that don't have corresponding media files."""
    orphaned = []
    
    try:
        index = registry_service._load_index()
        
        for entry_key, entry in index.media_index.items():
            media_file = registry_service._get_media_file_path(entry.media_id)
            if not media_file.exists():
                orphaned.append({
                    "type": "orphaned_index",
                    "id": entry.media_id,
                    "key": entry_key,
                    "reason": "Media file missing"
                })
    except Exception:
        pass
    
    return orphaned


def _find_invalid_entries(registry_service) -> list:
    """Find invalid or corrupted entries."""
    invalid = []
    
    try:
        # Check all media files
        for media_file in registry_service.media_registry_dir.iterdir():
            if not media_file.name.endswith('.json'):
                continue
            
            try:
                media_id = int(media_file.stem)
                record = registry_service.get_media_record(media_id)
                
                # Check for invalid record structure
                if not record or not record.media_item:
                    invalid.append({
                        "type": "invalid_record",
                        "id": media_id,
                        "file": media_file,
                        "reason": "Invalid record structure"
                    })
                elif not record.media_item.title or not record.media_item.title.english and not record.media_item.title.romaji:
                    invalid.append({
                        "type": "invalid_title",
                        "id": media_id,
                        "file": media_file,
                        "reason": "Missing or invalid title"
                    })
                    
            except (ValueError, Exception) as e:
                invalid.append({
                    "type": "corrupted_file",
                    "id": media_file.stem,
                    "file": media_file,
                    "reason": f"File corruption: {e}"
                })
    except Exception:
        pass
    
    return invalid


def _find_duplicate_entries(registry_service) -> list:
    """Find duplicate entries (same media ID appearing multiple times)."""
    duplicates = []
    seen_ids = set()
    
    try:
        index = registry_service._load_index()
        
        for entry_key, entry in index.media_index.items():
            if entry.media_id in seen_ids:
                duplicates.append({
                    "type": "duplicate_index",
                    "id": entry.media_id,
                    "key": entry_key,
                    "reason": "Duplicate media ID in index"
                })
            else:
                seen_ids.add(entry.media_id)
    except Exception:
        pass
    
    return duplicates


def _find_old_format_entries(registry_service) -> list:
    """Find entries from old registry format versions."""
    old_format = []
    
    try:
        index = registry_service._load_index()
        current_version = registry_service._index.version
        
        # Check for entries that might be from old formats
        # This is a placeholder - you'd implement specific checks based on your version history
        for media_file in registry_service.media_registry_dir.iterdir():
            if not media_file.name.endswith('.json'):
                continue
                
            try:
                import json
                with open(media_file, 'r') as f:
                    data = json.load(f)
                
                # Check for old format indicators
                if 'version' in data and data['version'] < current_version:
                    old_format.append({
                        "type": "old_version",
                        "id": media_file.stem,
                        "file": media_file,
                        "reason": f"Old format version {data.get('version')}"
                    })
            except Exception:
                pass
    except Exception:
        pass
    
    return old_format


def _display_cleanup_summary(console: Console, results: dict, icons: bool):
    """Display summary of cleanup opportunities."""
    
    table = Table(title=f"{'🧹 ' if icons else ''}Registry Cleanup Summary")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Count", style="magenta", justify="right")
    table.add_column("Description", style="white")
    
    categories = {
        "orphaned": "Orphaned Entries",
        "invalid": "Invalid Entries", 
        "duplicates": "Duplicate Entries",
        "old_format": "Old Format Entries"
    }
    
    for category, display_name in categories.items():
        count = len(results[category])
        if count > 0:
            # Get sample reasons
            reasons = set(item["reason"] for item in results[category][:3])
            description = "; ".join(list(reasons)[:2])
            if len(reasons) > 2:
                description += "..."
        else:
            description = "None found"
        
        table.add_row(display_name, str(count), description)
    
    console.print(table)
    console.print()
    
    # Show detailed breakdown if there are items to clean
    for category, items in results.items():
        if items:
            _display_category_details(console, category, items, icons)


def _display_category_details(console: Console, category: str, items: list, icons: bool):
    """Display detailed breakdown for a cleanup category."""
    
    category_names = {
        "orphaned": "🔗 Orphaned Entries" if icons else "Orphaned Entries",
        "invalid": "❌ Invalid Entries" if icons else "Invalid Entries",
        "duplicates": "👥 Duplicate Entries" if icons else "Duplicate Entries", 
        "old_format": "📼 Old Format Entries" if icons else "Old Format Entries"
    }
    
    table = Table(title=category_names.get(category, category.title()))
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Reason", style="yellow")
    
    for item in items[:10]:  # Show max 10 items
        table.add_row(
            str(item["id"]),
            item["type"],
            item["reason"]
        )
    
    if len(items) > 10:
        table.add_row("...", "...", f"And {len(items) - 10} more")
    
    console.print(table)
    console.print()


def _perform_cleanup(registry_service, results: dict, feedback):
    """Perform the actual cleanup operations."""
    
    cleaned_count = 0
    
    # Clean orphaned entries
    for item in results["orphaned"]:
        try:
            if item["type"] == "orphaned_index":
                index = registry_service._load_index()
                if item["key"] in index.media_index:
                    del index.media_index[item["key"]]
                    registry_service._save_index(index)
                    cleaned_count += 1
        except Exception as e:
            feedback.warning("Cleanup Error", f"Failed to clean orphaned entry {item['id']}: {e}")
    
    # Clean invalid entries
    for item in results["invalid"]:
        try:
            if "file" in item:
                item["file"].unlink()  # Delete the file
                cleaned_count += 1
            
            # Also remove from index if present
            index = registry_service._load_index()
            entry_key = f"{registry_service._media_api}_{item['id']}"
            if entry_key in index.media_index:
                del index.media_index[entry_key]
                registry_service._save_index(index)
                
        except Exception as e:
            feedback.warning("Cleanup Error", f"Failed to clean invalid entry {item['id']}: {e}")
    
    # Clean duplicates
    for item in results["duplicates"]:
        try:
            if item["type"] == "duplicate_index":
                index = registry_service._load_index()
                if item["key"] in index.media_index:
                    del index.media_index[item["key"]]
                    registry_service._save_index(index)
                    cleaned_count += 1
        except Exception as e:
            feedback.warning("Cleanup Error", f"Failed to clean duplicate entry {item['id']}: {e}")
    
    # Clean old format entries
    for item in results["old_format"]:
        try:
            if "file" in item:
                # You might want to migrate instead of delete
                # For now, we'll just remove old format files
                item["file"].unlink()
                cleaned_count += 1
        except Exception as e:
            feedback.warning("Cleanup Error", f"Failed to clean old format entry {item['id']}: {e}")
    
    feedback.info("Cleanup Results", f"Successfully cleaned {cleaned_count} items")
