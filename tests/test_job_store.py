from __future__ import annotations

from compress_core import CompressedResult
from job_store import InMemoryJobStore, JobFile


def make_result() -> CompressedResult:
    return CompressedResult(
        data=b"compressed",
        output_filename="a_compressed.jpg",
        fmt="JPEG",
        suffix=".jpg",
        original_filename="a.png",
        original_size=100,
        original_width=10,
        original_height=10,
        output_size=40,
        output_width=8,
        output_height=8,
        quality=90,
        note="JPEG quality=90",
        target_kb=80,
        success=True,
    )


def test_job_store_serializes_metadata_without_bytes() -> None:
    store = InMemoryJobStore()
    store.create_job("job", [JobFile(id="file", filename="a.png", original_size=100)])
    store.mark_job_processing("job")
    store.mark_file_processing("job", "file")
    store.apply_success("job", "file", make_result())
    store.mark_job_done("job")

    payload = store.serialize_job("job")

    assert payload["status"] == "done"
    assert payload["completed"] == 1
    assert payload["files"][0]["compression_ratio"] == 0.6
    assert "data" not in payload["files"][0]
    assert store.get_download("job", "file") == (b"compressed", "a_compressed.jpg")
