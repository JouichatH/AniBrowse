"""
Registry restore command - restore registry from backup files
"""

import shutil
import tarfile
from pathlib import Path
from datetime import datetime

import click

from .....core.config import AppConfig
from ....service.registry.service import MediaRegistryService
from ....utils.feedback import create_feedback_manager


@click.command(help="Restore registry from a backup file")
@click.argument("backup_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force restore even if current registry exists"
)
@click.option(
    "--backup-current",
    is_flag=True,
    help="Create backup of current registry before restoring"
)
@click.option(
    "--verify",
    is_flag=True,
    help="Verify backup integrity before restoring"
)
@click.option(
    "--api",
    default="anilist",
    type=click.Choice(["anilist"], case_sensitive=False),
    help="Media API registry to restore to"
)
@click.pass_obj
def restore(
    config: AppConfig,
    backup_file: Path,
    force: bool,
    backup_current: bool,
    verify: bool,
    api: str
):
    """
    Restore your media registry from a backup file.
    
    Can restore from tar or zip backups created by the backup command.
    Optionally creates a backup of the current registry before restoring.
    """
    feedback = create_feedback_manager(config.general.icons)
    
    try:
        # Detect backup format
        backup_format = _detect_backup_format(backup_file)
        feedback.info("Backup Format", f"Detected {backup_format.upper()} format")
        
        # Verify backup if requested
        if verify:
            if not _verify_backup(backup_file, backup_format, feedback):
                feedback.error("Verification Failed", "Backup file appears to be corrupted")
                raise click.Abort()
            feedback.success("Verification", "Backup file integrity verified")
        
        # Check if current registry exists
        registry_service = MediaRegistryService(api, config.registry)
        registry_exists = _check_registry_exists(registry_service)
        
        if registry_exists and not force:
            if not click.confirm("Current registry exists. Continue with restore?"):
                feedback.info("Restore Cancelled", "No changes were made")
                return
        
        # Create backup of current registry if requested
        if backup_current and registry_exists:
            _backup_current_registry(registry_service, api, feedback)
        
        # Show restore summary
        _show_restore_summary(backup_file, backup_format, feedback)
        
        # Perform restore
        _perform_restore(backup_file, backup_format, config, api, feedback)
        
        feedback.success("Restore Complete", "Registry has been successfully restored from backup")
        
        # Verify restored registry
        try:
            restored_service = MediaRegistryService(api, config.registry)
            stats = restored_service.get_registry_stats()
            feedback.info("Restored Registry", f"Contains {stats.get('total_media', 0)} media entries")
        except Exception as e:
            feedback.warning("Verification Warning", f"Could not verify restored registry: {e}")
        
    except Exception as e:
        feedback.error("Restore Error", f"Failed to restore registry: {e}")
        raise click.Abort()


def _detect_backup_format(backup_file: Path) -> str:
    """Detect backup file format."""
    if backup_file.suffix.lower() in ['.tar', '.gz']:
        return "tar"
    elif backup_file.suffix.lower() == '.zip':
        return "zip"
    elif backup_file.name.endswith('.tar.gz'):
        return "tar"
    else:
        # Try to detect by content
        try:
            with tarfile.open(backup_file, 'r:*'):
                return "tar"
        except:
            pass
        
        try:
            import zipfile
            with zipfile.ZipFile(backup_file, 'r'):
                return "zip"
        except:
            pass
    
    raise click.ClickException(f"Could not detect backup format for {backup_file}")


def _verify_backup(backup_file: Path, format_type: str, feedback) -> bool:
    """Verify backup file integrity."""
    try:
        if format_type == "tar":
            with tarfile.open(backup_file, 'r:*') as tar:
                # Check if essential files exist
                names = tar.getnames()
                has_registry = any('registry/' in name for name in names)
                has_index = any('index/' in name for name in names)
                has_metadata = 'backup_metadata.json' in names
                
                if not (has_registry and has_index):
                    return False
                
                # Try to read metadata if it exists
                if has_metadata:
                    try:
                        metadata_member = tar.getmember('backup_metadata.json')
                        metadata_file = tar.extractfile(metadata_member)
                        if metadata_file:
                            import json
                            metadata = json.load(metadata_file)
                            feedback.info("Backup Info", f"Created: {metadata.get('backup_timestamp', 'Unknown')}")
                            feedback.info("Backup Info", f"Total Media: {metadata.get('total_media', 'Unknown')}")
                    except:
                        pass
                
        else:  # zip
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zip_file:
                names = zip_file.namelist()
                has_registry = any('registry/' in name for name in names)
                has_index = any('index/' in name for name in names)
                has_metadata = 'backup_metadata.json' in names
                
                if not (has_registry and has_index):
                    return False
                
                # Try to read metadata
                if has_metadata:
                    try:
                        with zip_file.open('backup_metadata.json') as metadata_file:
                            import json
                            metadata = json.load(metadata_file)
                            feedback.info("Backup Info", f"Created: {metadata.get('backup_timestamp', 'Unknown')}")
                            feedback.info("Backup Info", f"Total Media: {metadata.get('total_media', 'Unknown')}")
                    except:
                        pass
        
        return True
        
    except Exception:
        return False


def _check_registry_exists(registry_service) -> bool:
    """Check if a registry already exists."""
    try:
        stats = registry_service.get_registry_stats()
        return stats.get('total_media', 0) > 0
    except:
        return False


def _backup_current_registry(registry_service, api: str, feedback):
    """Create backup of current registry before restoring."""
    from .backup import _create_tar_backup
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(f"fastanime_registry_pre_restore_{api}_{timestamp}.tar.gz")
    
    try:
        _create_tar_backup(registry_service, backup_path, True, False, feedback, api)
        feedback.info("Current Registry Backed Up", f"Saved to {backup_path}")
    except Exception as e:
        feedback.warning("Backup Warning", f"Failed to backup current registry: {e}")


def _show_restore_summary(backup_file: Path, format_type: str, feedback):
    """Show summary of what will be restored."""
    try:
        if format_type == "tar":
            with tarfile.open(backup_file, 'r:*') as tar:
                members = tar.getmembers()
                file_count = len([m for m in members if m.isfile()])
                
                # Count media files
                media_files = len([m for m in members if m.name.startswith('registry/') and m.name.endswith('.json')])
                
        else:  # zip
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zip_file:
                info_list = zip_file.infolist()
                file_count = len([info for info in info_list if not info.is_dir()])
                
                # Count media files
                media_files = len([info for info in info_list if info.filename.startswith('registry/') and info.filename.endswith('.json')])
        
        feedback.info("Restore Preview", f"Will restore {file_count} files")
        feedback.info("Media Records", f"Contains {media_files} media entries")
        
    except Exception as e:
        feedback.warning("Preview Error", f"Could not analyze backup: {e}")


def _perform_restore(backup_file: Path, format_type: str, config: AppConfig, api: str, feedback):
    """Perform the actual restore operation."""
    
    # Create temporary extraction directory
    temp_dir = Path(config.registry.media_dir.parent / "restore_temp")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Extract backup
        if format_type == "tar":
            with tarfile.open(backup_file, 'r:*') as tar:
                tar.extractall(temp_dir)
        else:  # zip
            import zipfile
            with zipfile.ZipFile(backup_file, 'r') as zip_file:
                zip_file.extractall(temp_dir)
        
        feedback.info("Extraction", "Backup extracted to temporary directory")
        
        # Remove existing registry if it exists
        registry_dir = config.registry.media_dir / api
        index_dir = config.registry.index_dir
        
        if registry_dir.exists():
            shutil.rmtree(registry_dir)
            feedback.info("Cleanup", "Removed existing registry data")
        
        if index_dir.exists():
            shutil.rmtree(index_dir)
            feedback.info("Cleanup", "Removed existing index data")
        
        # Move extracted files to proper locations
        extracted_registry = temp_dir / "registry" / api
        extracted_index = temp_dir / "index"
        
        if extracted_registry.exists():
            shutil.move(str(extracted_registry), str(registry_dir))
            feedback.info("Restore", "Registry data restored")
        
        if extracted_index.exists():
            shutil.move(str(extracted_index), str(index_dir))
            feedback.info("Restore", "Index data restored")
        
        # Restore cache if it exists
        extracted_cache = temp_dir / "cache"
        if extracted_cache.exists():
            cache_dir = config.registry.media_dir.parent / "cache"
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            shutil.move(str(extracted_cache), str(cache_dir))
            feedback.info("Restore", "Cache data restored")
        
    finally:
        # Clean up temporary directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            feedback.info("Cleanup", "Temporary files removed")
