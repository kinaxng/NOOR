Output:
# NOOR Docker 部署指南

## 概述

```
宿主机 NVIDIA Driver
        │
        ▼
┌─────────────────────────────────┐
│  Docker (CUDA 12.8 / smoke CPU)  │
│                                 │
│  ┌─────────────────────────┐   │
│  │ backend (PID 1)         │   │
│  │ uvicorn + lada-cli      │   │
│  │ Whisper (GPU)           │◄──┼── GPU (NVIDIA_VISIBLE_DEVICES=all)
│  └─────────────────────────┘   │
│                                 │
│  ┌─────────────────────────┐   │
│  │ frontend (nginx :80)   │   │
│  │ 静态文件 + 反向代理     │   │
│  └─────────────────────────┘   │
└─────────────────────────────────┘
         ▲
         │ docker-compose
         ▼
  volumes:
    /volume1/models (宿主机大模型目录)
    ./data -> /app/data (NOOR 数据 / 缓存 / 状态)
```

---

## 前置要求

### 1. NVIDIA Driver + Container Toolkit

```bash
# 验证宿主机 GPU 可访问
nvidia-smi
# 应显示 Driver Version, CUDA Version, GPU 型号

# 验证 nvidia-container-toolkit
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi
```

**Driver 版本对照**：
| Driver | 支持 CUDA | 适配容器 CUDA |
|--------|---------|-------------|
| 560.x | ≤ 12.6 | 12.8 ✓ |
| 575.x | ≤ 12.4 | 12.8 ✓ |
| 590.x | ≤ 13.1 | 12.8 ✓ |

### 2. Docker 环境

- Docker Engine 20.10+
- docker-compose v2 (或 `docker compose` plugin)
- NVIDIA Container Toolkit

安装 NVIDIA Container Toolkit（Ubuntu）:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/nvidia-docker/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-docker.gpg
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-docker.gpg] https#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

---

## 构建与启动

## 部署前建议先做一键预检查

```bash
./scripts/deploy-precheck.sh
```

该脚本会先执行 UI guard（旧组件回退检查 + build + 关键路由冒烟），并在检测到 docker compose 服务已运行时自动补跑 `docker-smoke.sh`。

## 上线流程建议（最小闭环）

```bash
# 1) 可选：安装本地 pre-push 钩子，避免把 UI 回退提交出去
./scripts/install-git-hooks.sh

# 2) 部署前检查（开发检查 + Docker 冒烟）
./scripts/deploy-precheck.sh

# 3) 构建并启动容器
docker compose up -d --build
```

### 1. 准备宿主机模型目录

Docker 版直接挂宿主机模型根目录，不要求仓库内存在 `models/` 软链接。

```bash
mkdir -p /volume1/models
mkdir -p /volume1/models/lada_model_weights
mkdir -p /volume1/models/huggingface
mkdir -p ./data
```

### 2. 配置环境变量

```bash
cp .env.example .env
nano .env  # 按需修改
```

`docker-compose.yml` 现在直接使用项目根 `.env`：

- Compose 用它做端口 / 挂载 / build args 插值
- backend 也把它当作应用主配置文件
- 设置页保存后会直接回写这份 `.env`

关键配置项：

```bash
# 模型目录（宿主机根目录，容器内保留相同绝对路径）
MODELS_DIR=/volume1/models
INSTALL_NEMO=false
FULL_RUNTIME_IMAGE=nvidia/cuda:12.8.1-runtime-ubuntu24.04

# 视频文件（宿主机目录在容器内保留相同绝对路径）
#
# MEDIA_ROOT 最好填写 downloads / media / 硬链接目录的共同上级
MEDIA_ROOT=/media

# NOOR 自身数据根。Docker 内固定为 /app/data，由宿主机 ./data 持久化。
NOOR_DATA_DIR=./data
```

说明：

- Docker 版默认只让用户配置少数几个**宿主机目录级**挂载：
  - `MODELS_DIR`
  - `MEDIA_ROOT`
- NOOR 自身数据库、插件数据、任务日志、状态文件、运行缓存和临时文件统一放在 `./data`，容器内路径为 `/app/data`
- `MODELS_DIR` / `MEDIA_ROOT` 会按**原绝对路径**挂进容器，不再改写成 `/app/...` 或 `/Videos`
- 业务配置也可以直接预填在同一个 `.env`，例如 Emby/Jellyfin、Whisper、LADA、媒体库路径映射
- LADA 权重默认仍从 `MODELS_DIR/lada_model_weights` 读取；Whisper / HuggingFace 模型默认指向 `MODELS_DIR/huggingface`
- Reazon / NeMo 与 audio-separator 模型默认落在 `MODELS_DIR/whisper/...`
- Whisper / LADA / FaceFusion 的运行缓存和临时目录默认落在 `/app/data/runtime/...`

升级说明：Docker 模式下建议通过更新镜像并重建容器来升级 LADA，不建议在运行中的容器内直接执行 `git pull / pip install`。

`INSTALL_NEMO=false` 是建议默认值。原因很直接：

- NeMo 目前在 NOOR 里仍属于实验链路
- 依赖体积大，构建慢
- 对部署镜像的默认价值不够高

只有你明确要启用 Reazon / NeMo runtime 时，再改成 `true` 重新构建。

`FULL_RUNTIME_IMAGE` 默认指向官方 `nvidia/cuda` Ubuntu 24.04 runtime。  
这样可以稳定拿到 Python 3.12，满足当前 LADA 的 `requires-python >= 3.12`。如果某些环境下拉取 Docker Hub 较慢，可以临时改成你信任的镜像代理地址做构建验证。

### 3. 构建镜像

```bash
# 默认构建 full（CUDA + Python 3.12 运行镜像）
docker compose build backend

# 或直接启动并后台构建
docker compose up -d --build
```

如果当前机器网络对 `nvidia/cuda` 大层拉取很慢，可先做一个 **smoke build** 验证 Dockerfile 与应用依赖是否成立：

```bash
docker build \
  --build-arg NOOR_DOCKER_PROFILE=smoke \
  -t noor-backend-smoke .
```

或：

```bash
NOOR_DOCKER_PROFILE=smoke docker compose build backend
```

`smoke` 使用 `ubuntu:24.04` 纯 CPU 基底，只用于构建与启动验证，不用于 GPU 生产运行。

### 4. 启动

```bash
docker compose up -d
docker compose logs -f   # 查看日志
```

访问：
- 默认部署入口（前端）: `http://localhost:19898`
- 如需额外直连后端调试：`docker compose -f docker-compose.yml -f docker-compose.deploy.yml up -d`
  - 后端 API 会额外暴露到 `http://localhost:19899`
- 后端默认**不直接暴露到宿主机**

首次打开后，进入设置页补齐：

- Emby / Jellyfin 地址与 API key
- 单个媒体库选择
- 路径映射

建议：
- 把 `MEDIA_ROOT` 指向所有媒体相关目录的共同上级
- 容器里会继续使用这个绝对路径，因此设置页里填写的源目录 / 输出目录 / 硬链接扫描目录可以直接复用宿主机路径
- 确保宿主机 `./data` 所在磁盘空间充足；任务日志、数据库、插件缓存和运行临时文件都会落在这里

### 5. 验证 GPU 可用性

```bash
# 进入后端容器
docker compose exec backend bash

# 验证 torch 可以看到 GPU
python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0)}')"

# 验证 lada-cli 可用
lada-cli --help

# 验证 ffmpeg 可用
ffmpeg -version | head -1
```

---

## 目录结构

```
noor/
├── Dockerfile              # 后端镜像（full/smoke 双档位）
├── Dockerfile.frontend      # 前端镜像（Nginx 静态服务）
├── docker-compose.yml       # 默认部署（前端 19898）
├── docker-compose.deploy.yml# 可选调试覆盖（额外暴露后端 19899）
├── .env.example             # 单一环境变量示例
├── .dockerignore            # 构建忽略
├── data/
│   ├── noor.db              # SQLite 数据库
│   ├── plugin_cache/        # 插件缓存
│   ├── runtime/             # 任务日志 / 状态 / 临时文件 / 运行缓存
│   └── models/              # NOOR 管理的小型/实验模型
├── backend/
│   ├── app/                 # WebUI 代码
│   └── ...
└── frontend/
    ├── dist/               # 构建产物（由 Dockerfile 构建）
    └── nginx.conf          # Nginx 反向代理配置
```

---

## 宿主机模型准备

### LADA 模型

将已有的 `lada_model_weights` 目录放到 `/volume1/models/lada_model_weights/`：
Output:
将已有的 `lada_model_weights` 目录放到 `/volume1/models/lada_model_weights/`：

```bash
# 宿主机上
cp -r /your-source/lada_model_weights /volume1/models/
```

### Whisper / Reazon / Audio Separator 模型

Whisper / transformers 模型目录由 `WHISPER_MODEL_DIR` / `HF_HOME` 控制。当前 compose 默认把 HuggingFace 缓存放在 `${MODELS_DIR}/huggingface`，运行缓存放在 `/app/data/runtime/whisper/cache`。

也可以手动预下载：

```bash
docker compose exec backend bash
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download(repo_id='Systran/faster-whisper-large-v3', cache_dir='/volume1/models/huggingface')
"
```

如果使用 Reazon / NeMo 或音频分离，直接把对应文件放到：

- `${MODELS_DIR}/whisper/reazon`
- `${MODELS_DIR}/whisper/audio-separator`

容器内会自动映射为：

- `REAZON_MODEL_DIR=${MODELS_DIR}/whisper/reazon`
- `REAZON_NEMO_MODEL_PATH=${MODELS_DIR}/whisper/reazon/reazonspeech-nemo-v2.nemo`
- `AUDIO_SEPARATOR_MODEL_DIR=${MODELS_DIR}/whisper/audio-separator`

---

## GPU 隔离（多用户 / 多容器）

如果宿主机有多个 GPU，指定只用的 GPU：

```yaml
# docker-compose.yml
environment:
  - NVIDIA_VISIBLE_DEVICES=0        # 只用 GPU 0
  # NVIDIA_VISIBLE_DEVICES=all       # 用所有 GPU
```

---

## 常见问题

### Q: `nvidia-smi` 在容器内不可用

```bash
# 确认 nvidia-container-toolkit 已安装
dpkg -l | grep nvidia-container

# 重启 docker
sudo systemctl restart docker

# 验证
docker run --rm --gpus all nvidia/cuda:12.8.0-runtime-ubuntu22.04 nvidia-smi
```

### Q: torch.cuda.is_available() == False

检查容器是否使用了 `runtime: nvidia`：

```bash
docker inspect noor-backend-1 | grep -A5 Runtime
# 应该看到 "nvidia"
```

### Q: 构建时 pip install torch 失败

网络问题导致 CUDA wheel 下载失败，检查：
1. 宿主机能否访问 `https://download.pytorch.org`
2. 使用镜像（需修改 Dockerfile 中的 index-url）

### Q: 模型目录权限错误

宿主机目录权限需让容器内 `root` 可读：

```bash
chmod -R 755 ./models
```

### Q: `Permission denied: /app/data`

宿主机 `./data` 目录需要可写：

```bash
chmod -R 755 data/
```

---

## 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建（Python 依赖不变则可以用缓存）
docker compose build

# 重启
docker compose up -d
```

如需强制重建所有层：

```bash
docker compose build --no-cache
docker compose up -d
```


## 端口对齐说明

- 本地开发：5173(前端) + 9898(后端)
- Docker 默认：19898(前端)
- `docker-compose.yml` 默认通过 `.env` 插值，`.env.docker` 为参考文件，不会自动生效。
