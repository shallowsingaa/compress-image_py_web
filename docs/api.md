# API 参考

Base URL depends on deployment:

- Local backend: `http://127.0.0.1:8793`
- Frontend same-origin deployment: `/api` must be reverse-proxied to the backend
- Custom frontend build: set `VITE_API_BASE_URL` before `npm run build`

## Create Job

`POST /api/jobs`

Content type: `multipart/form-data`

File field:

- `files`: one or more uploaded image files

Form fields:

| Field | Type | Default | Notes |
| --- | --- | --- | --- |
| `target_kb` | integer | `80` | Must be positive |
| `max_side` | integer | `1300` | Longest side cap; no upscaling |
| `output_format` | string | `jpg` | `jpg`, `jpeg`, `png`, `webp`, or `auto` |
| `min_quality` | integer | `70` | Positive; internally capped at `95` |
| `min_long_side` | integer or empty | empty | Optional lower bound for iterative resizing |
| `scale_step` | float | `0.92` | Must be greater than `0` and less than `1` |
| `grayscale` | boolean | `false` | Converts non-transparent images to grayscale |
| `sharpness` | float | `1.10` | `1` disables extra sharpening |
| `aggressive` | boolean | `false` | Lowers the effective minimum quality to at most `30` |

PNG uploads are first normalized through a highest-quality JPEG intermediate before the existing compression candidate flow runs. Transparent pixels are flattened onto a white background; the final output format is still controlled by `output_format`.

Example:

```powershell
curl.exe -X POST http://127.0.0.1:8793/api/jobs `
  -F "files=@assets/example.png" `
  -F "target_kb=80" `
  -F "max_side=1300" `
  -F "output_format=jpg"
```

Response:

```json
{
  "id": "job-id",
  "status": "queued",
  "total": 1,
  "completed": 0,
  "failed": 0,
  "files": [
    {
      "id": "file-id",
      "filename": "example.png",
      "status": "queued",
      "original_size": 12345,
      "original_width": null,
      "original_height": null,
      "output_filename": null,
      "output_size": null,
      "output_width": null,
      "output_height": null,
      "output_format": null,
      "note": null,
      "success": null,
      "error": null,
      "compression_ratio": null
    }
  ]
}
```

## Get Job

`GET /api/jobs/{job_id}`

Returns the current job snapshot. Poll this endpoint until `status` is `done`.

Completed files include output metadata and `compression_ratio`. Failed files include an `error` message and still count toward the job's final state.

## Download One File

`GET /api/jobs/{job_id}/files/{file_id}/download`

Returns the compressed bytes for one successfully processed file.

Failure cases:

- `404` when the job does not exist.
- `404` when the file does not exist.
- `404` when the file is not yet successfully processed.

## Download ZIP

`GET /api/jobs/{job_id}/download.zip`

Returns a ZIP containing all successful compressed outputs in that job. If two output names collide, the API appends numeric suffixes inside the archive.

Failure cases:

- `404` when the job does not exist.
- `404` when the job has no successful compressed outputs.

## Error Model

FastAPI validation and explicit option validation return JSON with a `detail` field. Common user-facing messages are Chinese, for example:

- `请至少上传一张图片`
- `target_kb 必须是正整数`
- `无法识别图片格式`
- `文件尚未成功处理`
