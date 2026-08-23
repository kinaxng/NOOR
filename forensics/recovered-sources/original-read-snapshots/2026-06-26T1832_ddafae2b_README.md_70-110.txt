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

