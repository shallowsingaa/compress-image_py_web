# ADR: 通过 npm 分发 PyInstaller 打包后的 Python CLI

## 状态

Accepted

## 日期

2026-05-16

## 背景

项目已有稳定的 Python CLI 和共享压缩核心。目标是让非 Python 用户也能通过 npm 全局安装命令行工具：

```bash
npm install -g compress-img-cli
compress-img --help
```

用户不应被要求安装 Python、Pillow、PyInstaller 或项目源码。

## 决策

采用 npm 包 + Node 启动器 + PyInstaller 平台二进制的组合：

- npm 包名：`compress-img-cli`
- 用户命令：`compress-img`
- npm 包根目录：`package/`
- Node 启动器：`package/bin/compress-image.js`
- Windows 二进制：`package/resources/win/compress-image.exe`
- Linux 二进制：`package/resources/linux/compress-image`

二进制由维护者在发布前构建，进入 npm tarball，但不提交到 git。

## 后果

好处：

- 用户安装路径简单，只需要 npm。
- Python 压缩逻辑保持单一来源，不需要改写为 Node.js。
- Windows 剪贴板能力可以保留在现有 Python CLI 中。

代价：

- 发布前必须分别构建 Windows 和 Linux 二进制。
- npm 包体积包含两个平台二进制，当前约 34MB。
- macOS 暂不支持。
- 发布验证必须依赖 `npm pack --dry-run` 检查 tarball 内容。

## 验证要求

发布前至少验证：

```bash
cd package
npm pack --dry-run
```

并在对应平台验证：

```bash
compress-img --help
```
