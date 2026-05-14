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

from compress_core import (
    CompressOptions,
    compress_image_file,
    format_from_suffix,
    human_size,
)


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
    parser.add_argument("--max-side", type=positive_int, default=1300, help="最长边上限，默认 1300")
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
        default=None,
        help="手动指定最低最长边；默认不限制，原图更小时不放大",
    )
    parser.add_argument(
        "--scale-step",
        type=float,
        default=0.92,
        help="逐步缩小尺寸的比例，默认 0.92；越小尝试越少",
    )
    parser.add_argument(
        "--format",
        default=None,
        choices=["auto", "webp", "png", "jpeg", "jpg"],
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
        default=1.10,
        help="轻微锐化强度，默认 1.10；设为 1 可关闭",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="更激进地追求 50KB：降低默认最低质量",
    )

    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"错误：找不到输入文件：{input_path}", file=sys.stderr)
        return 2

    output_fmt = format_from_suffix(args.output)
    if args.format is not None:
        output_format = args.format
    elif output_fmt is not None:
        output_format = output_fmt
    else:
        output_format = "jpg"

    options = CompressOptions(
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
    print(f"原始路径：{input_path}")
    print(f"原始尺寸：{result.original_width} x {result.original_height}")
    print(f"原始体积：{human_size(result.original_size)}")
    print()
    print(f"输出路径：{output_path}")
    print(f"输出格式：{result.fmt}")
    print(f"输出尺寸：{result.output_width} x {result.output_height}")
    print(f"输出体积：{human_size(result.output_size)}")
    print(f"压缩策略：{result.note}")
    print(f"是否达到 <= {args.target_kb}KB：{'是' if result.success else '否'}")

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
