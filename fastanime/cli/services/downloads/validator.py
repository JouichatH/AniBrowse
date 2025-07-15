"""
Download validation and integrity checking utilities.

This module provides functionality to validate downloaded files, verify
integrity, and repair corrupted download records.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import ValidationError

from ....core.constants import APP_DATA_DIR
from .manager import DownloadManager
from .models import DownloadIndex, MediaDownloadRecord

logger = logging.getLogger(__name__)


class DownloadValidator:
    """
    Validator for download records and file integrity using Pydantic models.
    
    Provides functionality to validate, repair, and maintain the integrity
    of download tracking data and associated files.
    """
    
    def __init__(self, download_manager: DownloadManager):
        self.download_manager = download_manager
        self.tracking_dir = APP_DATA_DIR / "downloads"
        self.media_dir = self.tracking_dir / "media"
    
    def validate_download_record(self, file_path: Path) -> Optional[MediaDownloadRecord]:
        """Load and validate a download record with Pydantic."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            record = MediaDownloadRecord.model_validate(data)
            logger.debug(f"Successfully validated download record: {file_path}")
            return record
            
        except ValidationError as e:
            logger.error(f"Invalid download record {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load download record {file_path}: {e}")
            return None
    
    def validate_all_records(self) -> Tuple[List[MediaDownloadRecord], List[Path]]:
        """Validate all download records and return valid records and invalid file paths."""
        valid_records = []
        invalid_files = []
        
        if not self.media_dir.exists():
            logger.warning("Media directory does not exist")
            return valid_records, invalid_files
        
        for record_file in self.media_dir.glob("*.json"):
            record = self.validate_download_record(record_file)
            if record:
                valid_records.append(record)
            else:
                invalid_files.append(record_file)
        
        logger.info(f"Validated {len(valid_records)} records, found {len(invalid_files)} invalid files")
        return valid_records, invalid_files
    
    def verify_file_integrity(self, record: MediaDownloadRecord) -> Dict[int, bool]:
        """Verify file integrity for all episodes in a download record."""
        integrity_results = {}
        
        for episode_num, episode_download in record.episodes.items():
            if episode_download.status != "completed":
                integrity_results[episode_num] = True  # Skip non-completed downloads
                continue
            
            # Check if file exists
            if not episode_download.file_path.exists():
                logger.warning(f"Missing file for episode {episode_num}: {episode_download.file_path}")
                integrity_results[episode_num] = False
                continue
            
            # Verify file size
            actual_size = episode_download.file_path.stat().st_size
            if actual_size != episode_download.file_size:
                logger.warning(f"Size mismatch for episode {episode_num}: expected {episode_download.file_size}, got {actual_size}")
                integrity_results[episode_num] = False
                continue
            
            # Verify checksum if available
            if episode_download.checksum:
                if not episode_download.verify_integrity():
                    logger.warning(f"Checksum mismatch for episode {episode_num}")
                    integrity_results[episode_num] = False
                    continue
            
            integrity_results[episode_num] = True
        
        return integrity_results
    
    def repair_download_record(self, record_file: Path) -> bool:
        """Attempt to repair a corrupted download record."""
        try:
            # Try to load raw data
            with open(record_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Attempt basic repairs
            repaired_data = self._attempt_basic_repairs(data)
            
            # Try to validate repaired data
            try:
                repaired_record = MediaDownloadRecord.model_validate(repaired_data)
                
                # Save repaired record
                self.download_manager.save_download_record(repaired_record)
                logger.info(f"Successfully repaired download record: {record_file}")
                return True
                
            except ValidationError as e:
                logger.error(f"Could not repair download record {record_file}: {e}")
                return False
        
        except Exception as e:
            logger.error(f"Failed to repair download record {record_file}: {e}")
            return False
    
    def _attempt_basic_repairs(self, data: Dict) -> Dict:
        """Attempt basic repairs on download record data."""
        repaired = data.copy()
        
        # Ensure required fields exist with defaults
        if "episodes" not in repaired:
            repaired["episodes"] = {}
        
        if "created_date" not in repaired:
            repaired["created_date"] = "2024-01-01T00:00:00"
        
        if "last_updated" not in repaired:
            repaired["last_updated"] = "2024-01-01T00:00:00"
        
        if "tags" not in repaired:
            repaired["tags"] = []
        
        if "preferred_quality" not in repaired:
            repaired["preferred_quality"] = "1080"
        
        if "auto_download_new" not in repaired:
            repaired["auto_download_new"] = False
        
        # Fix episodes data
        if isinstance(repaired["episodes"], dict):
            fixed_episodes = {}
            for ep_num, ep_data in repaired["episodes"].items():
                if isinstance(ep_data, dict):
                    # Ensure required episode fields
                    if "episode_number" not in ep_data:
                        ep_data["episode_number"] = int(ep_num) if ep_num.isdigit() else 1
                    
                    if "status" not in ep_data:
                        ep_data["status"] = "queued"
                    
                    if "download_progress" not in ep_data:
                        ep_data["download_progress"] = 0.0
                    
                    if "file_size" not in ep_data:
                        ep_data["file_size"] = 0
                    
                    if "subtitle_files" not in ep_data:
                        ep_data["subtitle_files"] = []
                    
                    fixed_episodes[ep_num] = ep_data
            
            repaired["episodes"] = fixed_episodes
        
        return repaired
    
    def rebuild_index_from_records(self) -> bool:
        """Rebuild the download index from individual record files."""
        try:
            valid_records, _ = self.validate_all_records()
            
            # Create new index
            new_index = DownloadIndex()
            
            # Add all valid records to index
            for record in valid_records:
                new_index.add_media_entry(record)
            
            # Save rebuilt index
            self.download_manager._save_index(new_index)
            
            logger.info(f"Rebuilt download index with {len(valid_records)} records")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rebuild index: {e}")
            return False
    
    def cleanup_orphaned_files(self) -> int:
        """Clean up orphaned files and inconsistent records."""
        cleanup_count = 0
        
        try:
            # Load current index
            index = self.download_manager._load_index()
            
            # Check for orphaned record files
            if self.media_dir.exists():
                for record_file in self.media_dir.glob("*.json"):
                    media_id = int(record_file.stem)
                    if media_id not in index.media_index:
                        # Check if record is valid
                        record = self.validate_download_record(record_file)
                        if record:
                            # Add to index
                            index.add_media_entry(record)
                            logger.info(f"Re-added orphaned record to index: {media_id}")
                        else:
                            # Remove invalid file
                            record_file.unlink()
                            cleanup_count += 1
                            logger.info(f"Removed invalid record file: {record_file}")
            
            # Check for missing record files
            missing_records = []
            for media_id, index_entry in index.media_index.items():
                if not index_entry.file_path.exists():
                    missing_records.append(media_id)
            
            # Remove missing records from index
            for media_id in missing_records:
                index.remove_media_entry(media_id)
                cleanup_count += 1
                logger.info(f"Removed missing record from index: {media_id}")
            
            # Save updated index
            if cleanup_count > 0:
                self.download_manager._save_index(index)
            
            return cleanup_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned files: {e}")
            return 0
    
    def validate_file_paths(self, record: MediaDownloadRecord) -> List[str]:
        """Validate file paths in a download record and return issues."""
        issues = []
        
        # Check download path
        if not record.download_path.is_absolute():
            issues.append(f"Download path is not absolute: {record.download_path}")
        
        # Check episode file paths
        for episode_num, episode_download in record.episodes.items():
            if not episode_download.file_path.is_absolute():
                issues.append(f"Episode {episode_num} file path is not absolute: {episode_download.file_path}")
            
            # Check if file exists for completed downloads
            if episode_download.status == "completed" and not episode_download.file_path.exists():
                issues.append(f"Episode {episode_num} file does not exist: {episode_download.file_path}")
            
            # Check subtitle files
            for subtitle_file in episode_download.subtitle_files:
                if not subtitle_file.exists():
                    issues.append(f"Episode {episode_num} subtitle file does not exist: {subtitle_file}")
        
        return issues
    
    def generate_validation_report(self) -> Dict:
        """Generate a comprehensive validation report."""
        report = {
            "timestamp": str(datetime.now()),
            "total_records": 0,
            "valid_records": 0,
            "invalid_records": 0,
            "integrity_issues": 0,
            "orphaned_files": 0,
            "path_issues": 0,
            "details": {
                "invalid_files": [],
                "integrity_failures": [],
                "path_issues": []
            }
        }
        
        try:
            # Validate all records
            valid_records, invalid_files = self.validate_all_records()
            
            report["total_records"] = len(valid_records) + len(invalid_files)
            report["valid_records"] = len(valid_records)
            report["invalid_records"] = len(invalid_files)
            report["details"]["invalid_files"] = [str(f) for f in invalid_files]
            
            # Check integrity and paths for valid records
            for record in valid_records:
                # Check file integrity
                integrity_results = self.verify_file_integrity(record)
                failed_episodes = [ep for ep, result in integrity_results.items() if not result]
                if failed_episodes:
                    report["integrity_issues"] += len(failed_episodes)
                    report["details"]["integrity_failures"].append({
                        "media_id": record.media_item.id,
                        "title": record.display_title,
                        "failed_episodes": failed_episodes
                    })
                
                # Check file paths
                path_issues = self.validate_file_paths(record)
                if path_issues:
                    report["path_issues"] += len(path_issues)
                    report["details"]["path_issues"].append({
                        "media_id": record.media_item.id,
                        "title": record.display_title,
                        "issues": path_issues
                    })
            
            # Check for orphaned files
            orphaned_count = self.cleanup_orphaned_files()
            report["orphaned_files"] = orphaned_count
            
        except Exception as e:
            logger.error(f"Failed to generate validation report: {e}")
            report["error"] = str(e)
        
        return report


def validate_downloads(download_manager: DownloadManager) -> Dict:
    """Convenience function to validate all downloads and return a report."""
    validator = DownloadValidator(download_manager)
    return validator.generate_validation_report()
