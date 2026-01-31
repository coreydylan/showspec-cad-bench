"""
In-memory job store for DXF/DWG import jobs.

Provides thread-safe storage and retrieval of import jobs.
In production, this could be replaced with Redis or a database.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Optional
from threading import Lock

from api.models import (
    DXFImportJob,
    DXFImportJobStatus,
    CADLayer,
)


class JobStore:
    """Thread-safe in-memory job store."""

    def __init__(self):
        self._jobs: dict[str, DXFImportJob] = {}
        self._file_paths: dict[str, str] = {}  # job_id -> temp file path
        self._lock = Lock()

    def create_job(
        self,
        file_name: str,
        file_size: int,
        file_format: str,
        temp_file_path: str,
    ) -> DXFImportJob:
        """Create a new import job."""
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        job = DXFImportJob(
            id=job_id,
            status=DXFImportJobStatus.PENDING,
            progress=0,
            message="Job created, waiting to start processing",
            createdAt=now,
            updatedAt=now,
            fileName=file_name,
            fileSize=file_size,
            fileFormat=file_format,
            layers=None,
            previewUrl=None,
            error=None,
        )

        with self._lock:
            self._jobs[job_id] = job
            self._file_paths[job_id] = temp_file_path

        return job

    def get_job(self, job_id: str) -> Optional[DXFImportJob]:
        """Get a job by ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def get_file_path(self, job_id: str) -> Optional[str]:
        """Get the temp file path for a job."""
        with self._lock:
            return self._file_paths.get(job_id)

    def update_job(
        self,
        job_id: str,
        status: Optional[DXFImportJobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        layers: Optional[list[CADLayer]] = None,
        preview_url: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[DXFImportJob]:
        """Update a job's status and data."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None

            # Create updated job
            update_data = {}
            if status is not None:
                update_data["status"] = status
            if progress is not None:
                update_data["progress"] = progress
            if message is not None:
                update_data["message"] = message
            if layers is not None:
                update_data["layers"] = layers
            if preview_url is not None:
                update_data["previewUrl"] = preview_url
            if error is not None:
                update_data["error"] = error

            update_data["updatedAt"] = datetime.now(timezone.utc).isoformat()

            # Update job in place
            updated_job = job.model_copy(update=update_data)
            self._jobs[job_id] = updated_job

            return updated_job

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its associated file path."""
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                if job_id in self._file_paths:
                    del self._file_paths[job_id]
                return True
            return False

    def list_jobs(self) -> list[DXFImportJob]:
        """List all jobs."""
        with self._lock:
            return list(self._jobs.values())


# Global job store instance
_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    """Get the global job store instance."""
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
