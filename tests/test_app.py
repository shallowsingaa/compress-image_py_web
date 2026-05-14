from __future__ import annotations

import io
import time
import zipfile

from fastapi.testclient import TestClient
from PIL import Image

from app import _jobs, app


def make_image(name: str = "sample.png") -> tuple[str, bytes, str]:
    image = Image.new("RGB", (240, 160), "#ffffff")
    for x in range(10, 220, 20):
        for y in range(10, 140, 20):
            image.putpixel((x, y), (10, 10, 10))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return name, buffer.getvalue(), "image/png"


def test_batch_job_allows_partial_failure_and_downloads_zip() -> None:
    _jobs.clear()
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        data={"target_kb": "80", "output_format": "jpg"},
        files=[
            ("files", make_image("a.png")),
            ("files", ("bad.txt", b"not an image", "text/plain")),
        ],
    )

    assert response.status_code == 200
    payload = response.json()
    for _ in range(30):
        payload = client.get(f"/api/jobs/{payload['id']}").json()
        if payload["status"] == "done":
            break
        time.sleep(0.1)

    assert payload["status"] == "done"
    assert payload["completed"] == 1
    assert payload["failed"] == 1

    done_file = next(file for file in payload["files"] if file["status"] == "done")
    bad_file = next(file for file in payload["files"] if file["status"] == "error")
    assert bad_file["error"] == "无法识别图片格式"

    single = client.get(f"/api/jobs/{payload['id']}/files/{done_file['id']}/download")
    assert single.status_code == 200
    assert single.content

    archive = client.get(f"/api/jobs/{payload['id']}/download.zip")
    assert archive.status_code == 200
    with zipfile.ZipFile(io.BytesIO(archive.content)) as zf:
        assert zf.namelist() == [done_file["output_filename"]]


def test_create_job_rejects_bad_options() -> None:
    _jobs.clear()
    client = TestClient(app)

    response = client.post(
        "/api/jobs",
        data={"target_kb": "0"},
        files=[("files", make_image())],
    )

    assert response.status_code == 400
    assert "target_kb" in response.json()["detail"]
