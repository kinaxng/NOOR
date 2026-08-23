# NOOR 恢复差距审计

更新时间：2026-08-23

本文件只记录 `noor-restored` 与删除前 NOOR 的差距。它不代替 `RECOVERY.md`，
只用于回答“现在为什么还不能说已经恢复原样”。

## 证据来源

- 原始 Codex rollout：`/home/kinax/.codex/sessions/2026/06/08/rollout-...jsonl`
- 早期前端会话：`/home/kinax/.codex/sessions/2026/04/12/rollout-...jsonl`
- 原始提交索引：`forensics/original-commit-index.json`
- 原始符号索引：`forensics/original-symbol-index.json`
- 前端快照：`forensics/frontend-snapshots/`
- 恢复后端字节码：`backend/app/**/*.pyc`（只作证据，不作为运行源码）

## 已验证为恢复原样的部分

- 资源搜索页 `ResourceSearch.vue`：已按 rollout 历史回放恢复为 851 行聚合页，
  实测 `DASS-927` 返回作品/资源/中字/JavDB 聚合结果。
- 插件运行时 `backend/app/plugins/runtime.py`：已恢复插件生命周期、SDK、
  后台任务钩子；14 个插件目录与运行注册表一致。
- 插件管理页 `PluginManager.vue`：当前 1530 行，覆盖已安装/市场/配置/测试/卸载等入口。
- FaceFusion 面板 `FaceFusionPanel.vue`：当前 2898 行，包含默认面板、全宽面板、
  模型选择、参考人脸、源脸库、预览和后续 face tracker score。
  - FaceFusion 设置页 `FaceFusionSettings.vue`：当前 1722 行，已核对原版最终会话，
  包含完整默认参数、执行/处理器/遮罩/预览选项、模型管理、固定换脸标签开关与
  face tracker score。
  - `LadaPanel.vue`：当前 294 行，已核对为拆出 `FaceFusionPanel.vue` 后的纯 LADA
  面板，不再包含 FF 双 tab 残留。
  - 媒体库首页 `Home.vue`：当前 735 行，已核对原版最后一次换脸标签提交；保留
  FF/LADA/字幕/详情/删除面板入口、Emby webhook 同步与移动端响应式样式。
- 演员管理/详情页：与 `2a7fe62` 中按历史工作区源码恢复的版本一致。
- 媒体库页面：Emby 数据可读，549 位演员、作品列表、破解/中字/流出/无码标签可用。
- 前端构建通过，后端 `pytest` 188 项通过；`compileall` 无语法错误。
- `StorageSettings.vue`：已恢复为最终“两个大头目录”形态，只编辑模型根目录、
  运行时根目录、NOOR 数据目录和数据库只读路径；子模块缓存/临时目录输入已移除。
- `SystemSettings.vue`：MDC-NG 路径、演员映射自动更新、Emby 连接与 webhook
  设置已按最终会话核对。
- `MediaCard.vue`：FaceFusion 标签已按 `has_facefusion` 聚合文件名/媒体信息，
  默认仅在悬停显示，开启固定显示后始终可见。
- `SubtitlePanel.vue`：已核对最终 Whisper 单链 UI，包含 runtime tier 提交，
  不包含已退役的音频预处理/旧链路 UI。
- `settings_facefusion_upgrade.py`：已核对内置 FaceFusion 的版本/运行时信息、
  受控上游同步、NOOR 内容分析跳过补丁和 TensorRT 缓存补丁；并新增 3.8 风格
  源码与已补丁源码的回归测试。
- 演员路由兼容已用 OpenAPI 契约测试锁定：前端使用的
  `/api/media-library/actor/*`、`/api/media-library/actors/*` 均由当前
  `endpoints/actors.py` 挂载，历史 `/actor/emby/:actorId` 会重定向到
  `/actors/:actorId` 详情页。
- 下载插件已核对最终行为：qBittorrent 支持 5.2+ Bearer API Key 与 start/stop
  控制；迅雷远程残留处理为 `.xltd/.xtld` 删除后按番号跳转搜索页。
- 推荐/订阅插件已核对最终行为：推荐中心为 `latest`/`full` 两种模式，
  候选池显示 `总数+今日增量`，卡片支持订阅、详情面板和刷新后封面回退。
- 后端高置信模块已登记为 verified：设置契约/更新、FaceFusion runner/API、
  Whisper engine/orchestrator/strategy/runtime tier，以及对应测试。
- Gfriends 已核对为头像库辅助插件：不再全局接管头像，只在演员资料编辑时提供
  候选头像查询与选择。

## 本轮一致性收敛（2026-08-23）

- `backend/app/tasks/manager.py` 已恢复完整队列语义并转 `verified`：阶段/SSE、
  持久化恢复、排队与运行中取消、依赖链激活/跳过、孤儿 `running` 清理、日志落盘、
  GPU Guard、LADA/FaceFusion，以及 Whisper/翻译独立 worker 进程和超时强杀。
  新增 `backend/tests/test_job_manager_recovery.py`，当前后端全量测试为 195 项通过。
- 新增 `backend/tests/test_media_library_api.py`，覆盖 NFO 嵌套演员/CDATA、
  `get_item_impl` 本地 NFO 集成、媒体库 503/502 错误响应、硬链接扫描与摘要契约。
- 恢复最终版本 `Settings` 中的 FaceFusion 目录、Python 路径和完整默认参数，
  同时保留 `facefusion_defaults.py` 作为旧配置覆盖文件兼容层。
- Whisper 模型删除统一走 `resolve_model_cache_candidates`，支持
  `transformers` / `onnx-vad` / `onnx` 三类缓存；Whisper 运行时探测不再返回
  `reazon_nemo` 等已退役链路字段。
- 设置页存储契约改为返回 `model_root_dir`、`runtime_root_dir`、
  `database_url`、`database_path`，前端不再依赖已移除的 Reazon 字段。
- 文件级差距清单已重新生成：当前无 `missing` 路径；53 个路径仍为
  `pending`，需要在后续逐文件核对后转 `verified`。
- JavDB 插件清单已按原版会话恢复：补回 `dashboard_widget`、下载器绑定、
  `resource_search`、RSS/知识图谱等能力；浏览器验证概览页的 `JAVDB 推荐`
  卡片恢复，`/api/plugins/dashboard/widgets?plugin_ids=javdb` 返回
  `javdb-recommend`。
- `media_library.py` 已补齐拆分后的旧函数名兼容层；与保留的
  `media_library.pyc` 顶层代码对象逐项比对，原版旧名字均已可导入。
- 继续按 rollout 回放核对运行时/路径模块：`runtime_cleanup`、`runtime_paths`、
  `database_paths`、`gpu_guard`、`lada_paths`、`timing_refiner`、
  `settings_whisper_models`、`settings_whisper_runtime` 已转 `verified`。
  GPU Guard 新增回归测试，覆盖 NOOR 自身进程保护和仅清理 NOOR/模型服务进程。
- 恢复 `settings_directories.py` 最终允许目录列表：除媒体目录外，重新接受
  `noor_data_dir`、`model_root_dir`、`runtime_root_dir` 以及 Whisper/LADA/FaceFusion
  的 model/cache/temp 根目录。
- 恢复 `local_library.py` 最终索引迁移：索引主路径改为
  `runtime/subtitle_library/subtitle_index.db`，并会从三个历史位置复制最强旧索引；
  原 `data/subtitle_index.db` 不再是运行路径。
- 任务/事件 API 新增契约测试：覆盖任务列表/详情/取消/删除/清理以及 SSE
  connected/done 序列；后端全量测试更新为 203 项通过。文件级差距清单当前为
  77 个 `verified`、53 个 `pending`、0 个 `missing`。

## 明确差距

1. 前端源码不是“磁盘直接恢复”，而是从会话片段重建/回放出来的。
   - 文件路径齐全，但部分文件内容仍是可维护重建，不是字节级原文件。
   - 例如 i18n 曾漏掉 `settings.whisper.testFailed`，本次已补回中英文键。
   - 静态扫描 `frontend/src` 中 687 个 `t()` 引用后，补回英文缺失键
     `dashboard.welcome.message`；当前中英文静态引用键均无缺失。
2. 原始 `media_library.py` 是约 228 个函数、43 个路由的单模块；当前按职责拆为
   `endpoints/media_library*.py` 和 `endpoints/actors.py`。大多数功能等价，
   但函数名、路由前缀、文件结构不同。
3. 演员映射表工作流有意从“上传 XML / 在线同步”改为“MDC-NG 路径同步”：
   - 已移除：`/actors/mapping/upload`、`/actors/mapping/sync-online`、
     `/actors/mapping/import-latest`、`/actors/mapping/latest-upload`。
   - 已保留：`/actors/mapping/source`、`/actors/mapping/sync-mdc-ng`。
   - 这是用户后来明确要求的方向，不作为待恢复项。
4. 推荐插件有意移除了“订阅推荐/洗版推荐”两个独立推荐模式：
   - 当前为 `latest`（最新推荐）和 `full`（完整推荐），候选池显示 `总数+今日增量`。
   - 卡片保留订阅按钮，但不再作为独立推荐 Tab。
5. Whisper 旧链路源码未保留源码文件，只保留 `.pyc` 证据：
   - `decoupled/anime_qwen3_chain.py`、`decoupled/qwen3.py`、
     `enhancer.py`、`preprocess.py` 只有字节码，没有 `.py`。
   - 这是用户要求收敛为 Chicken Rice 主链路后的预期结果；如后续要恢复为源码，
     只能靠反编译或会话历史重建。
6. 尚未找到的原始完整快照：
   - 完整 Vue 组件树没有单一可信的“最终原文件”副本。
   - `App.recovered-full.vue` 是旧单文件 UI，不能直接替换当前组件化前端。
   - 每个组件都应按 rollout 证据逐文件核对，已核对完 `ResourceSearch`、
     `FaceFusionSettings`、`LadaPanel`、`Home`；下一批是 i18n、
     `ActorManagementView`、`ActorDetailView` 和 `FaceFusionPanel` 的后续修订。

## 后续恢复建议（按影响排序）

1. 下一批继续用 rollout 回放核对 `facefusion/runner.py`、`facefusion.py`、
   `settings_facefusion_upgrade.py` 与插件恢复差异，把 `pending` 文件逐步转为 `verified`。
2. 继续核对拆分后的 actor 路由兼容，确认历史 `/api/media-library/actors*` 调用
   都能通过当前 `endpoints/actors.py` 得到原版行为。
3. 把 Whisper 旧链路的 `.py` 源码从历史会话/反编译中重建，或以文档形式明确退役。
4. 每恢复一个模块，更新本文件并提交，避免再次丢失。
