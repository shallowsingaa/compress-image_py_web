# npm 包分发说明

本文档说明 `compress-img-cli` 的 npm 分发形态，面向维护者和接手项目的开发者。普通用户请优先阅读 `package/README.md`。

## 目标

让用户通过 npm 全局安装命令行工具：

```bash
npm install -g compress-img-cli
compress-img --help
```

用户不需要手动安装 Python、Pillow 或 PyInstaller。维护者在发布前负责把 Python CLI 打包成平台二进制。

## 包名和命令名

| 项 | 值 |
| --- | --- |
| npm 包名 | `compress-img-cli` |
| 全局命令 | `compress-img` |
| npm 包根目录 | `package/` |
| Node 启动器 | `package/bin/compress-image.js` |
| postinstall 检查 | `package/bin/verify-platform.js` |

`compress-image` 仍然是内部 PyInstaller 输出文件名；用户面对的是 `compress-img` 命令。

## 发布包结构

```text
package/
├── bin/
│   ├── compress-image.js
│   └── verify-platform.js
├── resources/
│   ├── win/compress-image.exe
│   └── linux/compress-image
├── README.md
├── HELP.md
├── PUBLISHING.md
├── CHANGELOG.md
├── SUPPORT.md
├── SECURITY.md
├── LICENSE
├── index.js
└── package.json
```

`resources/` 不提交到 git，但必须进入 npm tarball。发布前用：

```bash
npm pack --dry-run
```

确认 tarball 中包含 `resources/win/compress-image.exe` 和 `resources/linux/compress-image`。

## 构建流程

Windows:

```powershell
cd package
npm run build:win
```

Linux:

```bash
cd package
npm run build:linux
```

两个脚本都会调用 `scripts/build/` 下的 PyInstaller spec，并把产物复制到 `package/resources/`。

## 运行流程

1. 用户执行 `compress-img ...`。
2. npm 实际启动 `package/bin/compress-image.js`。
3. Node 启动器用 `os.platform()` 判断平台。
4. Windows 启动 `resources/win/compress-image.exe`。
5. Linux 启动 `resources/linux/compress-image`。
6. 原始命令行参数完整转交给 Python CLI。

## 发布流程

1. 在 Windows 构建 Windows 二进制。
2. 在 Linux 构建 Linux 二进制。
3. 回到 `package/` 检查 `npm pack --dry-run`。
4. 如需升版本，执行 `npm version patch --no-git-tag-version` 或指定版本。
5. 使用 2FA OTP 或 npm granular access token 发布。
6. 发布后执行 `npm view compress-img-cli version` 和全局安装冒烟测试。

详细命令见 `package/PUBLISHING.md`。

## 常见故障

### postinstall 警告缺少平台捆绑包

说明发布 tarball 里没有包含当前平台的二进制。重新构建对应平台，并用 `npm pack --dry-run` 检查。

### `npm publish` 返回 403 和 2FA 提示

npm 账号要求发布 2FA。使用：

```bash
npm publish --otp=你的6位验证码
```

或者配置允许 bypass 2FA 的 granular access token。不要把 token 提交到仓库。

### Linux 上 `--clipboard` 不工作

这是当前设计限制。Linux 文件路径压缩可用，剪贴板模式会返回友好错误。
