# Agent Notes

This repository is a runnable image compression web app. Keep changes aligned with the current code instead of treating it as a static demo.

## Project Shape

- `compress_core.py` is the shared compression implementation for both the CLI and API.
- `batch_compress.py` owns per-file batch success/failure semantics over the shared core.
- `main.py` is the CLI entry point and should stay behaviorally consistent with the shared core.
- `clipboard_io.py` contains Windows-only clipboard image/file-list interop for the CLI `--clipboard` mode.
- `app.py` exposes the FastAPI API routes; `job_store.py` stores jobs and compressed bytes in process memory.
- `web/` is a Vite + React + TypeScript frontend.
- `package/` is the npm package root for `compress-img-cli`; it ships Node launchers plus generated PyInstaller binaries under `package/resources/`.
- `Linux/auto_sync_build_run.sh` is the deployment script for the Gitee-hosted production flow.
- `scripts/install-compress-img-hotkey/` contains the Windows Alt+E helper installer; it registers the elevated `CompressImgClipboard` task through Task Scheduler COM, writes `%LOCALAPPDATA%\CompressImgHotkey\install.log`, and keeps the user-facing usage notes in its local `README.md`.
- `docs/` is the human-facing handoff documentation. Update it when API routes, compression options, deployment ports, or runtime assumptions change.

## Runtime Contracts

- API job data and compressed bytes are in-memory only. A process restart loses old jobs and download data.
- `POST /api/jobs` accepts multipart field name `files` and form options that map to `CompressOptions`.
- `GET /api/jobs/{job_id}` is the polling endpoint used by the frontend.
- Download routes only work after a file has status `done`.
- Frontend `VITE_API_BASE_URL` controls API origin. When unset, requests go to same-origin `/api`.
- Production deployment either needs a reverse proxy from `/api` to the FastAPI backend or a build-time `VITE_API_BASE_URL`.
- The npm package name is `compress-img-cli`; the installed terminal command is `compress-img`.
- `package/resources/` is intentionally ignored by git. Build Windows and Linux binaries before `npm publish`, then verify with `npm pack --dry-run`.

## Agent skills

### Issue tracker

Issues live as markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Local markdown convention — `Status:` field in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` at repo root, `docs/adr/` for architectural decisions. See `docs/agents/domain.md`.

## Verification

Use these checks after relevant changes:

```powershell
pytest
cd web
cmd /c npm run build
```

For narrow Python-only changes, `pytest` is the minimum useful gate. For frontend changes, run the Vite build. If the local dev server is needed, start the backend on port `8793`, set `VITE_API_BASE_URL=http://127.0.0.1:8793`, then run `cmd /c npm run dev` in `web/`.

For npm package metadata or documentation changes:

```powershell
cd package
cmd /c npm pack --dry-run
```

For npm package binary changes, also run `npm run build:win` on Windows and `npm run build:linux` on Linux before publishing.

## Editing Guidance

- Preserve Chinese UI and error messages unless the user asks to rewrite copy.
- Keep Windows clipboard behavior isolated in `clipboard_io.py`; non-Windows callers should receive a clear `ClipboardError`.
- When changing `scripts/install-compress-img-hotkey/`, keep the script, its local `README.md`, and `scripts/install-compress-img-hotkey/tests/install-script-security.Tests.ps1` aligned on UAC behavior, install artifacts, log-file location, the `CompressImgClipboard` task name, and the top-level `$TaskCommand`.
- The hotkey installer should update the current `CompressImgClipboard` task in place and only clean legacy names such as `CompressImgClipboard65`; do not treat the current task as stale just because the installer has already run once.
- The unelevated hotkey installer may wait for the elevated installer to preserve its exit code, but the elevated child must use `-SkipStartHotkey` so it does not start the resident hotkey process while the parent is waiting.
- Prefer updating `CompressOptions` and tests together when adding compression parameters.
- Keep API response field names stable; the React types in `web/src/types.ts` depend on them.
- Do not document the frontend as defaulting to `127.0.0.1:8793`; that only happens when `VITE_API_BASE_URL` is set.
- Do not commit `package/resources/`; those binaries are release artifacts, not source.
- Keep `package/README.md`, `package/HELP.md`, `package/PUBLISHING.md`, `docs/npm-package.md`, and `docs/superpowers/` aligned when changing npm package name, command name, supported platforms, or publish flow.
