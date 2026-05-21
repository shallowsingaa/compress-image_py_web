from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageEnhance, ImageOps, features


@dataclass(frozen=True)
class Candidate:
    """一次压缩尝试的结果。"""

    data: bytes
    fmt: str
    suffix: str
    width: int
    height: int
    quality: Optional[int]
    file_size: int
    note: str

    @property
    def long_side(self) -> int:
        return max(self.width, self.height)


@dataclass(frozen=True)
class CompressOptions:
    target_kb: int = 80
    max_side: int = 1300
    min_quality: int = 70
    min_long_side: Optional[int] = None
    scale_step: float = 0.92
    output_format: str = "jpg"
    grayscale: bool = False
    sharpness: float = 1.10
    aggressive: bool = False


DEFAULT_COMPRESS_OPTIONS = CompressOptions()
OUTPUT_FORMAT_CHOICES = ("auto", "webp", "png", "jpeg", "jpg")


@dataclass(frozen=True)
class CompressedResult:
    data: bytes
    output_filename: str
    fmt: str
    suffix: str
    original_filename: str
    original_size: int
    original_width: int
    original_height: int
    output_size: int
    output_width: int
    output_height: int
    quality: Optional[int]
    note: str
    target_kb: int
    success: bool


def human_size(num_bytes: int) -> str:
    """将字节数格式化为更易读的字符串。"""
    return f"{num_bytes / 1024:.1f}KB"


def has_alpha_or_transparency(img: Image.Image) -> bool:
    """判断图片是否包含透明信息。"""
    return (
        img.mode in ("RGBA", "LA")
        or (img.mode == "P" and "transparency" in img.info)
    )


def flatten_to_rgb(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """将带透明通道的图片铺到白色背景上，得到 RGB 图片。"""
    if has_alpha_or_transparency(img):
        rgba = img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, background + (255,))
        bg.alpha_composite(rgba)
        return bg.convert("RGB")

    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def normalize_for_webp_or_png(img: Image.Image) -> Image.Image:
    """转换为适合 WebP/PNG 保存的模式。"""
    if has_alpha_or_transparency(img):
        return img.convert("RGBA")

    if img.mode in ("RGB", "L"):
        return img.copy()

    return img.convert("RGB")


def resize_to_max_side(img: Image.Image, max_side: int) -> Image.Image:
    """等比例缩小图片，使最长边不超过 max_side；不会放大原图。"""
    width, height = img.size
    long_side = max(width, height)

    if long_side <= max_side:
        return img.copy()

    ratio = max_side / long_side
    new_size = (
        max(1, round(width * ratio)),
        max(1, round(height * ratio)),
    )

    return img.resize(
        new_size,
        resample=Image.Resampling.LANCZOS,
        reducing_gap=3.0,
    )


def resize_to_long_side(img: Image.Image, target_long_side: int) -> Image.Image:
    """等比例缩放到指定最长边；不会放大。"""
    width, height = img.size
    long_side = max(width, height)

    if target_long_side >= long_side:
        return img.copy()

    ratio = target_long_side / long_side
    new_size = (
        max(1, round(width * ratio)),
        max(1, round(height * ratio)),
    )

    return img.resize(
        new_size,
        resample=Image.Resampling.LANCZOS,
        reducing_gap=3.0,
    )


def apply_text_friendly_enhancement(
    img: Image.Image,
    grayscale: bool,
    sharpness: float,
) -> Image.Image:
    """对文字类图片做轻量增强。"""
    out = normalize_for_webp_or_png(img)

    if grayscale and not has_alpha_or_transparency(out):
        out = ImageOps.grayscale(out)

    if sharpness and sharpness != 1.0:
        out = ImageEnhance.Sharpness(out).enhance(sharpness)

    return out


def save_bytes(img: Image.Image, fmt: str, **options) -> bytes:
    """将图片保存到内存并返回 bytes。"""
    buffer = io.BytesIO()
    img.save(buffer, format=fmt, **options)
    return buffer.getvalue()


def add_candidate(
    candidates: list[Candidate],
    img: Image.Image,
    fmt: str,
    suffix: str,
    candidate_quality: Optional[int],
    note: str,
    **save_options,
) -> None:
    """尝试保存一个候选结果；失败则跳过。"""
    try:
        data = save_bytes(img, fmt, **save_options)
    except Exception:
        return

    candidates.append(
        Candidate(
            data=data,
            fmt=fmt,
            suffix=suffix,
            width=img.width,
            height=img.height,
            quality=candidate_quality,
            file_size=len(data),
            note=note,
        )
    )


def iter_quality_values(min_quality: int) -> Iterable[int]:
    """质量参数从高到低尝试。"""
    min_quality = max(1, min(95, min_quality))
    return range(95, min_quality - 1, -5)


def generate_long_sides(
    base_long_side: int,
    min_long_side: int,
    scale_step: float,
) -> list[int]:
    """生成逐步缩小的最长边列表。"""
    min_long_side = min(min_long_side, base_long_side)
    min_long_side = max(1, min_long_side)

    sides: list[int] = []
    current = base_long_side

    while current >= min_long_side:
        if not sides or current != sides[-1]:
            sides.append(current)

        next_side = int(current * scale_step)
        if next_side >= current:
            break
        current = next_side

    if sides[-1] != min_long_side:
        sides.append(min_long_side)

    return sides


def make_candidates(
    base_img: Image.Image,
    target_bytes: int,
    min_quality: int,
    grayscale: bool,
    sharpness: float,
    min_long_side: int,
    scale_step: float,
    allowed_formats: set[str],
) -> list[Candidate]:
    """生成所有候选压缩结果。"""
    candidates: list[Candidate] = []

    base_long_side = max(base_img.size)
    long_sides = generate_long_sides(base_long_side, min_long_side, scale_step)

    for long_side in long_sides:
        resized = resize_to_long_side(base_img, long_side)
        work = apply_text_friendly_enhancement(resized, grayscale, sharpness)

        if "webp" in allowed_formats and features.check("webp"):
            webp_img = normalize_for_webp_or_png(work)

            add_candidate(
                candidates,
                webp_img,
                "WEBP",
                ".webp",
                None,
                "WebP lossless",
                lossless=True,
                quality=100,
                method=6,
            )

            for q in iter_quality_values(min_quality):
                add_candidate(
                    candidates,
                    webp_img,
                    "WEBP",
                    ".webp",
                    q,
                    f"WebP quality={q}",
                    quality=q,
                    method=6,
                    alpha_quality=100,
                )

        if "png" in allowed_formats:
            png_img = normalize_for_webp_or_png(work)

            add_candidate(
                candidates,
                png_img,
                "PNG",
                ".png",
                None,
                "PNG optimize",
                optimize=True,
                compress_level=9,
            )

            for colors in (256, 128, 64, 32):
                try:
                    if has_alpha_or_transparency(png_img):
                        quantized = png_img.convert("RGBA").quantize(
                            colors=colors,
                            method=Image.Quantize.FASTOCTREE,
                        )
                    else:
                        quantized = png_img.convert("RGB").quantize(
                            colors=colors,
                            method=Image.Quantize.MEDIANCUT,
                        )
                except Exception:
                    continue

                add_candidate(
                    candidates,
                    quantized,
                    "PNG",
                    ".png",
                    None,
                    f"PNG palette colors={colors}",
                    optimize=True,
                    compress_level=9,
                )

        if "jpeg" in allowed_formats or "jpg" in allowed_formats:
            jpg_img = flatten_to_rgb(work)

            for q in iter_quality_values(min_quality):
                add_candidate(
                    candidates,
                    jpg_img,
                    "JPEG",
                    ".jpg",
                    q,
                    f"JPEG quality={q}, subsampling=4:4:4",
                    quality=q,
                    optimize=True,
                    progressive=True,
                    subsampling=0,
                )

            for q in range(max(75, min_quality), min_quality - 1, -5):
                add_candidate(
                    candidates,
                    jpg_img,
                    "JPEG",
                    ".jpg",
                    q,
                    f"JPEG quality={q}, subsampling=4:2:0",
                    quality=q,
                    optimize=True,
                    progressive=True,
                    subsampling=2,
                )

        if any(c.file_size <= target_bytes and c.long_side == long_side for c in candidates):
            break

    return candidates


def candidate_score(candidate: Candidate, target_bytes: int) -> tuple:
    """候选排序规则。"""
    meets = candidate.file_size <= target_bytes
    quality_score = candidate.quality if candidate.quality is not None else 100

    format_preference = {
        "WEBP": 3,
        "PNG": 2,
        "JPEG": 1,
    }.get(candidate.fmt, 0)

    if meets:
        return (
            1,
            candidate.long_side,
            quality_score,
            candidate.file_size,
            format_preference,
        )

    return (
        0,
        -candidate.file_size,
        candidate.long_side,
        quality_score,
        format_preference,
    )


def choose_best_candidate(candidates: list[Candidate], target_bytes: int) -> Candidate:
    """选择最佳候选结果。"""
    if not candidates:
        raise RuntimeError("没有生成任何可用的输出候选。")

    return max(candidates, key=lambda c: candidate_score(c, target_bytes))


def parse_format_arg(fmt: str) -> set[str]:
    """解析输出格式参数。"""
    fmt = fmt.lower()
    if fmt == "auto":
        return {"webp", "png", "jpeg"}
    if fmt in OUTPUT_FORMAT_CHOICES:
        return {fmt}
    raise ValueError(f"不支持的格式：{fmt}")


def format_from_suffix(path: Optional[str]) -> Optional[str]:
    """从输出路径后缀推断用户想要的格式。"""
    if not path:
        return None

    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "jpg"
    if suffix == ".png":
        return "png"
    if suffix == ".webp":
        return "webp"
    return None


def build_output_path(input_path: Path, output_arg: Optional[str], suffix: str) -> Path:
    """生成输出路径。"""
    if output_arg:
        output_path = Path(output_arg)
        if output_path.exists() and output_path.is_dir():
            return output_path / f"{input_path.stem}_compressed{suffix}"

        if not output_path.suffix:
            return output_path.with_suffix(suffix)

        if output_path.suffix.lower() != suffix.lower():
            return output_path.with_suffix(suffix)

        return output_path

    return input_path.with_name(f"{input_path.stem}_compressed{suffix}")


def validate_options(options: CompressOptions) -> None:
    if options.target_kb <= 0:
        raise ValueError("target_kb 必须是正整数")
    if options.max_side <= 0:
        raise ValueError("max_side 必须是正整数")
    if options.min_quality <= 0:
        raise ValueError("min_quality 必须是正整数")
    if options.min_long_side is not None and options.min_long_side <= 0:
        raise ValueError("min_long_side 必须是正整数")
    if options.scale_step <= 0 or options.scale_step >= 1:
        raise ValueError("scale_step 必须在 0 到 1 之间，例如 0.92")
    parse_format_arg(options.output_format)


def safe_output_filename(filename: str, suffix: str) -> str:
    stem = Path(filename).stem or "image"
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem).strip(" .")
    if not stem:
        stem = "image"
    return f"{stem}_compressed{suffix}"


def compress_image_bytes(
    input_bytes: bytes,
    filename: str,
    options: CompressOptions | None = None,
) -> CompressedResult:
    """压缩内存中的图片 bytes，并返回输出 bytes 与元数据。"""
    options = options or CompressOptions()
    validate_options(options)

    target_bytes = options.target_kb * 1024
    allowed_formats = parse_format_arg(options.output_format)
    min_quality = min(options.min_quality, 95)
    min_long_side = options.min_long_side if options.min_long_side is not None else 1

    if options.aggressive:
        min_quality = min(min_quality, 30)

    with Image.open(io.BytesIO(input_bytes)) as img:
        img = ImageOps.exif_transpose(img)
        img.load()

        original_width, original_height = img.size
        base_img = resize_to_max_side(img, options.max_side)
        candidates = make_candidates(
            base_img=base_img,
            target_bytes=target_bytes,
            min_quality=min_quality,
            grayscale=options.grayscale,
            sharpness=options.sharpness,
            min_long_side=min_long_side,
            scale_step=options.scale_step,
            allowed_formats=allowed_formats,
        )

    best = choose_best_candidate(candidates, target_bytes)
    return CompressedResult(
        data=best.data,
        output_filename=safe_output_filename(filename, best.suffix),
        fmt=best.fmt,
        suffix=best.suffix,
        original_filename=filename,
        original_size=len(input_bytes),
        original_width=original_width,
        original_height=original_height,
        output_size=best.file_size,
        output_width=best.width,
        output_height=best.height,
        quality=best.quality,
        note=best.note,
        target_kb=options.target_kb,
        success=best.file_size <= target_bytes,
    )


def compress_image_file(
    input_path: Path,
    output_arg: Optional[str],
    options: CompressOptions,
) -> tuple[CompressedResult, Path]:
    """压缩磁盘图片并写入输出路径。"""
    input_bytes = input_path.read_bytes()
    result = compress_image_bytes(input_bytes, input_path.name, options)
    output_path = build_output_path(input_path, output_arg, result.suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(result.data)
    return result, output_path
