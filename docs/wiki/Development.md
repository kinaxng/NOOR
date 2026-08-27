# Development

## 分支与提交

- 每个变更保持单一目标。
- 不要把 `.env`、数据库、媒体样例、日志或生成目录加入提交。
- 插件功能优先提交到 `NOOR-Plugins`；通用运行时和 SDK 能力提交到 `NOOR`。

## 后端测试

```bash
PYTHONPATH=backend python -m pytest -q backend/tests
```

## 前端构建

```bash
npm --prefix frontend run build
```

## 插件校验

在 `NOOR-Plugins` 仓库执行：

```bash
./scripts/noor-plugin validate ./plugins/<plugin-id>
```

校验范围包括 Manifest、能力声明、前端入口、CSS 前缀、浏览器原生弹窗和硬编码主程序地址。

## Core 与插件的判断边界

适合进入 Core：

- 通用任务、配置、导航、弹窗、Toast 与 UI 组件
- 插件运行时、SDK、市场协议与生命周期
- 多个插件都需要的稳定抽象

适合进入插件：

- 某个站点、下载器或外部服务的协议
- 独立业务页面
- 可选资源源、字幕源和推荐策略

## 提交前检查

1. 后端测试通过。
2. 前端生产构建通过。
3. 插件校验通过。
4. `git diff --check` 无空白错误。
5. 隐私和密钥扫描无真实数据。
