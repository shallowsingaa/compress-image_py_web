# Python CLI 工具通过 npm 分发设计方案

> **Status 2026-05-16:** Implemented as `compress-img-cli` / `compress-img`. Current operational details live in `docs/npm-package.md` and `package/PUBLISHING.md`.

## 1. 目标

将 `compress-image-py-web` 的 Python CLI 工具（`main.py`）通过 npm 全局包分发，用户只需 `npm install -g compress-img-cli` 即可使用 `compress-img` 命令，无需自行安装 Python 环境。

## 2. 整体架构

```
compress-image-py-web/
├── package/
│   ├── bin/
│   │   └── compress-image.js   # Node.js CLI 启动器
│   ├── index.js               # require() 入口
│   ├── package.json
│   └── resources/
│       ├── win/
│       │   └── compress-image.exe  # PyInstaller 捆绑输出
│       └── linux/
│           └── compress-image     # Linux 单文件
├── scripts/
│   └── build/
│       ├── win.ps1            # Windows 构建脚本
│       ├── linux.sh          # Linux 构建脚本
│       ├── win.spec          # PyInstaller spec
│       └── linux.spec        # PyInstaller spec
├── main.py                    # Python CLI 入口（不变）
├── compress_core.py           # 压缩核心（不变）
└── clipboard_io.py           # 平台剪贴板（不变）
```

## 3. Node.js 启动器

`bin/compress-image.js` 是 npm 包入口，负责检测当前平台并调用对应的捆绑可执行文件：

```javascript
#!/usr/bin/env node
const { platform } = require('os');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

const RESOURCE_MAP = {
  win32: { dir: 'win', exe: 'compress-image.exe' },
  linux: { dir: 'linux', exe: 'compress-image' },
};

const { dir, exe } = RESOURCE_MAP[platform()] ?? {};
if (!dir) {
  console.error('不支持的平台:', platform());
  process.exit(1);
}

const executable = path.join(__dirname, '..', 'resources', dir, exe);

if (!fs.existsSync(executable)) {
  console.error(`错误：未找到 ${platform()} 平台的捆绑包。请重新安装。`);
  process.exit(1);
}

const child = spawn(executable, process.argv.slice(2), {
  stdio: 'inherit',
  windowsHide: true,
});

child.on('exit', (code) => process.exit(code ?? 0));
```

## 4. 跨平台剪贴板行为

- **Windows**: `clipboard_io.py` 保持现有实现，通过 PowerShell 调用 Windows 剪贴板 API
- **Linux**: `read_clipboard_images()` 抛出 `ClipboardError`，CLI 捕获后输出友好提示：
  ```
  警告：剪贴板功能在 Linux 上暂不可用。
  ```

## 5. PyInstaller 打包

每个平台使用独立的 `*.spec` 文件，配置 `onefile=True` 生成单一可执行文件：

- Windows: `scripts/build/win.spec` → `resources/win/compress-image.exe`
- Linux: `scripts/build/linux.spec` → `resources/linux/compress-image`

关键配置：
- `onefile=True`: 单文件输出，用户无需安装
- `hiddenimports`: `PIL` 和 `packaging`
- `preferred_encoding='UTF-8'`: 确保中文输出正常

## 6. package.json 核心字段

```json
{
  "name": "compress-img-cli",
  "version": "1.0.0",
  "description": "小而强的图片可控压缩工具 CLI 版，在线体验：ci.clicli.asia",
  "bin": {
    "compress-img": "./bin/compress-image.js"
  },
  "files": [
    "bin/",
    "resources/"
  ],
  "os": [ "win32", "linux" ],
  "engines": { "node": ">=16" }
}
```

## 7. 构建与发布流程

### 构建命令

| 命令 | 说明 |
|------|------|
| `npm run build:win` | Windows: 运行 `scripts/build/win.ps1` |
| `npm run build:linux` | Linux: 运行 `scripts/build/linux.sh` |
| `npm run build:all` | Windows + Linux 顺序构建 |

### 发布流程

1. 在对应平台运行构建命令，生成 `resources/*/` 下的可执行文件
2. 测试各平台可执行文件正常运行
3. 提交代码，git tag 打版本
4. `npm pack --dry-run` 确认两个平台二进制和文档都在 tarball 中
5. `npm publish` 发布到 npm

### 用户使用

```bash
npm install -g compress-img-cli

compress-img input.png
compress-img -o output.webp input.png
compress-img --clipboard
compress-img --target-kb 50 --aggressive input.png
```

## 8. 不纳入的范围

- macOS 支持
- Python 重写为 Node.js（方案 B 未采纳）
- Web 前端部分（仅 CLI 分发）
- API 服务部分

## 9. 验证清单

- [ ] Windows: `npm run build:win` 成功，`package/resources/win/compress-image.exe` 存在
- [ ] Linux: 在 Linux 平台上运行 `npm run build:linux`，产物存在于 `package/resources/linux/`
- [ ] Windows: `compress-img --help` 正常输出
- [ ] Windows: `compress-img <test-image.png>` 确认压缩功能正常
- [ ] Linux: `compress-img --help` 正常输出，剪贴板功能显示友好提示
- [ ] 中文输出正常，无乱码
- [ ] `npm install -g` 安装后 CLI 命令可用
- [ ] `npm publish --dry-run` 无报错
