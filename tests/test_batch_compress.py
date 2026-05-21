from __future__ import annotations

import io

from PIL import Image

from batch_compress import BatchImage, compress_batch
from compress_core import CompressOptions


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (160, 100), "#ffffff")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_compress_batch_reports_partial_failures() -> None:
    results = list(
        compress_batch(
            [
                BatchImage(id="ok", filename="ok.png", data=make_image_bytes()),
                BatchImage(id="bad", filename="bad.txt", data=b"not an image"),
            ],
            CompressOptions(target_kb=80, output_format="jpg"),
        )
    )

    assert results[0].success
    assert results[0].result is not None
    assert results[0].result.output_filename == "ok_compressed.jpg"
    assert not results[1].success
    assert results[1].error == "无法识别图片格式"
