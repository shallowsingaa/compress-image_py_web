# compress-img 帮助文档

`compress-img` 是 `compress-img-cli` 安装后的全局命令，用于压缩以文字为主的图片，例如文档截图、表单截图、证书、聊天记录截图等。

## 基本语法

```bash
compress-img [input] [options]
```

`input` 是输入图片路径。使用 Windows 剪贴板模式时可以省略：

```bash
compress-img --clipboard
```

## 命令示例

压缩单张图片，输出到默认 `outputs/` 目录：

```bash
compress-img screenshot.png
```

指定输出文件：

```bash
compress-img screenshot.png -o output.webp --format webp
```

尽量压到 50KB：

```bash
compress-img screenshot.png --target-kb 50
```

更激进地压缩：

```bash
compress-img screenshot.png --target-kb 50 --aggressive
```

文档截图转灰度：

```bash
compress-img screenshot.png --grayscale
```

Windows 剪贴板输入：

```bash
compress-img --clipboard
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `-h, --help` | 显示命令行帮助 |
| `input` | 输入图片路径；使用 `--clipboard` 时可省略 |
| `-o, --output` | 输出文件路径或目录；不填则自动生成 |
| `--clipboard` | Windows 专用：从剪贴板读取图片或复制的图片文件，处理成功后把结果文件复制回剪贴板 |
| `--max-side <number>` | 最长边上限，默认 `1300`，不会放大原图 |
| `--target-kb <number>` | 目标体积 KB，默认 `80` |
| `--min-quality <number>` | WebP/JPEG 最低质量，默认 `70` |
| `--min-long-side <number>` | 手动指定最低最长边；默认不限制，原图更小时不放大 |
| `--scale-step <number>` | 逐步缩小尺寸的比例，默认 `0.92` |
| `--format <format>` | 输出格式：`auto`、`webp`、`png`、`jpeg`、`jpg`；默认 `jpg` |
| `--grayscale` | 转为灰度图，文档截图通常更小，但会丢失颜色 |
| `--sharpness <number>` | 轻微锐化强度，默认 `1.10`；设为 `1` 可关闭 |
| `--aggressive` | 更激进地追求小体积，会降低默认最低质量 |

## 输出位置规则

- 未指定 `-o` 时，输出文件会自动生成到默认输出目录。
- `-o` 指向文件时，使用该文件路径。
- `-o` 指向目录时，在该目录下生成输出文件。
- `--clipboard` 模式下，如果 `-o` 指向目录，会在该目录下创建 `clipboard/` 子目录保存结果。

## 常见问题

### 安装后提示找不到平台捆绑包

说明 npm 包里缺少当前平台的二进制文件。发布者需要先运行对应构建命令，再执行 `npm publish`：

```bash
npm run build:win
npm run build:linux
npm pack --dry-run
```

### Linux 上能使用剪贴板模式吗？

当前不能。Linux 可正常压缩文件路径输入，但 `--clipboard` 会提示剪贴板功能暂不可用。

### 什么时候用 `--aggressive`？

当默认参数无法压到目标体积，或者你明确更看重小体积而不是画质时使用。

### 输出格式应该选什么？

- `jpg`：默认选择，适合截图和普通图片。
- `webp`：通常更小，但部分旧系统兼容性较弱。
- `png`：适合必须保留无损 PNG 的场景，体积可能更大。
- `auto`：优先根据输出路径后缀决定格式。
