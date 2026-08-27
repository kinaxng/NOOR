# Architecture

## Intelligence Core

NOOR uses a system-level Intelligence Core rather than a standalone graph UI. It is the shared memory used by the media library, resource search, work details, subscriptions and recommendations.

For every canonical work code the Core maintains:

- a continuously enriched work profile, including multilingual titles, aliases, semantic tokens and provider-scoped facts;
- source evidence and confidence, so conflicting provider facts are preserved rather than silently overwritten;
- provider-scoped resource observations with separate availability, features, first/last seen and expiry fields;
- a persistent refresh state used by background workers when page-time resource checks cannot finish.

Single-code resource searches are observations, not disposable responses. Results are written back to the Core and reused across NOOR. Work-detail actions also contribute identity and metadata. Recommendation cards read the same observations and enqueue unfinished checks for background completion, keeping page rendering independent from slow providers.

Core endpoints currently include:

- `GET /api/knowledge/works/{code}` — merged work profile and resource intelligence;
- `POST /api/knowledge/resources/refresh` — enqueue one or more work codes;
- `GET /api/knowledge/resources/refresh/status` — inspect persistent refresh progress.

The Agent layer is intentionally not part of the Core. A future optional Agent plugin can consume these APIs without making NOOR dependent on a language model.

NOOR 将稳定的通用能力保留在 Core，把可替换的服务集成与独立业务功能放入插件。

## Core

`kinaxng/NOOR` 负责：

- FastAPI API、SQLite 数据与任务生命周期
- Vue 3 管理界面、路由、通用组件和 Plugin UI SDK
- 媒体库、文件浏览、硬链接与处理管线
- 插件发现、配置、启停、市场安装和数据清理
- Whisper、LADA 与 FaceFusion 的核心任务编排

## Official plugins

`kinaxng/NOOR-Plugins` 负责：

- 官方插件源码
- 根目录 `plugins.json` 商店索引
- Plugin SDK、设计约束和开发文档
- `noor-plugin` 创建、校验与打包工具

## 插件生命周期

```text
Marketplace index
      ↓
Download repository archive
      ↓
Locate source_dir/plugin.json
      ↓
Install into NOOR plugin directory
      ↓
Configure → Test → Enable
      ↓
Disable or uninstall
      ↓
Keep or remove private runtime data
```

插件代码与插件私有运行数据是两个概念。卸载插件时，用户可以选择保留数据以便重新安装恢复，也可以一并删除。

## 数据边界

- `.env`：主程序和基础设施设置
- SQLite：NOOR 核心业务状态
- 插件私有目录：插件配置、索引、缓存和状态
- Runtime 目录：模型缓存、临时文件和任务中间产物
- 媒体目录：由部署者显式授权和映射

下一步：[Configuration](Configuration) · [Plugin Ecosystem](Plugin-Ecosystem)
