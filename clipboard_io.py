from __future__ import annotations

import ctypes
import ctypes.wintypes
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass(frozen=True)
class ClipboardImage:
    data: bytes
    filename: str


class ClipboardError(RuntimeError):
    pass


_CF_DIB = 8
_CF_HDROP = 15
_GMEM_MOVEABLE = 0x0002
_GHND = 0x0042
_DROPFILES_HEADER_SIZE = 20
_BI_BITFIELDS = 3
_BI_ALPHABITFIELDS = 6
_API_CONFIGURED = False


def read_clipboard_images() -> list[ClipboardImage]:
    _require_windows()
    if not _open_clipboard():
        raise ClipboardError("无法打开剪贴板，请稍后重试")

    try:
        if ctypes.windll.user32.IsClipboardFormatAvailable(_CF_HDROP):
            images = _read_hdrop_images()
            if images:
                return images

        if ctypes.windll.user32.IsClipboardFormatAvailable(_CF_DIB):
            data = _read_dib_image()
            return [ClipboardImage(data, "clipboard.png")]

        return []
    finally:
        ctypes.windll.user32.CloseClipboard()


def write_clipboard_images(items: list[tuple[bytes, str, str]]) -> None:
    _require_windows()
    if not items:
        raise ClipboardError("没有可复制的图片")

    if not _open_clipboard():
        raise ClipboardError("无法打开剪贴板，请稍后重试")

    try:
        if not ctypes.windll.user32.EmptyClipboard():
            raise ClipboardError("无法清空剪贴板")

        paths = [Path(filename).resolve() for _data, filename, _mime in items]
        _write_hdrop(paths)
    finally:
        ctypes.windll.user32.CloseClipboard()


def _require_windows() -> None:
    if sys.platform != "win32":
        raise ClipboardError("剪贴板图片模式当前仅支持 Windows")
    _configure_windows_api()


def _configure_windows_api() -> None:
    global _API_CONFIGURED
    if _API_CONFIGURED:
        return

    wintypes = ctypes.wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    shell32 = ctypes.windll.shell32

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE

    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalSize.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalSize.restype = ctypes.c_size_t

    shell32.DragQueryFileW.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        wintypes.LPWSTR,
        wintypes.UINT,
    ]
    shell32.DragQueryFileW.restype = wintypes.UINT

    _API_CONFIGURED = True


def _open_clipboard() -> bool:
    return bool(ctypes.windll.user32.OpenClipboard(None))


def _read_hdrop_images() -> list[ClipboardImage]:
    handle = ctypes.windll.user32.GetClipboardData(_CF_HDROP)
    if not handle:
        return []

    count = ctypes.windll.shell32.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
    images: list[ClipboardImage] = []
    for index in range(count):
        length = ctypes.windll.shell32.DragQueryFileW(handle, index, None, 0)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.shell32.DragQueryFileW(handle, index, buffer, length + 1)
        path = Path(buffer.value)
        if not path.is_file():
            continue

        try:
            data = path.read_bytes()
        except OSError:
            continue

        if _is_image_bytes(data):
            images.append(ClipboardImage(data, path.name))

    return images


def _read_dib_image() -> bytes:
    handle = ctypes.windll.user32.GetClipboardData(_CF_DIB)
    if not handle:
        raise ClipboardError("无法读取剪贴板图片")

    size = ctypes.windll.kernel32.GlobalSize(handle)
    pointer = ctypes.windll.kernel32.GlobalLock(handle)
    if not pointer:
        raise ClipboardError("无法锁定剪贴板图片内存")

    try:
        dib = ctypes.string_at(pointer, size)
    finally:
        ctypes.windll.kernel32.GlobalUnlock(handle)

    return _dib_to_bmp(dib)


def _dib_to_bmp(dib: bytes) -> bytes:
    if len(dib) < 40:
        raise ClipboardError("剪贴板图片数据不完整")

    header_size = struct.unpack_from("<I", dib, 0)[0]
    bit_count = struct.unpack_from("<H", dib, 14)[0]
    compression = struct.unpack_from("<I", dib, 16)[0]
    colors_used = struct.unpack_from("<I", dib, 32)[0] if header_size >= 40 else 0

    palette_size = 0
    if bit_count <= 8:
        palette_size = 4 * (colors_used or (1 << bit_count))

    masks_size = 12 if header_size == 40 and compression in {_BI_BITFIELDS, _BI_ALPHABITFIELDS} else 0
    pixel_offset = 14 + header_size + masks_size + palette_size
    file_size = 14 + len(dib)
    file_header = b"BM" + struct.pack("<IHHI", file_size, 0, 0, pixel_offset)
    return file_header + dib


def _write_hdrop(paths: list[Path]) -> None:
    existing = [path for path in paths if path.is_file()]
    if not existing:
        raise ClipboardError("没有可复制的输出文件")

    payload = ("\0".join(str(path) for path in existing) + "\0\0").encode("utf-16le")
    header = struct.pack("<IiiII", _DROPFILES_HEADER_SIZE, 0, 0, 0, 1)
    handle = _global_alloc_bytes(header + payload)
    if not ctypes.windll.user32.SetClipboardData(_CF_HDROP, handle):
        raise ClipboardError("写入多图剪贴板失败")


def _global_alloc_bytes(data: bytes) -> int:
    handle = ctypes.windll.kernel32.GlobalAlloc(_GHND | _GMEM_MOVEABLE, len(data))
    if not handle:
        raise ClipboardError("无法分配剪贴板内存")

    pointer = ctypes.windll.kernel32.GlobalLock(handle)
    if not pointer:
        raise ClipboardError("无法锁定剪贴板内存")

    try:
        ctypes.memmove(pointer, data, len(data))
    finally:
        ctypes.windll.kernel32.GlobalUnlock(handle)

    return handle


def _is_image_bytes(data: bytes) -> bool:
    try:
        with Image.open(_bytes_io(data)) as image:
            image.verify()
    except Exception:
        return False
    return True


def _bytes_io(data: bytes):
    import io

    return io.BytesIO(data)
