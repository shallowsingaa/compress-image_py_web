# 图片批量压缩网页版

面向中文用户的本地图片批量压缩工具。项目同时提供：

- FastAPI + Pillow 后端，负责批量任务、压缩、单文件下载和 ZIP 下载。
- Vite + React + TypeScript 前端，负责上传、参数配置、进度轮询和下载入口。
- Python CLI，复用同一套 `compress_core.py` 压缩逻辑。
- Linux 自动同步、构建、启动和发布脚本。

## 目录结构

```text
.
├── app.py                       # FastAPI API 与内存任务队列
├── compress_core.py             # CLI 和 API 共用的压缩核心
├── main.py                      # 命令行入口
├── tests/                       # Python 单元和 API 测试
├── web/                         # React 前端
├── Linux/auto_sync_build_run.sh # Gitee 同步部署脚本
└── docs/                        # 架构、API、部署说明
```

## 安装

Python 依赖：

```powershell
python -m pip install -r requirements.txt
```

前端依赖：

```powershell
cd web
cmd /c npm install
```

## 本地启动

后端：

```powershell
uvicorn app:app --reload --host 127.0.0.1 --port 8793
```

前端开发服务器：

```powershell
cd web
$env:VITE_API_BASE_URL='http://127.0.0.1:8793'
cmd /c npm run dev
```

前端默认端口是 `8792`。如果不设置 `VITE_API_BASE_URL`，前端会请求同源 `/api`，这通常只适合已经配置反向代理的生产环境。

## 命令行压缩

```powershell
python main.py assets/example.png --target-kb 80 --max-side 1300
python main.py assets/example.png --format auto --aggressive
python main.py assets/example.png -o outputs/example.webp --format webp
```

CLI 和 Web API 都使用 `compress_core.py`，所以压缩参数和候选选择策略保持一致。

## 测试和构建

```powershell
pytest
cd web
cmd /c npm run build
```

## 文档

- [架构说明](docs/architecture.md)
- [API 参考](docs/api.md)
- [部署和运维](docs/deployment.md)
