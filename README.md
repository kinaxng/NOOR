# NOOR

> No OR. It's AND.

NOOR 是一个本地优先、插件化的 AI 媒体工作流。它把媒体库管理、资源发现、下载器、元数据整理、字幕生成、视频修复和换脸处理放在一个统一界面中。

> 项目仍处于早期开发阶段。处理媒体前请先备份，并确保你对相关内容和服务拥有合法使用权限。

## 功能

- Vue 3 + TypeScript 的统一管理界面
- FastAPI + SQLite 后端与实时任务进度
- Emby/Jellyfin 媒体库浏览、文件与硬链接管理
- qBittorrent、Transmission 等插件化下载器集成
- Whisper 字幕、LADA 视频修复和 FaceFusion 处理管线
- 可独立安装、配置和清理运行数据的插件架构

## 本地开发

需要 Python 3.12+、Node.js 20+；GPU 功能还需要兼容的 NVIDIA/CUDA 环境。

```bash
cp .env.example .env
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python backend/run.py
```

另开终端启动前端：

```bash
cd frontend
npm install
npm run dev
```

默认开发入口为 `http://127.0.0.1:5173`，后端为 `http://127.0.0.1:9898`。所有路径、服务地址和凭据都应在本地 `.env` 或插件设置中配置；不要提交真实媒体路径、数据库、日志或密钥。

## 验证

```bash
PYTHONPATH=backend python -m pytest -q backend/tests
npm --prefix frontend run build
```

## 项目结构

```text
backend/   FastAPI API、任务系统和处理管线
frontend/  Vue 3 前端
plugins/   内置插件
scripts/   开发与检查脚本
docs/      补充文档
```

## 第三方组件

仓库包含具有独立许可证的第三方源代码，尤其是 LADA 与 FaceFusion。请阅读 [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) 以及对应源码目录中的许可证；第三方许可证在其适用范围内优先。

## 安全与隐私

公开 Issue 中请勿附带真实媒体文件名、内网地址、Cookie、令牌或日志。漏洞报告方式见 [SECURITY.md](./SECURITY.md)。

## 许可证

除另有注明的第三方组件外，NOOR 以 [GNU Affero General Public License v3.0](./LICENSE) 开源。
