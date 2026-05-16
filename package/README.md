# compress-img-cli

小而强的图片压缩命令行工具。它把 compress-image_py_web 项目的 Python 压缩核心预打包成 Windows / Linux 可执行文件，再通过 npm 分发；安装后无需用户单独安装 Python、Pillow 或 PyInstaller。

在线体验：<https://ci.clicli.asia>

## 安装

```bash
npm install -g compress-img-cli
```

安装后终端命令为：

```bash
compress-img --help
```

## 快速使用

```bash
compress-img input.png
compress-img -o output.webp input.png
compress-img --target-kb 50 --aggressive input.png
compress-img --grayscale --format jpg input.png
```

Windows 剪贴板模式：

```bash
compress-img --clipboard
compress-img --clipboard -o outputs/from_clipboard --format png
```

## 常用参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `input` | 无 | 输入图片路径；使用 `--clipboard` 时可省略 |
| `-o, --output` | 自动生成 | 输出文件路径或目录 |
| `--target-kb` | `80` | 目标体积 KB，尽量压到此值以内 |
| `--max-side` | `1300` | 最长边像素上限，不放大原图 |
| `--format` | `jpg` | 输出格式：`auto` / `webp` / `png` / `jpeg` / `jpg` |
| `--min-quality` | `70` | WebP/JPEG 最低质量 |
| `--min-long-side` | 无 | 手动指定最低最长边 |
| `--scale-step` | `0.92` | 每轮缩小比例，越小尝试越少 |
| `--grayscale` | `false` | 转为灰度图 |
| `--sharpness` | `1.10` | 轻微锐化强度，设为 `1` 可关闭 |
| `--aggressive` | `false` | 更激进地追求小体积 |
| `--clipboard` | `false` | Windows 专用：读取剪贴板图片或文件列表 |

更完整的帮助见 [HELP.md](./HELP.md)。

## 平台支持

| 平台 | 状态 | 说明 |
|------|------|------|
| Windows | 支持 | 包含 `resources/win/compress-image.exe`，支持剪贴板模式 |
| Linux | 支持 | 包含 `resources/linux/compress-image`，剪贴板模式会给出友好提示 |
| macOS | 暂不支持 | 当前 npm 包声明只支持 `win32` 和 `linux` |

## 发布包内容

npm 包通过 `files` 字段只发布必要文件：

```text
bin/
resources/
HELP.md
PUBLISHING.md
CHANGELOG.md
README.md
LICENSE
package.json
```

其中 `resources/` 下的二进制文件不纳入 git 管理，但发布前必须先构建出来，否则用户安装后无法运行。

## 从源码构建发布包

Windows:

```powershell
cd package
npm run build:win
npm pack --dry-run
```

Linux:

```bash
cd package
npm run build:linux
npm pack --dry-run
```

完整发布流程见 [PUBLISHING.md](./PUBLISHING.md)。

## 许可证

MIT。详见 [LICENSE](./LICENSE)。
