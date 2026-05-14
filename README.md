# 图片批量压缩网页版

面向中文用户的图片批量压缩工具，后端使用 FastAPI + Pillow，前端使用 Vite + React + TypeScript。

## 安装

```powershell
python -m pip install -r requirements.txt
cd web
cmd /c npm install
```

## 启动

后端：

```powershell
uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd web
cmd /c npm run dev
```

默认前端会请求 `http://127.0.0.1:8000`。如需修改 API 地址，设置 `VITE_API_BASE_URL`。

## 命令行压缩

原有 CLI 仍可使用：

```powershell
python main.py assets/example.png --target-kb 80 --max-side 1300
```

## 测试

```powershell
pytest
cd web
cmd /c npm run build
```
