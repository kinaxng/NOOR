# NOOR

> **No OR. It's AND.**

NOOR 是一个面向 JAV 视频处理与媒体管理的本地优先（Local-first）AI 平台。

NOOR 不要求用户在不同工具之间做取舍，而是将多种 AI 能力整合到同一个工作流中，让音频理解、元数据处理与媒体管理协同工作，自动分析、整理并管理视频内容。

通过将不同能力组合在一起，NOOR 可以帮助用户更高效地处理大规模视频库。

## 核心理念

| 理念 | 说明 |
|------|------|
| **本地优先** | 所有处理都在本地运行，数据完全由用户掌控 |
| **统一工作流** | 音频处理、元数据解析和媒体管理在同一流程中协同完成 |
| **自动化整理** | 为大规模视频库提供自动化分析与管理能力 |
| **可组合架构** | 支持整合多种处理引擎与工具，而不是绑定单一方案 |

## 开发约束

后续开发默认遵守以下约束，避免出现“开发版一套、Docker 版一套”的分叉：

1. **单一配置源**
   - 默认使用项目根 `.env`
   - Docker Compose 读取 `.env`
   - backend 读取 `.env`
   - 设置页回写 `.env`
   - 新功能不要再新增 `xxx_config.json` 作为主配置源

2. **路径语义同构**
   - 返回给前端的路径必须是任务可直接消费的真实路径
   - 开发环境可用的路径，Docker 环境也必须成立
   - 新增路径映射时，先验证容器内是否仍然成立

3. **新 runtime 先按 Docker 设计**
   - 适用于 NeMo / 新 ASR / 新翻译后端 / 新视频处理 backend
   - 先定义 `.env` 配置键、Docker 策略、feature gating，再做 UI 与任务链路

4. **功能验收包含 Docker 视角**
   - 主链功能完成时，至少验证配置持久化、容器内路径可访问、任务可执行、产物可落盘

5. **开发版不是另一套产品**
   - 不允许“开发版先能用，Docker 版后适配”
   - 默认以 Docker 可运行语义作为主线约束

## 核心功能

- **LADA 视频修复** — 马赛克区域 AI 修复（lada-cli GPU 加速）
- **Whisper 字幕生成** — 多引擎日语/中文/英语自动字幕
- **GPT 翻译** — SRT 字幕 OpenAI 兼容翻译
- **Emby / Jellyfin 媒体库** — 单库海报墙浏览、任务直接从媒体库提交
- **实时进度** — SSE 推送任务日志与进度
- **全容器化** — Docker + NVIDIA GPU 支持，一键部署

## 技术架构

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Frontend    │────→│  FastAPI Backend │────→│ lada-cli      │
│  Vue3 + TS   │←────│  (Uvicorn)       │←────│ Whisper       │
└──────────────┘     └──────────────────┘     └────────────────┘
   SSE 实时推送         SQLite                  NVIDIA GPU
   Vision UI           asyncio             Emby / Jellyfin API
```

## 快速开始
## 访问入口约定

- 开发环境：前端 `http://127.0.0.1:5173`，后端 `http://127.0.0.1:9898`
- Docker 环境：前端 `http://127.0.0.1:19898`（由 compose 映射）

> 说明：19898 是 Docker 前端入口，不作为本地开发前端入口。


### 本地开发

```bash
# 后端
cp .env.example .env
# 编辑项目根目录 .env，配置 Emby / Jellyfin、LADA、模型路径

cd backend
pip install -r requirements.txt
python run.py

# 前端（另一个终端）
cd frontend
npm install
npm run dev
```

### 前端提交前检查（UI Kit 防回退）

```bash
# 一键执行：旧组件导入检查 + build + 冒烟
./scripts/ui-kit-guard.sh
# 可选自定义冒烟地址
# ./scripts/ui-kit-guard.sh http://127.0.0.1:5173

# 或从 frontend 目录执行
npm --prefix frontend run guard:ui
```

可选：安装本地 pre-push 钩子（推送前自动执行 guard）

```bash
./scripts/install-git-hooks.sh
```

部署前检查（开发 + Docker 冒烟）：

```bash
./scripts/deploy-precheck.sh
# 可选：指定开发前端地址与 docker 前端地址
# ./scripts/deploy-precheck.sh http://127.0.0.1:5173 http://127.0.0.1:19898
```

### Docker 部署

Docker 版定位为**部署环境**，不是开发环境。

- 使用**单一 `.env`**：Docker Compose 读取它做端口/挂载插值，后端也直接读取并回写它
- 容器内 NOOR 自身数据统一落在 `/app/data`，由宿主机 `./data` 持久化
- `INSTALL_NEMO=false` 为默认值，避免把实验性的 Reazon / NeMo 运行时打进生产镜像
- `MODELS_DIR` 与 `MEDIA_ROOT` 都会以**宿主机原绝对路径**挂进容器
- `FULL_RUNTIME_IMAGE` 用来指定 full GPU 版的 CUDA/Python 3.12 基底；默认使用官方镜像
- 设置页修改的业务配置会直接回写项目根 `.env`；存储页显示的是后端解析后的实际运行路径

```bash
# 1) 准备部署环境变量
cp .env.example .env

# 2) 启动
# 默认部署：前端暴露 19898，后端只在 docker 内网提供服务
docker compose up -d
# 或
# 如需额外直连后端调试，再叠加 backend override（默认 19899）
# docker compose -f docker-compose.yml -f docker-compose.deploy.yml up -d

# 3) 查看日志
docker compose logs -f

# 4) 验证 GPU
docker compose exec backend nvidia-smi

# 5) 打开前端后，进入设置页填写：
#    - Emby / Jellyfin 地址与 API key
#    - 单个媒体库选择
#    - 路径映射
```

持久化约定：
- SQLite 数据库：`./data/noor.db`
- 插件数据 / 任务日志 / 状态文件：`./data/`
- 设置页保存配置：`./.env`
- 临时文件：`./data/runtime/...`
- 缓存目录：`./data/runtime/...`
- 模型总根：`${MODELS_DIR}` 挂载到容器内同一路径 `${MODELS_DIR}`
- 媒体总根：`${MEDIA_ROOT}` 挂载到容器内同一路径 `${MEDIA_ROOT}`

> Docker 模式升级建议通过更新镜像并重建容器完成，
> 不建议在运行中的容器内直接执行 LADA 自升级。

详细文档：[DOCKER.md](./DOCKER.md)

## 页面路由

| 路径 | 说明 |
|------|------|
| `/` | 单个媒体库海报墙，从 Emby / Jellyfin 浏览并提交任务 |
| `/jobs` | 实时任务监控，SSE 推送日志与进度 |
| `/history` | 历史记录，查看完成/失败任务 |
| `/settings` | 系统设置 |

## 配置 (.env)

```bash
# LADA
LADA_CLI_PATH=python3 -m lada.cli.main
LADA_MODEL_WEIGHTS_DIR=/path/to/lada_model_weights

# Whisper
WHISPER_MODEL_DIR=/path/to/models/huggingface
WHISPER_CACHE_DIR=/path/to/noor/data/runtime/whisper/cache

# Emby / Jellyfin
EMBY_SERVER=http://localhost:8096
EMBY_API_KEY=your_api_key
EMBY_USER_ID=optional_user_id
EMBY_ENABLED_LIBRARY_IDS=library_id
