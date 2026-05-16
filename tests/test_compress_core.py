from __future__ import annotations

import io

import pytest
from PIL import Image, UnidentifiedImageError

from compress_core import CompressOptions, compress_image_bytes


def make_image(fmt: str = "PNG", size: tuple[int, int] = (320, 180)) -> bytes:
    image = Image.new("RGB", size, "#ffffff")
    for x in range(20, size[0] - 20, 12):
        for y in range(20, size[1] - 20, 18):
            image.putpixel((x, y), (20, 20, 20))

    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def make_transparent_png(size: tuple[int, int] = (120, 80)) -> bytes:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    for x in range(20, 100):
        for y in range(20, 60):
            image.putpixel((x, y), (220, 30, 30, 255))

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("fmt", "filename", "output_format"),
    [
        ("JPEG", "sample.jpg", "jpg"),
        ("PNG", "sample.png", "png"),
        ("WEBP", "sample.webp", "webp"),
    ],
)
def test_compress_image_bytes_handles_common_formats(fmt: str, filename: str, output_format: str) -> None:
    data = make_image(fmt)

    result = compress_image_bytes(
        data,
        filename,
        CompressOptions(target_kb=80, max_side=200, output_format=output_format),
    )

    assert result.data
    assert result.output_size == len(result.data)
    assert result.original_filename == filename
    assert max(result.output_width, result.output_height) <= 200
    assert result.output_filename.endswith(result.suffix)
    assert result.fmt in {"JPEG", "PNG", "WEBP"}


def test_png_input_is_preconverted_to_jpeg_before_compression() -> None:
    result = compress_image_bytes(
        make_transparent_png(),
        "transparent.png",
        CompressOptions(
            target_kb=80,
            max_side=120,
            output_format="png",
            sharpness=1,
        ),
    )

    assert result.fmt == "PNG"
    with Image.open(io.BytesIO(result.data)) as output:
        pixel = output.convert("RGBA").getpixel((0, 0))

    assert pixel[3] == 255
    assert pixel[:3] == (255, 255, 255)


@pytest.mark.parametrize(
    "options",
    [
        CompressOptions(target_kb=0),
        CompressOptions(scale_step=1),
        CompressOptions(output_format="gif"),
    ],
)
def test_compress_image_bytes_validates_options(options: CompressOptions) -> None:
    with pytest.raises(ValueError):
        compress_image_bytes(make_image(), "sample.png", options)


def test_compress_image_bytes_rejects_unidentified_image() -> None:
    with pytest.raises(UnidentifiedImageError):
        compress_image_bytes(b"not an image", "sample.png", CompressOptions())
