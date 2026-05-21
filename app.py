from __future__ import annotations

import io
import zipfile
from urllib.parse import quote
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from batch_compress import BatchImage, compress_batch
from compress_core import (
    DEFAULT_COMPRESS_OPTIONS,
    CompressOptions,
    validate_options,
)
from job_store import InMemoryJobStore, JobFile, JobFileNotFound, JobNotFound


app = FastAPI(title="中文图片压缩工具", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

job_store = InMemoryJobStore()
_jobs = job_store._jobs


def _process_job(
    job_id: str,
    uploads: list[BatchImage],
    options: CompressOptions,
) -> None:
    job_store.mark_job_processing(job_id)

    for item in uploads:
        job_store.mark_file_processing(job_id, item.id)
        batch_result = next(compress_batch([item], options))
        if batch_result.result is not None:
            job_store.apply_success(job_id, batch_result.id, batch_result.result)
        else:
            job_store.apply_failure(
                job_id,
                batch_result.id,
                batch_result.original_size,
                batch_result.error or "处理失败",
            )

    job_store.mark_job_done(job_id)


@app.post("/api/jobs")
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    target_kb: int = Form(DEFAULT_COMPRESS_OPTIONS.target_kb),
    max_side: int = Form(DEFAULT_COMPRESS_OPTIONS.max_side),
    output_format: str = Form(DEFAULT_COMPRESS_OPTIONS.output_format),
    min_quality: int = Form(DEFAULT_COMPRESS_OPTIONS.min_quality),
    min_long_side: int | None = Form(None),
    scale_step: float = Form(DEFAULT_COMPRESS_OPTIONS.scale_step),
    grayscale: bool = Form(DEFAULT_COMPRESS_OPTIONS.grayscale),
    sharpness: float = Form(DEFAULT_COMPRESS_OPTIONS.sharpness),
    aggressive: bool = Form(DEFAULT_COMPRESS_OPTIONS.aggressive),
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

    uploads: list[BatchImage] = []
    job_files: list[JobFile] = []
    for upload in files:
        content = await upload.read()
        file_id = uuid4().hex
        filename = upload.filename or "image"
        uploads.append(BatchImage(id=file_id, filename=filename, data=content))
        job_files.append(
            JobFile(
                id=file_id,
                filename=filename,
                original_size=len(content),
            )
        )

    job_id = uuid4().hex
    job_store.create_job(job_id, job_files)

    background_tasks.add_task(_process_job, job_id, uploads, options)
    return job_store.serialize_job(job_id)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    try:
        return job_store.serialize_job(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc


@app.get("/api/jobs/{job_id}/files/{file_id}/download")
def download_file(job_id: str, file_id: str) -> Response:
    try:
        data, filename = job_store.get_download(job_id, file_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except JobFileNotFound as exc:
        raise HTTPException(status_code=404, detail="文件不存在") from exc

    if not data or not filename:
        raise HTTPException(status_code=404, detail="文件尚未成功处理")

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _attachment_header(filename)},
    )


@app.get("/api/jobs/{job_id}/download.zip")
def download_zip(job_id: str) -> StreamingResponse:
    try:
        successful_files = job_store.successful_files(job_id)
    except JobNotFound as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc

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
