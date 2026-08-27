# Getting Started

## 环境要求

- Linux（当前主要开发与验证平台）
- Python 3.12 或更高版本
- Node.js 20 或更高版本
- 可选：NVIDIA GPU 与兼容 CUDA 环境，用于 LADA、FaceFusion 和 GPU 字幕管线
- 可选：Emby/Jellyfin、下载器及其他外部服务

## 获取源码

```bash
git clone https://github.com/kinaxng/NOOR.git
cd NOOR
cp .env.example .env
```

修改 `.env`，至少确认 `NOOR_DATA_DIR`、媒体路径和模型路径适合当前机器。不要把包含真实凭据的 `.env` 提交到 Git。

## 启动后端

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python backend/run.py
```

默认后端地址：`http://127.0.0.1:9898`。

## 启动前端

另开终端：

```bash
cd frontend
npm install
npm run dev
```

默认前端地址：`http://127.0.0.1:5173`。

## 安装插件

首次启动会默认加入官方商店源：

```text
https://github.com/kinaxng/NOOR-Plugins
```

进入“插件管理”，刷新商店后选择需要的插件安装并启用。插件配置、状态与运行数据不会存放在官方插件源码仓库中。

## 安装后检查

1. 打开系统设置，确认数据、模型、缓存与临时目录。
2. 配置并测试媒体服务器连接。
3. 安装需要的下载器、资源源或字幕插件。
4. 先用非重要媒体完成一次小规模任务验证。

下一步：[Configuration](Configuration) · [Plugin Ecosystem](Plugin-Ecosystem)
