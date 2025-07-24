"""
Registry import command - import registry data from various formats
"""

import json
import csv
from pathlib import Path
from datetime import datetime

import click

from .....core.config import AppConfig
from .....libs.media_api.types import UserMediaListStatus, MediaItem, MediaTitle
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(name="import", help="Import registry data from various formats")
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "input_format",
    type=click.Choice(["json", "csv", "xml", "auto"], case_sensitive=False),
    default="auto",
    help="Input format (auto-detect if not specified)"
)
@click.option(
    "--merge",
    is_flag=True,
    help="Merge with existing registry (default: replace)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be imported without making changes"
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force import even if format version doesn't match"
)
@click.option(
    "--backup",
    is_flag=True,
    help="Create backup before importing"
)
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API registry to import to"
)
@click.pass_obj
def import_(
    config: AppConfig,
    input_file: Path,
    input_format: str,
    merge: bool,
    dry_run: bool,
    force: bool,
    backup: bool,
    api: str
):
    """
    Import media registry data from various formats.
    
    Supports JSON, CSV, and XML formats exported by the export command
    or compatible third-party tools.
    """
    feedback = create_feedback_manager(config.general.icons)
    
    try:
        registry_service = MediaRegistryService(api, config.registry)
        
        # Create backup if requested
        if backup and not dry_run:
            _create_backup(registry_service, feedback)
        
        # Auto-detect format if needed
        if input_format == "auto":
            input_format = _detect_format(input_file)
            feedback.info("Format Detection", f"Detected format: {input_format.upper()}")
        
        # Parse input file
        import_data = _parse_input_file(input_file, input_format, feedback)
        
        # Validate import data
        _validate_import_data(import_data, force, feedback)
        
        # Import data
        _import_data(
            registry_service, import_data, merge, dry_run, feedback
        )
        
        if not dry_run:
            feedback.success(
                "Import Complete",
                f"Successfully imported {len(import_data.get('media', []))} media entries"
            )
        else:
            feedback.info(
                "Dry Run Complete",
                f"Would import {len(import_data.get('media', []))} media entries"
            )
        
    except Exception as e:
        feedback.error("Import Error", f"Failed to import registry: {e}")
        raise click.Abort()


def _create_backup(registry_service, feedback):
    """Create a backup before importing."""
    from .export import _prepare_export_data, _export_json
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"fastanime_registry_backup_{timestamp}.json")
    
    export_data = _prepare_export_data(registry_service, True, ())
    _export_json(export_data, backup_path, False, feedback)
    
    feedback.info("Backup Created", f"Registry backed up to {backup_path}")


def _detect_format(file_path: Path) -> str:
    """Auto-detect file format based on extension and content."""
    extension = file_path.suffix.lower()
    
    if extension in ['.json', '.gz']:
        return "json"
    elif extension == '.csv':
        return "csv"
    elif extension == '.xml':
        return "xml"
    
    # Try to detect by content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(100).strip()
            if content.startswith('{') or content.startswith('['):
                return "json"
            elif content.startswith('<?xml') or content.startswith('<'):
                return "xml"
            elif ',' in content:  # Very basic CSV detection
                return "csv"
    except:
        pass
    
    raise click.ClickException(f"Could not detect format for {file_path}")


def _parse_input_file(file_path: Path, format_type: str, feedback) -> dict:
    """Parse input file based on format."""
    if format_type == "json":
        return _parse_json(file_path)
    elif format_type == "csv":
        return _parse_csv(file_path)
    elif format_type == "xml":
        return _parse_xml(file_path)
    else:
        raise click.ClickException(f"Unsupported format: {format_type}")


def _parse_json(file_path: Path) -> dict:
    """Parse JSON input file."""
    try:
        if file_path.suffix.lower() == '.gz':
            import gzip
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                return json.load(f)
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON format: {e}")


def _parse_csv(file_path: Path) -> dict:
    """Parse CSV input file."""
    import_data = {
        "metadata": {
            "import_timestamp": datetime.now().isoformat(),
            "source_format": "csv",
        },
        "media": []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                media_data = {
                    "id": int(row["id"]) if row.get("id") else None,
                    "title": {
                        "english": row.get("title_english"),
                        "romaji": row.get("title_romaji"),
                        "native": row.get("title_native"),
                    },
                    "user_status": {
                        "status": row.get("status"),
                        "progress": int(row["progress"]) if row.get("progress") else None,
                        "score": float(row["score"]) if row.get("score") else None,
                        "last_watched": row.get("last_watched"),
                        "notes": row.get("notes"),
                    }
                }
                
                # Add metadata fields if present
                if "format" in row:
                    media_data.update({
                        "format": row.get("format"),
                        "episodes": int(row["episodes"]) if row.get("episodes") else None,
                        "duration": int(row["duration"]) if row.get("duration") else None,
                        "media_status": row.get("media_status"),
                        "start_date": row.get("start_date"),
                        "end_date": row.get("end_date"),
                        "average_score": float(row["average_score"]) if row.get("average_score") else None,
                        "popularity": int(row["popularity"]) if row.get("popularity") else None,
                        "genres": row.get("genres", "").split(",") if row.get("genres") else [],
                        "description": row.get("description"),
                    })
                
                import_data["media"].append(media_data)
    
    except (ValueError, KeyError) as e:
        raise click.ClickException(f"Invalid CSV format: {e}")
    
    return import_data


def _parse_xml(file_path: Path) -> dict:
    """Parse XML input file."""
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        raise click.ClickException("XML import requires Python's xml module")
    
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        import_data = {
            "metadata": {},
            "media": []
        }
        
        # Parse metadata
        metadata_elem = root.find("metadata")
        if metadata_elem is not None:
            for child in metadata_elem:
                import_data["metadata"][child.tag] = child.text
        
        # Parse media
        media_list_elem = root.find("media_list")
        if media_list_elem is not None:
            for media_elem in media_list_elem.findall("media"):
                media_data = {
                    "id": int(media_elem.get("id")),
                    "title": {},
                    "user_status": {}
                }
                
                # Parse titles
                titles_elem = media_elem.find("titles")
                if titles_elem is not None:
                    for title_elem in titles_elem:
                        media_data["title"][title_elem.tag] = title_elem.text
                
                # Parse user status
                status_elem = media_elem.find("user_status")
                if status_elem is not None:
                    for child in status_elem:
                        value = child.text
                        if child.tag in ["progress", "score"] and value:
                            try:
                                value = float(value) if child.tag == "score" else int(value)
                            except ValueError:
                                pass
                        media_data["user_status"][child.tag] = value
                
                # Parse other metadata
                for child in media_elem:
                    if child.tag not in ["titles", "user_status"]:
                        if child.tag in ["episodes", "duration", "popularity"]:
                            try:
                                media_data[child.tag] = int(child.text) if child.text else None
                            except ValueError:
                                media_data[child.tag] = child.text
                        elif child.tag == "average_score":
                            try:
                                media_data[child.tag] = float(child.text) if child.text else None
                            except ValueError:
                                media_data[child.tag] = child.text
                        else:
                            media_data[child.tag] = child.text
                
                import_data["media"].append(media_data)
    
    except ET.ParseError as e:
        raise click.ClickException(f"Invalid XML format: {e}")
    
    return import_data


def _validate_import_data(data: dict, force: bool, feedback):
    """Validate import data structure and compatibility."""
    if "media" not in data:
        raise click.ClickException("Import data missing 'media' section")
    
    if not isinstance(data["media"], list):
        raise click.ClickException("'media' section must be a list")
    
    # Check if any media entries exist
    if not data["media"]:
        feedback.warning("No Media", "Import file contains no media entries")
        return
    
    # Validate media entries
    required_fields = ["id", "title"]
    for i, media in enumerate(data["media"]):
        for field in required_fields:
            if field not in media:
                raise click.ClickException(f"Media entry {i} missing required field: {field}")
        
        if not isinstance(media.get("title"), dict):
            raise click.ClickException(f"Media entry {i} has invalid title format")
    
    feedback.info("Validation", f"Import data validated - {len(data['media'])} media entries")


def _import_data(registry_service, data: dict, merge: bool, dry_run: bool, feedback):
    """Import data into the registry."""
    from .....libs.media_api.types import MediaFormat, MediaGenre, MediaStatus, MediaType
    
    imported_count = 0
    updated_count = 0
    error_count = 0
    
    status_map = {
        "watching": UserMediaListStatus.WATCHING,
        "completed": UserMediaListStatus.COMPLETED,
        "planning": UserMediaListStatus.PLANNING,
        "dropped": UserMediaListStatus.DROPPED,
        "paused": UserMediaListStatus.PAUSED,
        "repeating": UserMediaListStatus.REPEATING,
    }
    
    for media_data in data["media"]:
        try:
            media_id = media_data["id"]
            if not media_id:
                error_count += 1
                continue
            
            title_data = media_data.get("title", {})
            title = MediaTitle(
                english=title_data.get("english") or "",
                romaji=title_data.get("romaji"),
                native=title_data.get("native"),
            )
            
            # Create minimal MediaItem for registry
            media_item = MediaItem(
                id=media_id,
                title=title,
                type=MediaType.ANIME,  # Default to anime
            )
            
            # Add additional metadata if available
            if "format" in media_data and media_data["format"]:
                try:
                    media_item.format = getattr(MediaFormat, media_data["format"])
                except (AttributeError, TypeError):
                    pass
            
            if "episodes" in media_data:
                media_item.episodes = media_data["episodes"]
            
            if "average_score" in media_data:
                media_item.average_score = media_data["average_score"]
            
            if dry_run:
                title_str = title.english or title.romaji or f"ID:{media_id}"
                feedback.info("Would import", title_str)
                imported_count += 1
                continue
            
            # Check if record exists
            existing_record = registry_service.get_media_record(media_id)
            if existing_record and not merge:
                # Skip if not merging
                continue
            elif existing_record:
                updated_count += 1
            else:
                imported_count += 1
            
            # Create or update record
            record = registry_service.get_or_create_record(media_item)
            registry_service.save_media_record(record)
            
            # Update user status if provided
            user_status = media_data.get("user_status", {})
            if user_status.get("status"):
                status_enum = status_map.get(user_status["status"].lower())
                if status_enum:
                    registry_service.update_media_index_entry(
                        media_id,
                        media_item=media_item,
                        status=status_enum,
                        progress=str(user_status.get("progress", 0)),
                        score=user_status.get("score"),
                        notes=user_status.get("notes"),
                    )
        
        except Exception as e:
            error_count += 1
            feedback.warning("Import Error", f"Failed to import media {media_data.get('id', 'unknown')}: {e}")
            continue
    
    if not dry_run:
        feedback.info(
            "Import Summary",
            f"Imported: {imported_count}, Updated: {updated_count}, Errors: {error_count}"
        )
