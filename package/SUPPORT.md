# 支持说明

## 适用范围

`compress-img-cli` 支持：

- Windows
- Linux

当前不支持 macOS。

## 提交问题前请准备

请尽量提供以下信息：

- 操作系统和版本
- Node.js 版本：`node -v`
- npm 版本：`npm -v`
- 包版本：`npm view compress-img-cli version`
- 命令输出：`compress-img --help`
- 出错命令和完整错误信息
- 可复现的输入图片类型和参数

## 常见自查

重新安装：

```bash
npm uninstall -g compress-img-cli
npm install -g compress-img-cli
```

确认命令是否在 PATH 中：

```bash
compress-img --help
```

如果安装后提示缺少平台捆绑包，说明发布包可能缺少对应二进制。请联系维护者重新发布。
