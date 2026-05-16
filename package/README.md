# image-compress-cli

小而强的图片可控压缩工具 CLI 版。

在线体验：ci.clicli.asia

## 安装

```bash
npm install -g image-compress-cli
```

## 使用

```bash
compress-image input.png
compress-image -o output.webp input.png
compress-image --clipboard
compress-image --target-kb 50 --aggressive input.png
```

## 平台支持

- Windows: 完整支持，包括剪贴板功能
- macOS/Linux: 完整支持，剪贴板功能禁用

## 构建

```bash
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux
npm run build:all    # 全部平台
```