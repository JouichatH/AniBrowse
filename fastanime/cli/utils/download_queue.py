"""
Download queue management system for FastAnime.
Handles queuing, processing, and tracking of download jobs.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from ...core.constants import APP_DATA_DIR

logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    """Status of a download job."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DownloadJob(BaseModel):
    """Represents a single download job in the queue."""
    id: str = Field(description="Unique identifier for the job")
    anime_title: str = Field(description="Title of the anime")
    episode: str = Field(description="Episode number or identifier")
    media_id: Optional[int] = Field(default=None, description="AniList media ID if available")
    provider_id: Optional[str] = Field(default=None, description="Provider-specific anime ID")
    quality: str = Field(default="1080", description="Preferred quality")
    translation_type: str = Field(default="sub", description="sub or dub")
    priority: int = Field(default=5, description="Priority level (1-10, lower is higher priority)")
    status: DownloadStatus = Field(default=DownloadStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0)
    auto_added: bool = Field(default=False, description="Whether this was auto-added by the service")


class DownloadQueue(BaseModel):
    """Container for all download jobs."""
    jobs: Dict[str, DownloadJob] = Field(default_factory=dict)
    max_concurrent: int = Field(default=3, description="Maximum concurrent downloads")
    auto_retry_count: int = Field(default=3, description="Maximum retry attempts")


class QueueManager:
    """Manages the download queue operations."""
    
    def __init__(self, queue_file_path: Optional[Path] = None):
        self.queue_file_path = queue_file_path or APP_DATA_DIR / "download_queue.json"
        self._queue: Optional[DownloadQueue] = None
        
    def _load_queue(self) -> DownloadQueue:
        """Load queue from file."""
        if self.queue_file_path.exists():
            try:
                with open(self.queue_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return DownloadQueue.model_validate(data)
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to load queue from {self.queue_file_path}: {e}")
                return DownloadQueue()
        return DownloadQueue()
    
    def _save_queue(self, queue: DownloadQueue) -> bool:
        """Save queue to file."""
        try:
            with open(self.queue_file_path, 'w', encoding='utf-8') as f:
                json.dump(queue.model_dump(), f, indent=2, default=str)
            return True
        except Exception as e:
            logger.error(f"Failed to save queue to {self.queue_file_path}: {e}")
            return False
    
    @property
    def queue(self) -> DownloadQueue:
        """Get the current queue, loading it if necessary."""
        if self._queue is None:
            self._queue = self._load_queue()
        return self._queue
    
    def add_job(self, job: DownloadJob) -> bool:
        """Add a new download job to the queue."""
        try:
            self.queue.jobs[job.id] = job
            success = self._save_queue(self.queue)
            if success:
                logger.info(f"Added download job: {job.anime_title} Episode {job.episode}")
            return success
        except Exception as e:
            logger.error(f"Failed to add job to queue: {e}")
            return False
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the queue."""
        try:
            if job_id in self.queue.jobs:
                job = self.queue.jobs.pop(job_id)
                success = self._save_queue(self.queue)
                if success:
                    logger.info(f"Removed download job: {job.anime_title} Episode {job.episode}")
                return success
            return False
        except Exception as e:
            logger.error(f"Failed to remove job from queue: {e}")
            return False
    
    def update_job_status(self, job_id: str, status: DownloadStatus, error_message: Optional[str] = None) -> bool:
        """Update the status of a job."""
        try:
            if job_id in self.queue.jobs:
                job = self.queue.jobs[job_id]
                job.status = status
                if error_message:
                    job.error_message = error_message
                
                if status == DownloadStatus.DOWNLOADING:
                    job.started_at = datetime.now()
                elif status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED):
                    job.completed_at = datetime.now()
                
                return self._save_queue(self.queue)
            return False
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            return False
    
    def get_pending_jobs(self, limit: Optional[int] = None) -> List[DownloadJob]:
        """Get pending jobs sorted by priority and creation time."""
        pending = [
            job for job in self.queue.jobs.values() 
            if job.status == DownloadStatus.PENDING
        ]
        # Sort by priority (lower number = higher priority), then by creation time
        pending.sort(key=lambda x: (x.priority, x.created_at))
        
        if limit:
            return pending[:limit]
        return pending
    
    def get_active_jobs(self) -> List[DownloadJob]:
        """Get currently downloading jobs."""
        return [
            job for job in self.queue.jobs.values() 
            if job.status == DownloadStatus.DOWNLOADING
        ]
    
    def get_job_by_id(self, job_id: str) -> Optional[DownloadJob]:
        """Get a specific job by ID."""
        return self.queue.jobs.get(job_id)
    
    def get_all_jobs(self) -> List[DownloadJob]:
        """Get all jobs."""
        return list(self.queue.jobs.values())
    
    def clean_completed_jobs(self, max_age_days: int = 7) -> int:
        """Remove completed jobs older than specified days."""
        cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - max_age_days)
        
        jobs_to_remove = []
        for job_id, job in self.queue.jobs.items():
            if (job.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED) 
                and job.completed_at and job.completed_at < cutoff_date):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.queue.jobs[job_id]
        
        if jobs_to_remove:
            self._save_queue(self.queue)
            logger.info(f"Cleaned {len(jobs_to_remove)} old completed jobs")
        
        return len(jobs_to_remove)
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get statistics about the queue."""
        stats = {
            "total": len(self.queue.jobs),
            "pending": 0,
            "downloading": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self.queue.jobs.values():
            if job.status == DownloadStatus.PENDING:
                stats["pending"] += 1
            elif job.status == DownloadStatus.DOWNLOADING:
                stats["downloading"] += 1
            elif job.status == DownloadStatus.COMPLETED:
                stats["completed"] += 1
            elif job.status == DownloadStatus.FAILED:
                stats["failed"] += 1
            elif job.status == DownloadStatus.CANCELLED:
                stats["cancelled"] += 1
        
        return stats
