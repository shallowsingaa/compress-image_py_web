# 架构说明

## Overview

This project has three entry points over one compression core:

- Web API: `app.py` exposes FastAPI routes for batch jobs and downloads.
- Frontend: `web/src/main.tsx` uploads images, polls job status, and opens download routes.
- CLI: `main.py` calls the same core functions for single-file compression.

`compress_core.py` owns image processing. Keep new compression behavior in this module first, then expose it through the API, CLI, and frontend as needed.

## Data Flow

1. The frontend sends `multipart/form-data` to `POST /api/jobs` with one or more `files` fields and compression options.
2. `app.py` validates the form into `CompressOptions`, stores a `Job` with `JobFile` entries in `_jobs`, and schedules background processing.
3. `_process_job()` calls `compress_image_bytes()` for each upload.
4. `compress_core.py` opens the image with Pillow, applies EXIF transpose, constrains longest side, generates candidates across formats, quality levels, palette settings, and downscaled dimensions, then chooses the best candidate.
5. The frontend polls `GET /api/jobs/{job_id}` until the job is `done`.
6. Successful files can be downloaded individually or as `download.zip`.

## Compression Strategy

The core implementation is optimized for text-heavy images such as document photos, screenshots, forms, and certificates:

- `resize_to_max_side()` limits the initial longest side without upscaling.
- `generate_long_sides()` iteratively shrinks dimensions using `scale_step`.
- `make_candidates()` tries WebP, PNG, and JPEG variants depending on `output_format`.
- JPEG candidates include both 4:4:4 and 4:2:0 subsampling.
- PNG candidates include optimized true-color and palette versions.
- WebP candidates include lossless and quality-based output when Pillow supports WebP.
- `candidate_score()` prefers results that meet the target size, then larger dimensions, higher quality, smaller size, and preferred formats.

The target size is best-effort. If no candidate fits under `target_kb`, the API and CLI return the best available candidate with `success=false`.

## State Model

Jobs are stored in the module-level `_jobs` dictionary in `app.py`.

- Job statuses: `queued`, `processing`, `done`.
- File statuses: `queued`, `processing`, `done`, `error`.
- Compressed bytes are kept in memory on each `JobFile`.
- There is no persistent storage, cleanup worker, auth, or multi-process coordination.

This means old jobs disappear when the process restarts. Multiple Uvicorn workers would each have their own independent job store, so run a single backend process unless the storage model is changed.

## Frontend Contract

The frontend defines API response types directly in `web/src/main.tsx`. Backend response fields should remain stable:

- `id`
- `status`
- `total`
- `completed`
- `failed`
- `files`
- per-file metadata such as `output_filename`, `output_size`, `output_format`, `success`, `error`, and `compression_ratio`

`VITE_API_BASE_URL` is optional. When it is unset, browser requests are same-origin relative URLs such as `/api/jobs`.

## Known Limits

- Uploaded files and compressed outputs are held fully in memory.
- Any origin is currently allowed by CORS.
- Background jobs run inside the FastAPI process rather than through a durable queue.
- There is no file expiry API because there is no persistent file store.
