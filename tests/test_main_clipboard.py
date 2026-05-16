from __future__ import annotations

import io

from PIL import Image

import main


def make_image_bytes(fmt: str = "PNG") -> bytes:
    image = Image.new("RGB", (180, 120), "#ffffff")
    for x in range(12, 168, 16):
        for y in range(12, 108, 18):
            image.putpixel((x, y), (10, 10, 10))

    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def test_clipboard_mode_processes_all_images_and_writes_outputs(tmp_path, monkeypatch, capsys) -> None:
    copied: list[tuple[bytes, str, str]] = []

    monkeypatch.setattr(
        main,
        "read_clipboard_images",
        lambda: [
            main.ClipboardImage(make_image_bytes(), "clip-one.png"),
            main.ClipboardImage(make_image_bytes(), "clip-two.png"),
        ],
    )
    monkeypatch.setattr(main, "write_clipboard_images", lambda items: copied.extend(items))

    exit_code = main.main(["--clipboard", "-o", str(tmp_path), "--format", "png", "--target-kb", "80"])

    assert exit_code == 0
    assert len(copied) == 2
    assert all(data for data, _filename, _mime in copied)
    assert sorted(path.name for path in (tmp_path / "clipboard").iterdir()) == [
        "clip-one_compressed.png",
        "clip-two_compressed.png",
    ]
    assert all(path.parent == tmp_path / "clipboard" for _data, filename, _mime in copied for path in [main.Path(filename)])
    assert all(mime == "image/png" for _data, _filename, mime in copied)
    assert "剪贴板图片：2 张" in capsys.readouterr().out


def test_clipboard_output_path_uses_clipboard_folder_for_output_file(tmp_path) -> None:
    output_file = tmp_path / "ignored-name.webp"

    assert main.clipboard_output_path("clip.png", str(output_file), ".webp") == (
        tmp_path / "clipboard" / "clip_compressed.webp"
    )


def test_clipboard_mode_reports_empty_clipboard(monkeypatch, capsys) -> None:
    monkeypatch.setattr(main, "read_clipboard_images", lambda: [])

    exit_code = main.main(["--clipboard"])

    assert exit_code == 2
    assert "剪贴板中没有可用图片" in capsys.readouterr().err


def test_cli_requires_input_without_clipboard(capsys) -> None:
    exit_code = main.main([])

    assert exit_code == 2
    assert "请提供输入图片路径，或使用 --clipboard" in capsys.readouterr().err
