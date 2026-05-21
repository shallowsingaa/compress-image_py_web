from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field
from typing import Literal

from compress_core import CompressedResult


JobStatus = Literal["queued", "processing", "done"]
FileStatus = Literal["queued", "processing", "done", "error"]


class JobNotFound(KeyError):
    pass


class JobFileNotFound(KeyError):
    pass


@dataclass
class JobFile:
    id: str
    filename: str
    status: FileStatus = "queued"
    original_size: int = 0
    original_width: int | None = None
    original_height: int | None = None
    output_filename: str | None = None
    output_size: int | None = None
    output_width: int | None = None
    output_height: int | None = None
    output_format: str | None = None
    note: str | None = None
    success: bool | None = None
    error: str | None = None
    data: bytes | None = field(default=None, repr=False)


@dataclass
class Job:
    id: str
    status: JobStatus
    files: list[JobFile]
    total: int
    completed: int = 0
    failed: int = 0


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, job_id: str, files: list[JobFile]) -> Job:
        job = Job(id=job_id, status="queued", files=files, total=len(files))
        with self._lock:
            self._jobs[job_id] = job
        return job

    def mark_job_processing(self, job_id: str) -> None:
        with self._lock:
            self._find_job(job_id).status = "processing"

    def mark_file_processing(self, job_id: str, file_id: str) -> None:
        with self._lock:
            self._find_file(self._find_job(job_id), file_id).status = "processing"

    def apply_success(self, job_id: str, file_id: str, result: CompressedResult) -> None:
        with self._lock:
            job = self._find_job(job_id)
            job_file = self._find_file(job, file_id)
            job_file.status = "done"
            job_file.original_size = result.original_size
            job_file.original_width = result.original_width
            job_file.original_height = result.original_height
            job_file.output_filename = result.output_filename
            job_file.output_size = result.output_size
            job_file.output_width = result.output_width
            job_file.output_height = result.output_height
            job_file.output_format = result.fmt
            job_file.note = result.note
            job_file.success = result.success
            job_file.error = None
            job_file.data = result.data
            job.completed += 1

    def apply_failure(self, job_id: str, file_id: str, original_size: int, error: str) -> None:
        with self._lock:
            job = self._find_job(job_id)
            job_file = self._find_file(job, file_id)
            job_file.status = "error"
            job_file.error = error
            job_file.original_size = original_size
            job.failed += 1

    def mark_job_done(self, job_id: str) -> None:
        with self._lock:
            self._find_job(job_id).status = "done"

    def serialize_job(self, job_id: str) -> dict:
        with self._lock:
            return _serialize_job(self._find_job(job_id))

    def get_download(self, job_id: str, file_id: str) -> tuple[bytes | None, str | None]:
        with self._lock:
            job_file = self._find_file(self._find_job(job_id), file_id)
            return job_file.data, job_file.output_filename

    def successful_files(self, job_id: str) -> list[tuple[str, bytes]]:
        with self._lock:
            job = self._find_job(job_id)
            return [
                (file.output_filename, file.data)
                for file in job.files
                if file.status == "done" and file.output_filename and file.data
            ]

    def _find_job(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFound(job_id)
        return job

    def _find_file(self, job: Job, file_id: str) -> JobFile:
        for file in job.files:
            if file.id == file_id:
                return file
        raise JobFileNotFound(file_id)


def _serialize_file(job_file: JobFile) -> dict:
    payload = asdict(job_file)
    payload.pop("data", None)
    if payload["original_size"] and payload["output_size"]:
        saved = max(0, payload["original_size"] - payload["output_size"])
        payload["compression_ratio"] = round(saved / payload["original_size"], 4)
    else:
        payload["compression_ratio"] = None
    return payload


def _serialize_job(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "total": job.total,
        "completed": job.completed,
        "failed": job.failed,
        "files": [_serialize_file(file) for file in job.files],
    }
