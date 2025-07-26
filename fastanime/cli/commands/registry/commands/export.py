"""
Registry export command - export registry data to various formats
"""

import json
import csv
from pathlib import Path
from datetime import datetime

import click

from .....core.config import AppConfig
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(help="Export registry data to various formats")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv", "xml"], case_sensitive=False),
    default="json",
    help="Export format",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file path (auto-generated if not specified)",
)
@click.option(
    "--include-metadata", is_flag=True, help="Include detailed media metadata in export"
)
@click.option(
    "--status",
    multiple=True,
    type=click.Choice(
        ["watching", "completed", "planning", "dropped", "paused", "repeating"],
        case_sensitive=False,
    ),
    help="Only export specific status lists",
)
@click.option("--compress", is_flag=True, help="Compress the output file")
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API registry to export",
)
@click.pass_obj
def export(
    config: AppConfig,
    output_format: str,
    output: str | None,
    include_metadata: bool,
    status: tuple[str, ...],
    compress: bool,
    api: str,
):
    """
    Export your local media registry to various formats.

    Supports JSON, CSV, and XML formats. Can optionally include
    detailed metadata and compress the output.
    """
    feedback = create_feedback_manager(config.general.icons)

    try:
        registry_service = MediaRegistryService(api, config.registry)

        # Generate output filename if not specified
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = output_format.lower()
            if compress:
                extension += ".gz"
            output = f"fastanime_registry_{api}_{timestamp}.{extension}"

        output_path = Path(output)

        # Get export data
        export_data = _prepare_export_data(registry_service, include_metadata, status)

        # Export based on format
        if output_format.lower() == "json":
            _export_json(export_data, output_path, compress, feedback)
        elif output_format.lower() == "csv":
            _export_csv(export_data, output_path, compress, feedback)
        elif output_format.lower() == "xml":
            _export_xml(export_data, output_path, compress, feedback)

        feedback.success(
            "Export Complete",
            f"Registry exported to {output_path} ({_format_file_size(output_path)})",
        )

    except Exception as e:
        feedback.error("Export Error", f"Failed to export registry: {e}")
        raise click.Abort()


def _prepare_export_data(
    registry_service, include_metadata: bool, status_filter: tuple[str, ...]
) -> dict:
    """Prepare data for export based on options."""

    # Convert status filter to enums
    from .....libs.media_api.types import UserMediaListStatus

    status_map = {
        "watching": UserMediaListStatus.WATCHING,
        "completed": UserMediaListStatus.COMPLETED,
        "planning": UserMediaListStatus.PLANNING,
        "dropped": UserMediaListStatus.DROPPED,
        "paused": UserMediaListStatus.PAUSED,
        "repeating": UserMediaListStatus.REPEATING,
    }

    status_enums = [status_map[s] for s in status_filter] if status_filter else None

    export_data = {
        "metadata": {
            "export_timestamp": datetime.now().isoformat(),
            "registry_version": registry_service._load_index().version,
            "include_metadata": include_metadata,
            "filtered_status": list(status_filter) if status_filter else None,
        },
        "statistics": registry_service.get_registry_stats(),
        "media": [],
    }

    # Get all records and filter by status if specified
    all_records = registry_service.get_all_media_records()

    for record in all_records:
        index_entry = registry_service.get_media_index_entry(record.media_item.id)

        # Skip if status filter is specified and doesn't match
        if status_enums and (not index_entry or index_entry.status not in status_enums):
            continue

        media_data = {
            "id": record.media_item.id,
            "title": {
                "english": record.media_item.title.english,
                "romaji": record.media_item.title.romaji,
                "native": record.media_item.title.native,
            },
            "user_status": {
                "status": index_entry.status.value
                if index_entry and index_entry.status
                else None,
                "progress": index_entry.progress if index_entry else None,
                "score": index_entry.score if index_entry else None,
                "last_watched": index_entry.last_watched.isoformat()
                if index_entry and index_entry.last_watched
                else None,
                "notes": index_entry.notes if index_entry else None,
            },
        }

        if include_metadata:
            media_data.update(
                {
                    "format": record.media_item.format.value
                    if record.media_item.format
                    else None,
                    "episodes": record.media_item.episodes,
                    "duration": record.media_item.duration,
                    "status": record.media_item.status.value
                    if record.media_item.status
                    else None,
                    "start_date": record.media_item.start_date.isoformat()
                    if record.media_item.start_date
                    else None,
                    "end_date": record.media_item.end_date.isoformat()
                    if record.media_item.end_date
                    else None,
                    "average_score": record.media_item.average_score,
                    "popularity": record.media_item.popularity,
                    "genres": [genre.value for genre in record.media_item.genres],
                    "tags": [
                        {"name": tag.name.value, "rank": tag.rank}
                        for tag in record.media_item.tags
                    ],
                    "studios": [
                        studio.name
                        for studio in record.media_item.studios
                        if studio.name
                    ],
                    "description": record.media_item.description,
                    "cover_image": {
                        "large": record.media_item.cover_image.large
                        if record.media_item.cover_image
                        else None,
                        "medium": record.media_item.cover_image.medium
                        if record.media_item.cover_image
                        else None,
                    }
                    if record.media_item.cover_image
                    else None,
                }
            )

        export_data["media"].append(media_data)

    return export_data


def _export_json(data: dict, output_path: Path, compress: bool, feedback):
    """Export data to JSON format."""
    if compress:
        import gzip

        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def _export_csv(data: dict, output_path: Path, compress: bool, feedback):
    """Export data to CSV format."""
    # Flatten media data for CSV
    fieldnames = [
        "id",
        "title_english",
        "title_romaji",
        "title_native",
        "status",
        "progress",
        "score",
        "last_watched",
        "notes",
    ]

    # Add metadata fields if included
    if data["metadata"]["include_metadata"]:
        fieldnames.extend(
            [
                "format",
                "episodes",
                "duration",
                "media_status",
                "start_date",
                "end_date",
                "average_score",
                "popularity",
                "genres",
                "description",
            ]
        )

    def write_csv(file_obj):
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()

        for media in data["media"]:
            row = {
                "id": media["id"],
                "title_english": media["title"]["english"],
                "title_romaji": media["title"]["romaji"],
                "title_native": media["title"]["native"],
                "status": media["user_status"]["status"],
                "progress": media["user_status"]["progress"],
                "score": media["user_status"]["score"],
                "last_watched": media["user_status"]["last_watched"],
                "notes": media["user_status"]["notes"],
            }

            if data["metadata"]["include_metadata"]:
                row.update(
                    {
                        "format": media.get("format"),
                        "episodes": media.get("episodes"),
                        "duration": media.get("duration"),
                        "media_status": media.get("status"),
                        "start_date": media.get("start_date"),
                        "end_date": media.get("end_date"),
                        "average_score": media.get("average_score"),
                        "popularity": media.get("popularity"),
                        "genres": ",".join(media.get("genres", [])),
                        "description": media.get("description"),
                    }
                )

            writer.writerow(row)

    if compress:
        import gzip

        with gzip.open(output_path, "wt", encoding="utf-8", newline="") as f:
            write_csv(f)
    else:
        with open(output_path, "w", encoding="utf-8", newline="") as f:
            write_csv(f)


def _export_xml(data: dict, output_path: Path, compress: bool, feedback):
    """Export data to XML format."""
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        feedback.error("XML Export Error", "XML export requires Python's xml module")
        raise click.Abort()

    root = ET.Element("fastanime_registry")

    # Add metadata
    metadata_elem = ET.SubElement(root, "metadata")
    for key, value in data["metadata"].items():
        if value is not None:
            elem = ET.SubElement(metadata_elem, key)
            elem.text = str(value)

    # Add statistics
    stats_elem = ET.SubElement(root, "statistics")
    for key, value in data["statistics"].items():
        if value is not None:
            elem = ET.SubElement(stats_elem, key)
            elem.text = str(value)

    # Add media
    media_list_elem = ET.SubElement(root, "media_list")
    for media in data["media"]:
        media_elem = ET.SubElement(media_list_elem, "media")
        media_elem.set("id", str(media["id"]))

        # Add titles
        titles_elem = ET.SubElement(media_elem, "titles")
        for title_type, title_value in media["title"].items():
            if title_value:
                title_elem = ET.SubElement(titles_elem, title_type)
                title_elem.text = title_value

        # Add user status
        status_elem = ET.SubElement(media_elem, "user_status")
        for key, value in media["user_status"].items():
            if value is not None:
                elem = ET.SubElement(status_elem, key)
                elem.text = str(value)

        # Add metadata if included
        if data["metadata"]["include_metadata"]:
            for key, value in media.items():
                if key not in ["id", "title", "user_status"] and value is not None:
                    if isinstance(value, list):
                        list_elem = ET.SubElement(media_elem, key)
                        for item in value:
                            item_elem = ET.SubElement(list_elem, "item")
                            item_elem.text = str(item)
                    elif isinstance(value, dict):
                        dict_elem = ET.SubElement(media_elem, key)
                        for sub_key, sub_value in value.items():
                            if sub_value is not None:
                                sub_elem = ET.SubElement(dict_elem, sub_key)
                                sub_elem.text = str(sub_value)
                    else:
                        elem = ET.SubElement(media_elem, key)
                        elem.text = str(value)

    # Write XML
    tree = ET.ElementTree(root)
    if compress:
        import gzip

        with gzip.open(output_path, "wb") as f:
            tree.write(f, encoding="utf-8", xml_declaration=True)
    else:
        tree.write(output_path, encoding="utf-8", xml_declaration=True)


def _format_file_size(file_path: Path) -> str:
    """Format file size in human-readable format."""
    try:
        size = file_path.stat().st_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Unknown size"
