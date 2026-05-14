from __future__ import annotations

import io
import threading
import zipfile
from dataclasses import asdict, dataclass, field
from typing import Literal
from urllib.parse import quote
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from PIL import UnidentifiedImageError

from compress_core import (
    CompressOptions,
    CompressedResult,
    compress_image_bytes,
    validate_options,
)


JobStatus = Literal["queued", "processing", "done"]
FileStatus = Literal["queued", "processing", "done", "error"]


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


app = FastAPI(title="中文图片压缩工具", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_jobs: dict[str, Job] = {}
_lock = threading.Lock()


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


def _find_job(job_id: str) -> Job:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


def _find_job_file(job: Job, file_id: str) -> JobFile:
    for file in job.files:
        if file.id == file_id:
            return file
    raise HTTPException(status_code=404, detail="文件不存在")


def _apply_result(job_file: JobFile, result: CompressedResult) -> None:
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
    job_file.data = result.data


def _process_job(
    job_id: str,
    uploads: list[tuple[str, str, bytes]],
    options: CompressOptions,
) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "processing"

    for file_id, filename, content in uploads:
        with _lock:
            job = _jobs[job_id]
            job_file = _find_job_file(job, file_id)
            job_file.status = "processing"

        try:
            result = compress_image_bytes(content, filename, options)
        except UnidentifiedImageError:
            error = "无法识别图片格式"
        except ValueError as exc:
            error = str(exc)
        except Exception as exc:
            error = f"处理失败：{exc}"
        else:
            with _lock:
                _apply_result(job_file, result)
                job.completed += 1
            continue

        with _lock:
            job_file.status = "error"
            job_file.error = error
            job_file.original_size = len(content)
            job.failed += 1

    with _lock:
        job = _jobs[job_id]
        job.status = "done"


@app.post("/api/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    target_kb: int = Form(80),
    max_side: int = Form(1300),
    output_format: str = Form("jpg"),
    min_quality: int = Form(70),
    min_long_side: int | None = Form(None),
    scale_step: float = Form(0.92),
    grayscale: bool = Form(False),
    sharpness: float = Form(1.10),
    aggressive: bool = Form(False),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张图片")

    options = CompressOptions(
        target_kb=target_kb,
        max_side=max_side,
        min_quality=min_quality,
        min_long_side=min_long_side,
        scale_step=scale_step,
        output_format=output_format,
        grayscale=grayscale,
        sharpness=sharpness,
        aggressive=aggressive,
    )
    try:
        validate_options(options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uploads: list[tuple[str, str, bytes]] = []
    job_files: list[JobFile] = []
    for upload in files:
        content = await upload.read()
        file_id = uuid4().hex
        filename = upload.filename or "image"
        uploads.append((file_id, filename, content))
        job_files.append(
            JobFile(
                id=file_id,
                filename=filename,
                original_size=len(content),
            )
        )

    job_id = uuid4().hex
    job = Job(id=job_id, status="queued", files=job_files, total=len(job_files))
    with _lock:
        _jobs[job_id] = job

    background_tasks.add_task(_process_job, job_id, uploads, options)
    return _serialize_job(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with _lock:
        job = _find_job(job_id)
        return _serialize_job(job)


@app.get("/api/jobs/{job_id}/files/{file_id}/download")
def download_file(job_id: str, file_id: str) -> Response:
    with _lock:
        job = _find_job(job_id)
        job_file = _find_job_file(job, file_id)
        data = job_file.data
        filename = job_file.output_filename

    if not data or not filename:
        raise HTTPException(status_code=404, detail="文件尚未成功处理")

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _attachment_header(filename)},
    )


@app.get("/api/jobs/{job_id}/download.zip")
def download_zip(job_id: str) -> StreamingResponse:
    with _lock:
        job = _find_job(job_id)
        successful_files = [
            (file.output_filename, file.data)
            for file in job.files
            if file.status == "done" and file.output_filename and file.data
        ]

    if not successful_files:
        raise HTTPException(status_code=404, detail="暂无可下载的压缩结果")

    buffer = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, data in successful_files:
            arcname = _dedupe_name(filename, used_names)
            zf.writestr(arcname, data)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": _attachment_header("compressed-images.zip")},
    )


def _dedupe_name(filename: str, used_names: set[str]) -> str:
    if filename not in used_names:
        used_names.add(filename)
        return filename

    stem, dot, suffix = filename.rpartition(".")
    if not dot:
        stem = filename
        suffix = ""

    index = 2
    while True:
        candidate = f"{stem}_{index}.{suffix}" if suffix else f"{stem}_{index}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        index += 1


def _attachment_header(filename: str) -> str:
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download"
    return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'
