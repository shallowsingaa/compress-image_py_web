# 架构说明

## Overview

This project has three entry points over one compression core:

- Web API: `app.py` exposes FastAPI routes for batch jobs and downloads.
- Frontend: `web/src/main.tsx` composes the UI; `web/src/api.ts`, `web/src/clipboard.ts`, `web/src/device.ts`, `web/src/format.ts`, and `web/src/types.ts` hold request, browser workflow, formatting, and response-type helpers.
- CLI: `main.py` calls the same core functions for single-file compression and Windows clipboard batches.
- npm package: `package/` wraps the CLI as `compress-img-cli`, installing the `compress-img` command that launches a platform-specific PyInstaller binary.

`compress_core.py` owns image processing. `batch_compress.py` owns per-file batch semantics over that core. Keep new compression behavior in the core first, then expose it through the batch flow, API, CLI, and frontend as needed.

## Data Flow

1. The frontend sends `multipart/form-data` to `POST /api/jobs` with one or more `files` fields and compression options.
2. `app.py` validates the form into `CompressOptions`, stores a `Job` with `JobFile` entries through `job_store.py`, and schedules background processing.
3. `_process_job()` passes each upload through `batch_compress.py`, which calls `compress_image_bytes()` and returns either a compressed result or a per-file error.
4. `compress_core.py` opens the image with Pillow, applies EXIF transpose, constrains longest side, generates candidates across formats, quality levels, palette settings, and downscaled dimensions, then chooses the best candidate.
5. The frontend polls `GET /api/jobs/{job_id}` until the job is `done`.
6. Successful files can be downloaded individually or as `download.zip`.

CLI file-path flow:

1. `main.py` builds `CompressOptions` from argparse values.
2. `compress_image_file()` compresses the input path and writes the output path chosen by `compress_core.py`.
3. The CLI prints the same result metadata returned by the shared core.

CLI Windows clipboard flow:

1. `main.py --clipboard` calls `clipboard_io.read_clipboard_images()`.
2. `clipboard_io.py` reads copied image files from `CF_HDROP`, or screenshot bitmap data from `CF_DIB`.
3. Each clipboard image is compressed through `batch_compress.py`.
4. Outputs are saved under a `clipboard/` subdirectory and copied back to the Windows clipboard as an `CF_HDROP` file list.

npm package flow:

1. Maintainers build binaries with `npm run build:win` on Windows and `npm run build:linux` on Linux.
2. Build scripts run PyInstaller specs from `scripts/build/` and copy outputs into `package/resources/win/` or `package/resources/linux/`.
3. `package/bin/compress-image.js` is installed by npm as the `compress-img` command.
4. At runtime, the Node launcher selects the current platform with `os.platform()` and spawns the bundled binary with the original CLI arguments.
5. `package/bin/verify-platform.js` runs at postinstall and warns when the current platform binary is missing.

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

Jobs are stored by `job_store.py` in an in-memory dictionary exposed to `app.py`.

- Job statuses: `queued`, `processing`, `done`.
- File statuses: `queued`, `processing`, `done`, `error`.
- Compressed bytes are kept in memory on each `JobFile`.
- There is no persistent storage, cleanup worker, auth, or multi-process coordination.

This means old jobs disappear when the process restarts. Multiple Uvicorn workers would each have their own independent job store, so run a single backend process unless the storage model is changed.

## Frontend Contract

The frontend defines API response types in `web/src/types.ts`. Backend response fields should remain stable:

- `id`
- `status`
- `total`
- `completed`
- `failed`
- `files`
- per-file metadata such as `output_filename`, `output_size`, `output_format`, `success`, `error`, and `compression_ratio`

`VITE_API_BASE_URL` is optional. When it is unset, browser requests are same-origin relative URLs such as `/api/jobs`.

## npm Distribution Contract

The published npm package is rooted at `package/`:

- Package name: `compress-img-cli`
- Installed command: `compress-img`
- Supported npm `os`: `win32`, `linux`
- Source launcher: `package/bin/compress-image.js`
- Windows binary: `package/resources/win/compress-image.exe`
- Linux binary: `package/resources/linux/compress-image`

`package/resources/` is ignored by git. It must exist before `npm publish`, and `npm pack --dry-run` is the release gate for confirming that both binaries and package docs are included.

## Known Limits

- Uploaded files and compressed outputs are held fully in memory.
- Any origin is currently allowed by CORS.
- Background jobs run inside the FastAPI process rather than through a durable queue.
- There is no file expiry API because there is no persistent file store.
- CLI clipboard mode is Windows-only and depends on the native clipboard APIs exposed through `ctypes`.
- npm distribution does not currently ship a macOS binary.
