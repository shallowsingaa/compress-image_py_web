#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_text_image.py

将以文字为主的图片等比例缩小并压缩到指定体积附近。
默认目标：
- 最长边 <= 1500px
- 文件体积 <= 80KB
- 尽量保留文字清晰度

安装依赖：
    python -m pip install -U pillow

使用示例：
    python compress_text_image.py input.png
    python compress_text_image.py input.png -o output.webp
    python compress_text_image.py input.png --target-kb 80 --max-side 1500
    python compress_text_image.py input.png --aggressive
    python compress_text_image.py input.png --grayscale
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import (
    Image,
    ImageEnhance,
    ImageOps,
    UnidentifiedImageError,
    features,
)


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
    """
    将带透明通道的图片铺到白色背景上，得到 RGB 图片。
    JPEG 不支持透明通道，因此保存 JPEG 前需要这样处理。
    """
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
    """
    对文字类图片做轻量增强。

    - grayscale=True 可明显减小很多文档截图的体积，但会丢失颜色信息。
    - sharpness 默认只做轻微锐化，避免出现明显白边或噪点。
    """
    out = normalize_for_webp_or_png(img)

    if grayscale and not has_alpha_or_transparency(out):
        out = ImageOps.grayscale(out)

    if sharpness and sharpness != 1.0:
        # ImageEnhance.Sharpness 支持 L/RGB/RGBA 等常见模式。
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
    """尝试保存一个候选结果；失败则跳过。

    注意：这里的 candidate_quality 只是用于记录/排序；
    真正传给 Pillow 的保存参数仍然通过 save_options 里的 quality 传入。
    不能把这个形参也命名为 quality，否则调用时会和 save_options 中的
    quality=... 发生 Python 参数冲突。
    """
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
    """
    质量参数从高到低尝试。
    步长为 5，足够接近目标体积，同时速度较快。
    """
    min_quality = max(1, min(95, min_quality))
    return range(95, min_quality - 1, -5)


def generate_long_sides(
    base_long_side: int,
    min_long_side: int,
    scale_step: float,
) -> list[int]:
    """
    生成逐步缩小的最长边列表。
    默认从 1500 或原图较小最长边开始，逐步缩小到 min_long_side。
    """
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

        # 1) WebP：通常适合在体积与清晰度之间取得较好平衡，也支持透明。
        if "webp" in allowed_formats and features.check("webp"):
            webp_img = normalize_for_webp_or_png(work)

            # WebP lossless 对纯文字/截图有时很优秀，先尝试一次。
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

        # 2) PNG：对纯色背景、截图、文字图片可能很好；尝试原样 PNG 与调色板 PNG。
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

            # 调色板 PNG 对截图/文档常有效，但颜色过少可能影响边缘观感。
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

        # 3) JPEG：不支持透明；使用 4:4:4 采样以尽量保护彩色文字边缘。
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

            # 如果前面都没法达标，4:2:0 可能显著变小，但彩色文字边缘可能变糊。
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

        # 如果当前尺寸已有不错候选达标，后续更小尺寸不一定需要；
        # 但为了选出质量/体积更稳的结果，仍继续收集一轮。
        if any(c.file_size <= target_bytes and c.long_side == long_side for c in candidates):
            # 不立即 break，给同一轮所有格式都试完后，这里可以选择停止缩小。
            break

    return candidates


def candidate_score(candidate: Candidate, target_bytes: int) -> tuple:
    """
    候选排序规则：
    1. 优先达标；
    2. 达标时优先更大尺寸；
    3. 再优先更高质量；
    4. 再优先更接近但不超过目标体积；
    5. 最后偏好 WebP/PNG，通常更适合文字截图。
    """
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

    # 未达标时，选择在当前质量/尺寸约束下文件最小的。
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
    """解析 --format 参数。"""
    fmt = fmt.lower()
    if fmt == "auto":
        return {"webp", "png", "jpeg"}
    if fmt in {"webp", "png", "jpeg", "jpg"}:
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
        # 如果用户给的是目录，则自动生成文件名。
        if output_path.exists() and output_path.is_dir():
            return output_path / f"{input_path.stem}_compressed{suffix}"

        # 如果用户没有写后缀，则使用实际输出格式的后缀。
        if not output_path.suffix:
            return output_path.with_suffix(suffix)

        # 防止实际编码格式和文件后缀不一致，例如把 WebP bytes 写进 .jpg。
        if output_path.suffix.lower() != suffix.lower():
            return output_path.with_suffix(suffix)

        return output_path

    return input_path.with_name(f"{input_path.stem}_compressed{suffix}")


def positive_int(value: str) -> int:
    num = int(value)
    if num <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return num


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="压缩以文字为主的图片：最长边 <= 指定像素，体积尽量 <= 指定 KB。"
    )
    parser.add_argument("input", help="输入图片路径，例如 input.png")
    parser.add_argument("-o", "--output", help="输出文件路径或目录；不填则自动生成")
    parser.add_argument("--max-side", type=positive_int, default=1500, help="最长边上限，默认 1500")
    parser.add_argument("--target-kb", type=positive_int, default=80, help="目标体积 KB，默认 80")
    parser.add_argument(
        "--min-quality",
        type=positive_int,
        default=70,
        help="WebP/JPEG 最低质量，默认 70；越低越小但越容易糊",
    )
    parser.add_argument(
        "--min-long-side",
        type=positive_int,
        default=600,
        help="默认不会把最长边压到低于此值，默认 600；原图更小时不放大",
    )
    parser.add_argument(
        "--scale-step",
        type=float,
        default=0.92,
        help="逐步缩小尺寸的比例，默认 0.92；越小尝试越少",
    )
    parser.add_argument(
        "--format",
        default="auto",
        choices=["auto", "webp", "png", "jpeg", "jpg"],
        help="输出格式，默认 auto 自动选择",
    )
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="转为灰度图；文档截图通常更小，但会丢失颜色",
    )
    parser.add_argument(
        "--sharpness",
        type=float,
        default=1.10,
        help="轻微锐化强度，默认 1.10；设为 1 可关闭",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="更激进地追求 50KB：降低默认最低质量和最低最长边",
    )

    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：找不到输入文件：{input_path}", file=sys.stderr)
        return 2

    if args.scale_step <= 0 or args.scale_step >= 1:
        print("错误：--scale-step 必须在 0 到 1 之间，例如 0.92", file=sys.stderr)
        return 2

    target_bytes = args.target_kb * 1024
    allowed_formats = parse_format_arg(args.format)

    # 如果用户指定了输出后缀但没有显式指定 --format，则尊重输出后缀。
    # 例如：-o outputs/example_out.jpg 应输出真正的 JPEG，而不是 WebP 内容 + .jpg 后缀。
    output_fmt = format_from_suffix(args.output)
    if args.format == "auto" and output_fmt is not None:
        allowed_formats = {output_fmt}

    min_quality = min(args.min_quality, 95)
    min_long_side = args.min_long_side

    if args.aggressive:
        min_quality = min(min_quality, 30)
        min_long_side = min(min_long_side, 420)

    try:
        with Image.open(input_path) as img:
            # 按 EXIF 方向纠正手机照片/截图方向。
            img = ImageOps.exif_transpose(img)
            img.load()

            original_size = input_path.stat().st_size
            original_width, original_height = img.size

            base_img = resize_to_max_side(img, args.max_side)
            candidates = make_candidates(
                base_img=base_img,
                target_bytes=target_bytes,
                min_quality=min_quality,
                grayscale=args.grayscale,
                sharpness=args.sharpness,
                min_long_side=min_long_side,
                scale_step=args.scale_step,
                allowed_formats=allowed_formats,
            )

            best = choose_best_candidate(candidates, target_bytes)
            output_path = build_output_path(input_path, args.output, best.suffix)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(best.data)

    except UnidentifiedImageError:
        print(f"错误：无法识别图片格式：{input_path}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"错误：处理失败：{exc}", file=sys.stderr)
        return 1

    success = best.file_size <= target_bytes

    print("处理完成")
    print("-" * 48)
    print(f"原始路径：{input_path}")
    print(f"原始尺寸：{original_width} x {original_height}")
    print(f"原始体积：{human_size(original_size)}")
    print()
    print(f"输出路径：{output_path}")
    print(f"输出格式：{best.fmt}")
    print(f"输出尺寸：{best.width} x {best.height}")
    print(f"输出体积：{human_size(best.file_size)}")
    print(f"压缩策略：{best.note}")
    print(f"是否达到 <= {args.target_kb}KB：{'是' if success else '否'}")

    if not success:
        print()
        print("提示：在当前“最低质量/最低尺寸”约束下，未能压到目标体积以内。")
        print("你可以尝试：")
        print("  1. 添加 --aggressive")
        print("  2. 添加 --grayscale")
        print("  3. 降低 --min-quality，例如 --min-quality 30")
        print("  4. 降低 --min-long-side，例如 --min-long-side 420")
        print("  5. 适当提高 --target-kb，例如 --target-kb 80")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
