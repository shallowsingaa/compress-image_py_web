# 部署和运维

## Local Development

Run the backend:

```powershell
uvicorn app:app --reload --host 127.0.0.1 --port 8793
```

Run the frontend:

```powershell
cd web
$env:VITE_API_BASE_URL='http://127.0.0.1:8793'
cmd /c npm run dev
```

The Vite server is configured for port `8792`.

## Production Options

The frontend reads the API base from `VITE_API_BASE_URL` at build time:

```bash
cd web
VITE_API_BASE_URL="https://example.com" npm run build
```

If `VITE_API_BASE_URL` is unset, the frontend calls same-origin `/api/...`. In that mode, configure the web server to proxy `/api` to the FastAPI backend.

The current Linux script starts Uvicorn on:

```text
0.0.0.0:8793
```

For same-origin production, proxy:

```text
/api/* -> http://127.0.0.1:8793/api/*
```

## Linux Auto Deploy Script

`Linux/auto_sync_build_run.sh` is configured for a Gitee repository and a 1Panel-style static web root.

Important defaults:

| Setting | Value |
| --- | --- |
| `REPO_URL` | `https://gitee.com/shallowspider/compress-image_py_web.git` |
| `BRANCH` | `master` |
| `TARGET_DIR` | `/opt/compress-image/src` |
| `PYTHON_INSTALL_CMD` | `/opt/compress-image/venv/bin/pip3 install -r requirements.txt` |
| `NPM_INSTALL_CMD` | `cd web && npm ci` |
| `BUILD_CMD` | `cd web && npm run build` |
| `AFTER_NPM_INSTALL_CMD` | `/opt/compress-image/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8793` |
| `WEB_ROOT` | `/opt/1panel/www/sites/ci.clicli.asia/index` |
| `BACKEND_PID_FILE` | `/tmp/gitee-site-uvicorn.pid` |
| `BACKEND_LOG_FILE` | `/var/log/gitee-site-uvicorn.log` |
| `LOG_FILE` | `/var/log/gitee-site-deploy.log` |

The script:

1. Acquires a flock lock.
2. Checks the remote commit.
3. Reuses current source when it is already up to date.
4. Stops old matching backend processes before source replacement.
5. Installs Python and npm dependencies.
6. Starts the backend in the background.
7. Builds the frontend.
8. Publishes `web/dist` to `WEB_ROOT` with `rsync --delete`.

Use `FORCE=1` to force a fresh sync and rebuild:

```bash
FORCE=1 ./Linux/auto_sync_build_run.sh
```

## Smoke Checks

Backend health by route existence:

```powershell
curl.exe http://127.0.0.1:8793/api/jobs/missing-id
```

Expected result is a JSON `404` with `detail` equal to `任务不存在`.

Full local validation:

```powershell
pytest
cd web
cmd /c npm run build
```

## Operational Notes

- Keep Uvicorn to one worker unless `_jobs` is replaced with shared storage.
- Restarting the backend clears all active jobs and download data.
- Large batches can increase memory use because original uploads and compressed outputs are processed in-process.
- CORS currently allows all origins. Tighten it before exposing the API to untrusted networks.
