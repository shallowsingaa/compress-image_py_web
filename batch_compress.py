from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator

from PIL import UnidentifiedImageError

from compress_core import CompressOptions, CompressedResult, compress_image_bytes


@dataclass(frozen=True)
class BatchImage:
    id: str
    filename: str
    data: bytes


@dataclass(frozen=True)
class BatchImageResult:
    id: str
    filename: str
    original_size: int
    result: CompressedResult | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.result is not None


def compress_batch(
    images: Iterable[BatchImage],
    options: CompressOptions,
) -> Iterator[BatchImageResult]:
    for image in images:
        try:
            result = compress_image_bytes(image.data, image.filename, options)
        except UnidentifiedImageError:
            yield BatchImageResult(
                id=image.id,
                filename=image.filename,
                original_size=len(image.data),
                error="无法识别图片格式",
            )
        except ValueError as exc:
            yield BatchImageResult(
                id=image.id,
                filename=image.filename,
                original_size=len(image.data),
                error=str(exc),
            )
        except Exception as exc:
            yield BatchImageResult(
                id=image.id,
                filename=image.filename,
                original_size=len(image.data),
                error=f"处理失败：{exc}",
            )
        else:
            yield BatchImageResult(
                id=image.id,
                filename=image.filename,
                original_size=len(image.data),
                result=result,
            )
