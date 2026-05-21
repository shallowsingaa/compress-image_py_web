# 项目上下文

本文件定义项目内常用术语，帮助维护者和 agent 使用一致语言。

## 核心术语

- **共享压缩核心**：`compress_core.py`，负责 Pillow 图片读取、尺寸约束、候选生成、评分和输出字节。
- **批量压缩流程**：`batch_compress.py`，负责把多张输入图片逐个送入共享压缩核心，并把成功结果或中文错误归一成逐文件结果。
- **Python CLI**：`main.py`，面向本地命令行；支持文件路径输入和 Windows 剪贴板模式。
- **Windows 剪贴板模式**：`main.py --clipboard` 通过 `clipboard_io.py` 读取 `CF_HDROP` 文件列表或 `CF_DIB` 截图位图，压缩后把输出文件列表写回剪贴板。
- **FastAPI 后端**：`app.py`，提供 `/api/jobs` 批处理任务、轮询和下载接口；任务和压缩结果只保存在进程内存。
- **后端任务存储**：`job_store.py`，负责 FastAPI 后端的内存任务状态、逐文件状态流转、下载数据查找和响应序列化。
- **Vite 前端**：`web/`，提供中文批量上传、拖拽、桌面粘贴、轮询结果、逐个下载和 ZIP 下载。
- **npm 包**：`package/`，发布名 `compress-img-cli`，安装后命令名 `compress-img`。
- **平台二进制**：PyInstaller 生成的 `package/resources/win/compress-image.exe` 和 `package/resources/linux/compress-image`；属于发布产物，不提交到 git。
- **Windows Alt+E 热键助手**：`scripts/install-compress-img-hotkey/`，安装常驻热键程序 `CompressImgHotkey.exe`，通过计划任务 `CompressImgClipboard` 以最高权限运行脚本顶部 `$TaskCommand` 指定的 `compress-img` 命令。
- **部署脚本**：`Linux/auto_sync_build_run.sh`，用于 Gitee + 1Panel/OpenResty 风格的服务器自动同步、构建和启动。

## 设计边界

- 新增或修改压缩参数时，先改 `CompressOptions` 和 `compress_core.py`，再同步 CLI、API、前端类型和文档。
- 批量处理的逐文件成功/失败语义放在 `batch_compress.py`，CLI 剪贴板模式和 FastAPI 后端应复用它。
- FastAPI 任务状态流转放在 `job_store.py`，`app.py` 路由应只负责 HTTP 参数、状态码和响应类型。
- API 响应字段名要稳定；`web/src/types.ts` 定义前端使用的响应字段。
- 前端默认请求同源 `/api`；只有设置 `VITE_API_BASE_URL` 时才请求指定后端源。
- npm 发布前必须先生成二进制并运行 `npm pack --dry-run`。
- Linux 和 Web 的剪贴板能力不同，不要把 Windows CLI 剪贴板模式误写成跨平台能力。
- Windows Alt+E 热键助手的当前计划任务名是 `CompressImgClipboard`；重新安装应更新它而不是清理它，只清理旧任务名。

## 面向读者的入口

- 项目总览：`README.md`
- 架构：`docs/architecture.md`
- API：`docs/api.md`
- 部署运维：`docs/deployment.md`
- npm 包分发：`docs/npm-package.md`
- npm 用户文档：`package/README.md`
- npm 发布文档：`package/PUBLISHING.md`
- Windows Alt+E 热键安装：`scripts/install-compress-img-hotkey/README.md`
