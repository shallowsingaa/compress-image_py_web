# 图片批量压缩工具

以文字为主的图片（文档截图、表单、证书等）批量压缩工具，提供 CLI 和网页版两种使用方式。CLI 在 Windows 上还支持直接处理剪贴板图片。

## 目录

- [命令行版](#命令行版)
- [网页版](#网页版)
- [项目结构](#项目结构)
- [文档索引](#文档索引)
- [API 参考](#api-参考)
- [本地开发](#本地开发)
- [测试](#测试)

---

## 命令行版

### npm 全局安装

如果只需要命令行压缩工具，推荐直接安装 npm 包：

```bash
npm install -g compress-img-cli
compress-img --help
```

该方式会安装预打包好的 Windows / Linux 可执行文件，用户无需手动安装 Python 依赖。npm 包的详细说明见 [`package/README.md`](package/README.md)，发布流程见 [`package/PUBLISHING.md`](package/PUBLISHING.md)。

### 安装依赖

从源码运行 `main.py` 时再安装 Python 依赖：

```bash
python -m pip install -r requirements.txt
```

### 基本用法

```bash
python main.py 输入图片.png
```

Windows 剪贴板模式：

```bash
python main.py --clipboard
python main.py --clipboard -o outputs/from_clipboard --format png
```

剪贴板模式会读取截图图片，或读取在资源管理器中复制的一张或多张图片文件。压缩结果会保存到 `outputs/clipboard/`；如果 `-o` 指向目录，则保存到该目录下的 `clipboard/`；如果 `-o` 指向文件名，则保存到该文件所在目录下的 `clipboard/`。处理成功后，CLI 会把压缩后的输出文件作为一组文件复制回 Windows 剪贴板。

### 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `input` | 无 | 输入图片路径；使用 `--clipboard` 时可省略 |
| `--clipboard` | `false` | Windows 专用：从剪贴板读取图片，处理成功后复制结果回剪贴板 |
| `--target-kb` | `80` | 目标文件体积（KB），尽量不超过此值 |
| `--max-side` | `1300` | 最长边像素上限，不放大原图 |
| `--format` | `jpg` | 输出格式：`auto`/`webp`/`png`/`jpeg`/`jpg` |
| `--min-quality` | `70` | 最低质量，越低文件越小但越容易糊 |
| `--min-long-side` | 无 | 手动指定最低最长边 |
| `--scale-step` | `0.92` | 逐步缩小尺寸的比例，越小尝试越少 |
| `--grayscale` | `false` | 转为灰度图，文档截图通常更小 |
| `--sharpness` | `1.10` | 锐化强度，`1` 为关闭 |
| `--aggressive` | `false` | 激进模式，降低默认最低质量至 30 |

### 输出示例

```bash
python main.py screenshot.png --target-kb 80 --max-side 1300
```

```
处理完成
------------------------------------------------
原始路径：screenshot.png
原始尺寸：1920 x 1080
原始体积：245.7 KB

输出路径：outputs/screenshot.jpg
输出格式：jpg
输出尺寸：1300 x 731
输出体积：76.3 KB
压缩策略：quality=80/lossless=False/format=jpg/w=1300
是否达到 <= 80KB：是
```

### 未能压到目标体积时的建议

```bash
# 1. 使用激进模式
python main.py 输入.png --aggressive

# 2. 转灰度图
python main.py 输入.png --grayscale

# 3. 降低最低质量
python main.py 输入.png --min-quality 30

# 4. 指定输出格式
python main.py 输入.png --format webp -o outputs/result.webp

# 5. 提高目标体积上限
python main.py 输入.png --target-kb 120
```

---

## 网页版

网页版面向在 **Linux 服务器**上部署的场景。通过 `Linux/auto_sync_build_run.sh` 实现代码同步、依赖安装、后端启动、前端构建和产物发布的一键自动化。

### 前端能力

- 多图选择、拖拽上传、桌面端粘贴剪贴板图片批处理。
- 每张图片可单独下载，也可逐个下载全部结果或下载 ZIP。
- 桌面浏览器在压缩完成后会尝试把成功结果复制回剪贴板；若权限或系统限制阻止复制，仍可使用下载入口。

### 部署架构

```
Gitee 仓库
    |
    |  (auto_sync_build_run.sh)
    v
Gitee ---> 触发脚本 ---> 克隆/拉取代码
                              |
                              v
                    Python 依赖 + npm 依赖
                              |
                    +---> uvicorn 后端 (0.0.0.0:8793)
                    |
                    +---> npm run build (web/dist)
                              |
                              v
                    Web 静态文件 ---> 1Panel 站点目录
                                   (ci.clicli.asia)
```

### 环境要求

- Linux 服务器（本文基于 1Panel + 面板管理的站点）
- Python 3.10+
- Node.js 18+ / npm 9+
- git、rsync、flock
- 虚拟环境：`/opt/compress-image/venv`
- 原生依赖需先安装：`pip install pillow` 对应的系统级图像库

### 配置部署脚本

编辑 `Linux/auto_sync_build_run.sh` 顶部配置区：

```bash
# ========== 可修改配置区 ==========

# Gitee HTTPS 仓库地址
REPO_URL="https://gitee.com/shallowspider/compress-image_py_web.git"

# 远程分支
BRANCH="master"

# 本地源码目录（绝对路径）
TARGET_DIR="/opt/compress-image/src"

# Python 依赖安装命令
PYTHON_INSTALL_CMD="/opt/compress-image/venv/bin/pip3 install -r requirements.txt"

# npm 依赖安装命令（生产环境推荐 npm ci）
NPM_INSTALL_CMD="cd web && npm ci"

# npm 构建命令
BUILD_CMD="cd web && npm run build"

# 后端启动命令（常驻后台运行）
AFTER_NPM_INSTALL_CMD="/opt/compress-image/venv/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8793"

# 后端工作目录
AFTER_NPM_INSTALL_WORKDIR="$TARGET_DIR"

# Web 服务目录（1Panel 站点根目录）
WEB_ROOT="/opt/1panel/www/sites/ci.clicli.asia/index"

# ========== 内部参数（通常无需修改）==========

BACKEND_PID_FILE="/tmp/gitee-site-uvicorn.pid"
BACKEND_LOG_FILE="/var/log/gitee-site-uvicorn.log"
LOG_FILE="/var/log/gitee-site-deploy.log"
LOCK_FILE="/tmp/gitee-site-deploy.lock"
BUILD_OUTPUT_DIR="web/dist"
```

### 初始化部署

首次部署时，需在服务器上手动执行以下步骤：

```bash
# 1. 创建必要的目录
sudo mkdir -p /opt/compress-image
sudo mkdir -p /opt/1panel/www/sites/ci.clicli.asia/index
sudo mkdir -p /var/log

# 2. 创建 Python 虚拟环境
python3 -m venv /opt/compress-image/venv

# 3. 安装 Python 依赖
/opt/compress-image/venv/bin/pip3 install -r requirements.txt

# 4. 将部署脚本设为可执行
chmod +x /opt/compress-image/src/Linux/auto_sync_build_run.sh
```

### 启动自动化部署

```bash
# 正常部署（检测到远程有新提交才执行完整流程）
/opt/compress-image/src/Linux/auto_sync_build_run.sh

# 强制重新拉取和构建（跳过远程提交检查）
FORCE=1 /opt/compress-image/src/Linux/auto_sync_build_run.sh
```

### 部署流程说明

脚本自动执行以下步骤：

1. **加锁** — 通过 `flock` 确保同一时间只有一个部署实例运行；若检测到旧进程持有锁，自动释放后重试
2. **检查远程提交** — 对比远程 `master` 分支与本地 `HEAD`，无更新且后端正常运行则直接退出
3. **停止旧后端** — 识别并停止与当前 PID 文件匹配的后端进程（`uvicorn app:app --port 8793`），超时强制 kill
4. **同步代码** — 若本地目录不是目标仓库或远程地址不一致，执行全新克隆；否则强制拉取并重置到 `origin/master`
5. **安装依赖** — 依次执行 Python 依赖安装、npm 依赖安装
6. **启动后端** — 以后台 `nohup` 方式启动 uvicorn，PID 写入 `/tmp/gitee-site-uvicorn.pid`，日志写入 `/var/log/gitee-site-uvicorn.log`
7. **构建前端** — 执行 `npm run build`，产物输出到 `web/dist`
8. **发布产物** — 用 `rsync --delete` 将 `web/dist/` 同步到 `WEB_ROOT`（1Panel 站点目录）

### 日志查看

```bash
# 查看部署日志
tail -f /var/log/gitee-site-deploy.log

# 查看后端运行日志
tail -f /var/log/gitee-site-uvicorn.log

# 查看后端实时输出（启动命令的标准输出和错误）
cat /var/log/gitee-site-uvicorn.log
```

### 服务管理

```bash
# 查看后端进程是否在运行
ps -p $(cat /tmp/gitee-site-uvicorn.pid) 2>/dev/null && echo "运行中" || echo "未运行"

# 手动停止后端
kill $(cat /tmp/gitee-site-uvicorn.pid) 2>/dev/null || true

# 查看端口占用
lsof -i :8793
```

### 故障排查

**症状：后端无法启动**
```bash
# 检查虚拟环境中的 uvicorn 是否可用
/opt/compress-image/venv/bin/python3 -m uvicorn --version

# 查看后端日志
cat /var/log/gitee-site-uvicorn.log
```

**症状：npm install 失败**
```bash
# 检查 Node.js 版本
node --version
npm --version

# 检查 web 目录是否存在 package.json
ls /opt/compress-image/src/web/package.json
```

**症状：rsync 发布失败**
```bash
# 检查目标目录是否存在
ls -d /opt/1panel/www/sites/ci.clicli.asia/index

# 手动执行 rsync 进行调试
rsync -av /opt/compress-image/src/web/dist/ /opt/1panel/www/sites/ci.clicli.asia/index/
```

**症状：部署被锁住，长时间不执行**
```bash
# 查看是否有进程持有部署锁
lsof /tmp/gitee-site-deploy.lock

# 手动删除锁文件（确认没有部署任务在运行后）
rm /tmp/gitee-site-deploy.lock
```

---

## 项目结构

```
.
├── app.py                       # FastAPI 后端（内存任务队列）
├── clipboard_io.py              # Windows 剪贴板图片读写
├── compress_core.py             # CLI 和 API 共用的压缩核心逻辑
├── main.py                      # 命令行入口（文件路径和 Windows 剪贴板模式）
├── package/                     # npm 包 compress-img-cli
│   ├── bin/                     # Node 启动器和安装后检查
│   └── resources/               # 发布前生成的平台二进制（git 忽略）
├── requirements.txt             # Python 依赖
├── scripts/build/               # PyInstaller 构建脚本和 spec
├── tests/                       # Python 单元测试
├── web/                         # React 前端源码
│   ├── src/main.tsx             # 前端入口，API 调用逻辑
│   └── dist/                    # 前端构建产物（npm run build 生成）
├── Linux/
│   └── auto_sync_build_run.sh   # Linux 服务器自动同步部署脚本
└── docs/                        # 项目文档
    ├── architecture.md           # 架构说明
    ├── api.md                    # API 参考
    ├── deployment.md             # 部署和运维
    └── npm-package.md            # npm 包分发说明
```

---

## 文档索引

| 文档 | 读者 | 内容 |
|------|------|------|
| [CONTEXT.md](CONTEXT.md) | 维护者 / agent | 项目术语、边界和入口 |
| [AGENTS.md](AGENTS.md) | agent | 代码约定、验证命令和编辑红线 |
| [docs/architecture.md](docs/architecture.md) | 维护者 | API、前端、CLI、npm 分发的数据流 |
| [docs/api.md](docs/api.md) | API 使用者 | `/api/jobs`、轮询和下载接口 |
| [docs/deployment.md](docs/deployment.md) | 运维 | 本地开发、生产部署和 npm 发布入口 |
| [docs/npm-package.md](docs/npm-package.md) | npm 包维护者 | `compress-img-cli` 架构、构建、发布和故障排查 |
| [package/README.md](package/README.md) | npm 用户 | 安装、使用、平台支持 |
| [package/HELP.md](package/HELP.md) | CLI 用户 | `compress-img` 参数和示例 |
| [package/PUBLISHING.md](package/PUBLISHING.md) | 发布者 | npm 发布 checklist、2FA/token 和回滚 |

---

## API 参考

详见 [docs/api.md](docs/api.md)。

### 端点概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/jobs` | 创建压缩任务（支持多文件） |
| `GET` | `/api/jobs/{job_id}` | 查询任务状态（轮询） |
| `GET` | `/api/jobs/{job_id}/files/{file_id}/download` | 下载单个压缩文件 |
| `GET` | `/api/jobs/{job_id}/download.zip` | 下载全部压缩文件（ZIP） |

### 前端与后端的通信

- 前端默认请求同源 `/api/...`（需配置反向代理）
- 构建时设置 `VITE_API_BASE_URL` 可指定后端地址：
  ```bash
  VITE_API_BASE_URL="https://ci.clicli.asia" npm run build --prefix web
  ```

---

## 本地开发

```bash
# 安装依赖
python -m pip install -r requirements.txt
cd web && npm install

# 启动后端
uvicorn app:app --reload --host 127.0.0.1 --port 8793

# 启动前端（另开终端）
cd web
VITE_API_BASE_URL='http://127.0.0.1:8793' npm run dev
```

前端开发服务器默认端口 `8792`。

---

## 测试

```bash
# Python 测试
pytest

# 前端构建
cd web && npm run build
```
