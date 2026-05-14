# Agent Notes

This repository is a runnable image compression web app. Keep changes aligned with the current code instead of treating it as a static demo.

## Project Shape

- `compress_core.py` is the shared compression implementation for both the CLI and API.
- `main.py` is the CLI entry point and should stay behaviorally consistent with the shared core.
- `app.py` exposes the FastAPI API and stores jobs in process memory.
- `web/` is a Vite + React + TypeScript frontend.
- `Linux/auto_sync_build_run.sh` is the deployment script for the Gitee-hosted production flow.
- `docs/` is the human-facing handoff documentation. Update it when API routes, compression options, deployment ports, or runtime assumptions change.

## Runtime Contracts

- API job data and compressed bytes are in-memory only. A process restart loses old jobs and download data.
- `POST /api/jobs` accepts multipart field name `files` and form options that map to `CompressOptions`.
- `GET /api/jobs/{job_id}` is the polling endpoint used by the frontend.
- Download routes only work after a file has status `done`.
- Frontend `VITE_API_BASE_URL` controls API origin. When unset, requests go to same-origin `/api`.
- Production deployment either needs a reverse proxy from `/api` to the FastAPI backend or a build-time `VITE_API_BASE_URL`.

## Verification

Use these checks after relevant changes:

```powershell
pytest
cd web
cmd /c npm run build
```

For narrow Python-only changes, `pytest` is the minimum useful gate. For frontend changes, run the Vite build. If the local dev server is needed, start the backend on port `8793`, set `VITE_API_BASE_URL=http://127.0.0.1:8793`, then run `cmd /c npm run dev` in `web/`.

## Editing Guidance

- Preserve Chinese UI and error messages unless the user asks to rewrite copy.
- Prefer updating `CompressOptions` and tests together when adding compression parameters.
- Keep API response field names stable; the React types in `web/src/main.tsx` depend on them.
- Do not document the frontend as defaulting to `127.0.0.1:8793`; that only happens when `VITE_API_BASE_URL` is set.
