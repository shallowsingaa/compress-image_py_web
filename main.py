#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compress_text_image.py

将以文字为主的图片等比例缩小并压缩到指定体积附近。
默认目标：
- 最长边 <= 1300px
- 文件体积 <= 80KB
- 输出 JPG
- 尽量保留文字清晰度

安装依赖：
    python -m pip install -U pillow

使用示例：
    python main.py input.png
    python main.py input.png -o output.webp
    python main.py input.png --target-kb 80 --max-side 1300
    python main.py input.png --format auto
    python main.py input.png --aggressive
    python main.py input.png --grayscale
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from PIL import UnidentifiedImageError

from clipboard_io import (
    ClipboardError,
    ClipboardImage,
    read_clipboard_images,
    write_clipboard_images,
)
from batch_compress import BatchImage, compress_batch
from compress_core import (
    DEFAULT_COMPRESS_OPTIONS,
    OUTPUT_FORMAT_CHOICES,
    CompressedResult,
    CompressOptions,
    compress_image_file,
    format_from_suffix,
    human_size,
    validate_options,
)


def positive_int(value: str) -> int:
    num = int(value)
    if num <= 0:
        raise argparse.ArgumentTypeError("必须是正整数")
    return num


def build_options(args: argparse.Namespace) -> CompressOptions:
    output_fmt = format_from_suffix(args.output)
    if args.format is not None:
        output_format = args.format
    elif output_fmt is not None:
        output_format = output_fmt
    else:
        output_format = "jpg"

    return CompressOptions(
        target_kb=args.target_kb,
        max_side=args.max_side,
        min_quality=args.min_quality,
        min_long_side=args.min_long_side,
        scale_step=args.scale_step,
        output_format=output_format,
        grayscale=args.grayscale,
        sharpness=args.sharpness,
        aggressive=args.aggressive,
    )


def print_result_summary(
    result: CompressedResult,
    output_path: Path,
    target_kb: int,
    input_label: str,
) -> None:
    print(f"原始路径：{input_label}")
    print(f"原始尺寸：{result.original_width} x {result.original_height}")
    print(f"原始体积：{human_size(result.original_size)}")
    print()
    print(f"输出路径：{output_path}")
    print(f"输出格式：{result.fmt}")
    print(f"输出尺寸：{result.output_width} x {result.output_height}")
    print(f"输出体积：{human_size(result.output_size)}")
    print(f"压缩策略：{result.note}")
    print(f"是否达到 <= {target_kb}KB：{'是' if result.success else '否'}")


def clipboard_output_dir(output_arg: Optional[str]) -> Path:
    if not output_arg:
        return Path("outputs") / "clipboard"

    output_path = Path(output_arg)
    if output_path.suffix:
        return output_path.parent / "clipboard"

    return output_path / "clipboard"


def clipboard_output_path(filename: str, output_arg: Optional[str], suffix: str) -> Path:
    input_path = Path(filename)
    return clipboard_output_dir(output_arg) / f"{input_path.stem}_compressed{suffix}"


def mime_from_result(result: CompressedResult) -> str:
    if result.suffix.lower() in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if result.suffix.lower() == ".webp":
        return "image/webp"
    return "image/png"


def process_clipboard(args: argparse.Namespace, options: CompressOptions) -> int:
    try:
        images = read_clipboard_images()
    except ClipboardError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if not images:
        print("错误：剪贴板中没有可用图片。请先复制截图、图片，或在资源管理器中复制图片文件。", file=sys.stderr)
        return 2

    try:
        validate_options(options)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    print(f"剪贴板图片：{len(images)} 张")
    print("-" * 48)

    copied_items: list[tuple[bytes, str, str]] = []
    failed = 0

    for index, image in enumerate(images, start=1):
        if index > 1:
            print()
            print("-" * 48)

        batch_result = next(
            compress_batch(
                [BatchImage(id=str(index), filename=image.filename, data=image.data)],
                options,
            )
        )
        if batch_result.result is None:
            failed += 1
            print(f"第 {index} 张处理失败：{batch_result.error}：{image.filename}", file=sys.stderr)
            continue

        result = batch_result.result
        output_path = clipboard_output_path(image.filename, args.output, result.suffix)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(result.data)
        except Exception as exc:
            failed += 1
            print(f"第 {index} 张处理失败：{exc}", file=sys.stderr)
            continue

        print_result_summary(result, output_path, args.target_kb, f"剪贴板：{image.filename}")
        copied_items.append((result.data, str(output_path), mime_from_result(result)))

    if not copied_items:
        print("错误：剪贴板图片全部处理失败，未写入剪贴板。", file=sys.stderr)
        return 1

    try:
        write_clipboard_images(copied_items)
    except ClipboardError as exc:
        print()
        print(f"警告：压缩结果已保存，但复制回剪贴板失败：{exc}", file=sys.stderr)
        return 1 if failed else 0

    print()
    if len(copied_items) == 1:
        print("已将压缩结果复制回剪贴板。")
    else:
        print(f"已将 {len(copied_items)} 个压缩结果作为一组文件复制回剪贴板。")

    if failed:
        print(f"警告：有 {failed} 张图片处理失败，其余结果已保存并复制。", file=sys.stderr)
        return 1

    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="压缩以文字为主的图片：最长边 <= 指定像素，体积尽量 <= 指定 KB。"
    )
    parser.add_argument("input", nargs="?", help="输入图片路径，例如 input.png")
    parser.add_argument("-o", "--output", help="输出文件路径或目录；不填则自动生成")
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="从 Windows 剪贴板读取图片作为输入，处理成功后复制结果回剪贴板",
    )
    parser.add_argument(
        "--max-side",
        type=positive_int,
        default=DEFAULT_COMPRESS_OPTIONS.max_side,
        help=f"最长边上限，默认 {DEFAULT_COMPRESS_OPTIONS.max_side}",
    )
    parser.add_argument(
        "--target-kb",
        type=positive_int,
        default=DEFAULT_COMPRESS_OPTIONS.target_kb,
        help=f"目标体积 KB，默认 {DEFAULT_COMPRESS_OPTIONS.target_kb}",
    )
    parser.add_argument(
        "--min-quality",
        type=positive_int,
        default=DEFAULT_COMPRESS_OPTIONS.min_quality,
        help=f"WebP/JPEG 最低质量，默认 {DEFAULT_COMPRESS_OPTIONS.min_quality}；越低越小但越容易糊",
    )
    parser.add_argument(
        "--min-long-side",
        type=positive_int,
        default=None,
        help="手动指定最低最长边；默认不限制，原图更小时不放大",
    )
    parser.add_argument(
        "--scale-step",
        type=float,
        default=DEFAULT_COMPRESS_OPTIONS.scale_step,
        help=f"逐步缩小尺寸的比例，默认 {DEFAULT_COMPRESS_OPTIONS.scale_step}；越小尝试越少",
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=OUTPUT_FORMAT_CHOICES,
        help="输出格式，默认 jpg；未指定时会优先使用输出路径后缀",
    )
    parser.add_argument(
        "--grayscale",
        action="store_true",
        help="转为灰度图；文档截图通常更小，但会丢失颜色",
    )
    parser.add_argument(
        "--sharpness",
        type=float,
        default=DEFAULT_COMPRESS_OPTIONS.sharpness,
        help=f"轻微锐化强度，默认 {DEFAULT_COMPRESS_OPTIONS.sharpness:.2f}；设为 1 可关闭",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="更激进地追求 50KB：降低默认最低质量",
    )

    args = parser.parse_args(argv)

    if not args.clipboard and not args.input:
        print("错误：请提供输入图片路径，或使用 --clipboard 从剪贴板读取图片。", file=sys.stderr)
        return 2

    options = build_options(args)

    if args.clipboard:
        return process_clipboard(args, options)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：找不到输入文件：{input_path}", file=sys.stderr)
        return 2

    try:
        result, output_path = compress_image_file(input_path, args.output, options)
    except UnidentifiedImageError:
        print(f"错误：无法识别图片格式：{input_path}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"错误：处理失败：{exc}", file=sys.stderr)
        return 1

    print("处理完成")
    print("-" * 48)
    print_result_summary(result, output_path, args.target_kb, str(input_path))

    if not result.success:
        print()
        if args.min_long_side is not None:
            print("提示：在当前“最低质量/最低尺寸”约束下，未能压到目标体积以内。")
        else:
            print("提示：在当前“最低质量”约束下，未能压到目标体积以内。")
        print("你可以尝试：")
        print("  1. 添加 --aggressive")
        print("  2. 添加 --grayscale")
        print("  3. 降低 --min-quality，例如 --min-quality 30")
        if args.min_long_side is not None:
            print("  4. 降低或移除 --min-long-side")
            print("  5. 适当提高 --target-kb，例如 --target-kb 80")
        else:
            print("  4. 适当提高 --target-kb，例如 --target-kb 80")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
