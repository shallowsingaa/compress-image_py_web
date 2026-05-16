# npm 分发实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Python CLI 工具通过 npm 全局包分发，用户只需 `npm install -g image-compress-cli` 即可使用。

**Architecture:** Node.js 启动器检测平台并调用 PyInstaller 捆绑的 Python 可执行文件，实现真正的零配置跨平台分发。仅支持 Windows 和 Linux。

**Tech Stack:** Node.js (CLI 启动器), Python (核心逻辑), PyInstaller (捆绑)

---

## 文件结构

```
compress-image-py-web/
├── package/                      # npm 包根目录
│   ├── bin/
│   │   └── compress-image.js     # CLI 入口（新建）
│   ├── index.js                  # require() 入口（新建）
│   ├── package.json              # npm 包配置（新建）
│   └── resources/                 # 平台相关捆绑包
│       ├── win/
│       │   └── compress-image.exe
│       └── linux/
│           └── compress-image
├── scripts/
│   └── build/
│       ├── win.ps1               # Windows 构建脚本（新建）
│       ├── linux.sh              # Linux 构建脚本（新建）
│       ├── win.spec              # PyInstaller spec（新建）
│       └── linux.spec            # PyInstaller spec（新建）
├── main.py                       # Python CLI 入口
├── compress_core.py              # 压缩核心
└── clipboard_io.py               # 剪贴板实现
```

---

## Task 1: 创建 package/ 目录结构

**Files:**
- Create: `package/package.json`
- Create: `package/bin/compress-image.js`
- Create: `package/index.js`
- Create: `package/bin/verify-platform.js`
- Create: `package/README.md`

- [ ] **Step 1: 创建 package/bin/ 目录**

Run: `mkdir -p package/bin package/resources`

- [ ] **Step 2: 创建 package/package.json**

```json
{
  "name": "image-compress-cli",
  "version": "1.0.0",
  "description": "小而强的图片可控压缩工具 CLI 版，在线体验：ci.clicli.asia",
  "bin": {
    "compress-image": "./bin/compress-image.js"
  },
  "files": [
    "bin/",
    "resources/"
  ],
  "os": [ "win32", "linux" ],
  "engines": { "node": ">=16" },
  "scripts": {
    "postinstall": "node bin/verify-platform.js"
  }
}
```

Run: Write to `package/package.json`

- [ ] **Step 3: 创建 package/bin/compress-image.js**

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

Run: Write to `package/bin/compress-image.js`

- [ ] **Step 4: 创建 package/index.js**

```javascript
module.exports = {
  version: '1.0.0',
  description: '小而强的图片可控压缩工具 CLI 版，在线体验：ci.clicli.asia',
};
```

Run: Write to `package/index.js`

- [ ] **Step 5: 创建 package/bin/verify-platform.js**

```javascript
const { platform } = require('os');
const path = require('path');
const fs = require('fs');

const RESOURCE_MAP = {
  win32: { dir: 'win', exe: 'compress-image.exe' },
  linux: { dir: 'linux', exe: 'compress-image' },
};

const { dir, exe } = RESOURCE_MAP[platform()] ?? {};
if (!dir) {
  console.error(`不支持的平台: ${platform()}`);
  process.exit(1);
}

const resourcePath = path.join(__dirname, '..', 'resources', dir, exe);
if (!fs.existsSync(resourcePath)) {
  console.error(`警告：未找到 ${platform()} 平台的捆绑包。CLI 可能无法正常工作。`);
  console.error(`期望路径: ${resourcePath}`);
}
```

Run: Write to `package/bin/verify-platform.js`

- [ ] **Step 6: 创建 package/README.md**

```markdown
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

- **Windows**: 完整支持，包括剪贴板功能
- **Linux**: 完整支持，剪贴板功能禁用

## 构建

```bash
npm run build:win    # Windows
npm run build:linux  # Linux
npm run build:all    # 全部平台
```
```

Run: Write to `package/README.md`

- [ ] **Step 7: 提交**

Run:
```bash
git add package/bin/compress-image.js package/index.js package/package.json package/bin/verify-platform.js package/README.md
git commit -m "feat(npm): initial npm package structure"
```

---

## Task 2: 创建构建脚本目录和平台 PyInstaller specs

**Files:**
- Create: `scripts/build/` 目录
- Create: `scripts/build/win.ps1`
- Create: `scripts/build/linux.sh`
- Create: `scripts/build/win.spec`
- Create: `scripts/build/linux.spec`

- [ ] **Step 1: 创建 scripts/build/ 目录**

Run: `mkdir -p scripts/build`

- [ ] **Step 2: 创建 scripts/build/win.ps1**

```powershell
#!/usr/bin/env pwsh
# Build Windows executable using PyInstaller

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PackageDir = Join-Path $ProjectRoot "package"
$ResourcesDir = Join-Path $PackageDir "resources\win"
$SpecFile = Join-Path $PSScriptRoot "win.spec"

# Ensure resources directory exists
New-Item -ItemType Directory -Force -Path $ResourcesDir | Out-Null

# Install pyinstaller if not present
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    pip install pyinstaller
}

# Run PyInstaller
Push-Location $PSScriptRoot
try {
    pyinstaller --clean $SpecFile
    $OutputExe = Join-Path $PSScriptRoot "dist\compress-image.exe"
    if (Test-Path $OutputExe) {
        Copy-Item $OutputExe -Destination $ResourcesDir -Force
        Write-Host "Windows build complete: $ResourcesDir\compress-image.exe"
    } else {
        throw "PyInstaller did not produce expected output"
    }
} finally {
    Pop-Location
}
```

Run: Write to `scripts/build/win.ps1`

- [ ] **Step 3: 创建 scripts/build/linux.sh**

```bash
#!/bin/bash
# Build Linux executable using PyInstaller

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGE_DIR="$PROJECT_ROOT/package"
RESOURCES_DIR="$PACKAGE_DIR/resources/linux"
SPEC_FILE="$SCRIPT_DIR/linux.spec"

mkdir -p "$RESOURCES_DIR"

if ! command -v pyinstaller &> /dev/null; then
    pip install pyinstaller
fi

cd "$SCRIPT_DIR"
pyinstaller --clean "$SPEC_FILE"

OUTPUT_BIN="$SCRIPT_DIR/dist/compress-image"
if [ -f "$OUTPUT_BIN" ]; then
    cp "$OUTPUT_BIN" "$RESOURCES_DIR/"
    chmod +x "$RESOURCES_DIR/compress-image"
    echo "Linux build complete: $RESOURCES_DIR/compress-image"
else
    echo "Error: PyInstaller did not produce expected output" >&2
    exit 1
fi
```

Run: Write to `scripts/build/linux.sh`

- [ ] **Step 4: 创建 scripts/build/win.spec**

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

a = Analysis(
    ['../../main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'packaging', 'colorama'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.binaries, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='compress-image',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    preferred_encoding='UTF-8',
)
```

Run: Write to `scripts/build/win.spec`

- [ ] **Step 5: 创建 scripts/build/linux.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['../../main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['PIL', 'packaging', 'colorama'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.binaries, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='compress-image',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    preferred_encoding='UTF-8',
)
```

Run: Write to `scripts/build/linux.spec`

- [ ] **Step 6: 提交**

Run:
```bash
git add scripts/build/
git commit -m "feat(build): add PyInstaller build scripts for Win/Linux"
```

---

## Task 3: 添加 npm 构建命令到 package.json

**Files:**
- Modify: `package/package.json`

- [ ] **Step 1: 更新 package.json 添加构建脚本**

```json
{
  "name": "image-compress-cli",
  "version": "1.0.0",
  "description": "小而强的图片可控压缩工具 CLI 版，在线体验：ci.clicli.asia",
  "bin": {
    "compress-image": "./bin/compress-image.js"
  },
  "files": [
    "bin/",
    "resources/"
  ],
  "os": [ "win32", "linux" ],
  "engines": { "node": ">=16" },
  "scripts": {
    "postinstall": "node bin/verify-platform.js",
    "build:win": "pwsh scripts/build/win.ps1",
    "build:linux": "bash scripts/build/linux.sh",
    "build:all": "npm run build:win && npm run build:linux"
  }
}
```

Run: Edit `package/package.json`, replace the entire content with the above.

- [ ] **Step 2: 提交**

Run:
```bash
git add package/package.json
git commit -m "feat(npm): add build scripts to package.json"
```

---

## Task 4: 添加 .gitignore 规则

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: 添加 npm 打包和构建产物目录到 .gitignore**

Add to `.gitignore`:
```
# npm package
package/node_modules/
package/resources/
scripts/build/dist/
scripts/build/build/
*.spec.ejs
```

Run: Read `.gitignore`, then edit it.

- [ ] **Step 2: 提交**

Run:
```bash
git add .gitignore
git commit -m "chore: add npm build artifacts to gitignore"
```

---

## Task 5: 验证清单（人工验证）

此任务不需要代码修改，需要在构建完成后人工验证。

---

## 验证清单（详细）

### 构建验证

**Windows 构建验证：**
- [ ] 确保已安装 PyInstaller：`pip install pyinstaller`
- [ ] 运行 `npm run build:win`
- [ ] 检查 `package/resources/win/compress-image.exe` 存在
- [ ] 检查文件大小合理（通常 50-80MB）

**Linux 构建验证（在 Linux 机器上）：**
- [ ] 确保已安装 PyInstaller：`pip install pyinstaller`
- [ ] 运行 `npm run build:linux`
- [ ] 检查 `package/resources/linux/compress-image` 存在
- [ ] 检查文件有执行权限：`ls -la package/resources/linux/compress-image`

### 功能验证

**Windows 功能验证：**
- [ ] 运行 `compress-image --help`，确认输出正常
- [ ] 确认中文帮助信息无乱码
- [ ] 运行 `compress-image assets/000.jpg`，确认压缩功能正常
- [ ] 运行 `compress-image --clipboard`，确认剪贴板功能正常

**Linux 功能验证：**
- [ ] 运行 `compress-image --help`，确认输出正常
- [ ] 确认中文帮助信息无乱码
- [ ] 运行 `compress-image assets/000.jpg`，确认压缩功能正常
- [ ] 运行 `compress-image --clipboard`，确认输出友好提示："剪贴板功能在 Linux 上暂不可用"

### npm 发布验证

- [ ] `cd package && npm publish --dry-run` 无报错
- [ ] 检查 package.json 的 description、bin、files、os 字段正确

### 代码完整性检查

- [ ] `package/bin/compress-image.js` 不包含 darwin 引用
- [ ] `package/bin/verify-platform.js` 不包含 darwin 引用
- [ ] `package/package.json` 的 `os` 字段为 `["win32", "linux"]`
- [ ] `package/README.md` 无 macOS 相关描述
- [ ] `scripts/build/` 目录不包含 mac.sh 或 mac.spec