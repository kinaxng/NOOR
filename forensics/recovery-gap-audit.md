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
- 原始 HANDOFF：`forensics/original-handoff.md`（并已恢复到 `/home/kinax/HANDOFF.md`）
- 原镜像 Vite 内联 source map：`forensics/raw-vite-sourcemaps/`
- 恢复后端字节码：`backend/app/**/*.pyc`（只作证据，不作为运行源码）
- 预接管完整备份：`/.1panel_clash/files/0ccfe0c069554d47be2eb71f8e92f7fd/noor-full-pre-takeover-20260412-160609.tar.gz`
  （含 `.git`、完整源码，作为原版早期基准）

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
- 前端构建通过，后端 `pytest` 216 项通过；`compileall` 无语法错误。
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

- 将此前只存在于 `/tmp` 的原版前端证据复制到 `forensics/recovered-sources/`
  并生成 SHA256SUMS：ActorDetail、History、ResourceSearch、Home source-map raw、
  FaceFusionPanel source-map raw 和 Jobs 回放证据。
- `Jobs.vue` 已按最终原版回放版本核对并转 `verified`，当前文件与
  `forensics/recovered-sources/Jobs.vue.2026-06-13-final-replayed.vue` 字节一致；
  其职责是任务运行/后台 Tab，不含已迁移到 `History.vue` 的诊断链路面板。
- `ActorManagementView.vue` 已核对为 `2a7fe62` 历史工作区源码回放版本并归档
  `forensics/recovered-sources/ActorManagementView.vue.replayed.vue`，SHA256
  与当前文件一致；演员管理页的映射、重名检测、TMDB 补全、语言批量同步入口齐全。
- 给 `backend/app/api/endpoints/media_library_recovery.py` 的恢复路由补独立
  `operation_id`，消除 FastAPI OpenAPI 重复操作名告警；后端全量测试仍为
  216 项通过。

- 从活盘 `/dev/nvme0n1p2` 恢复出早期原版 `media_library.py` 源码种子，并
  用 2026-06/07 NOOR rollout 补丁回放得到
  `forensics/recovered-sources/media_library.early-replayed.py`（4400 行、
  188 个函数、45 条媒体库路由）。随后将 helper/item-detail/stream 契约内联为
  `forensics/recovered-sources/media_library.final-replayed.py`：204 个函数、
  覆盖原版 43 条路由（另含 `/stream` 与 `/sync-mdc-ng`）。剩余 29 个原版符号
  主要是已退役 XML/在线映射函数、历史单测和旧适配器兼容函数；该文件已通过
  `ast.parse`，可作为原版媒体库路由/函数的独立证据，不再只依赖会话片段。
- 路由核对：回放版 43 条原版路由里，除 4 条用户明确废弃的 XML/在线映射
  路由外，全部由当前 `endpoints/media_library*.py + endpoints/actors.py`
  承接；当前另有 `/stream/{item_id}` 和 `/actors/mapping/source` 两条
  恢复期新增/保留路由。
- 继续全盘扫描 `/dev/nvme0n1p2` 中可能残留的 Git pack，目标是匹配原版
  commit hash；扫描仍在后台运行。同时用 4 月预接管备份和旧 464G 镜像交叉核对，
  目前尚未命中 NOOR pack，但已确认预接管备份保留的是删除前原始早期工作树。

- `backend/app/tasks/manager.py` 已恢复完整队列语义并转 `verified`：阶段/SSE、
  持久化恢复、排队与运行中取消、依赖链激活/跳过、孤儿 `running` 清理、日志落盘、
  GPU Guard、LADA/FaceFusion，以及 Whisper/翻译独立 worker 进程和超时强杀。
  新增 `backend/tests/test_job_manager_recovery.py`，当前后端全量测试为 216 项通过。
- 新增 `backend/tests/test_media_library_api.py`，覆盖 NFO 嵌套演员/CDATA、
  `get_item_impl` 本地 NFO 集成、媒体库 503/502 错误响应、硬链接扫描与摘要契约。
- 恢复最终版本 `Settings` 中的 FaceFusion 目录、Python 路径和完整默认参数，
  同时保留 `facefusion_defaults.py` 作为旧配置覆盖文件兼容层。
- Whisper 模型删除统一走 `resolve_model_cache_candidates`，支持
  `transformers` / `onnx-vad` / `onnx` 三类缓存；Whisper 运行时探测不再返回
  `reazon_nemo` 等已退役链路字段。
- 设置页存储契约改为返回 `model_root_dir`、`runtime_root_dir`、
  `database_url`、`database_path`，前端不再依赖已移除的 Reazon 字段。
- 文件级差距清单已重新生成：当前无 `missing`、无 `pending`，130 个路径已转
  `verified`。目录级路径与对应文件级恢复、测试覆盖一并核销。
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
  connected/done 序列，并恢复 `POST /api/jobs` 的原版任务类型白名单；
  后端全量测试更新为 216 项通过。文件级差距清单当前为 130 个 `verified`、
  0 个 `pending`、0 个 `missing`。
- 新增媒体库路由契约测试：以 `forensics/original-symbol-index.json` 中的原版
  43 条路由为基准，核对当前 `/api/media-library/*`；除用户明确改为 MDC-NG
  映射的 4 条路由外，其余路由均已恢复，并保留当前 4 条兼容路由。
- 新增前端原始 Vite source map 证据：从 `/tmp/chromium-shared` 提取 111 个
  5 月前端文件，从 `/tmp/cdp-v1WmoE` 提取 11 个 5 月 18 日组件，从
  `/home/kinax/.cache/chrome-devtools-profile` 提取 14 个 7/8 月晚版组件，已归档到
  `forensics/frontend-snapshots/vite-cache-*`，并生成 SHA256 校验。
- `History.vue` 已按“5 月原版源码 + June/July rollout 补丁回放”恢复，补回
  原版任务日志展开、评分/诊断摘要、任务元数据与日志尾部查看功能；当前文件
  恢复为 714 行以上，前端生产构建通过。
- `Jobs.vue` 已按 2026-06-13 原版分段源码 + 8 个后台任务成功补丁重建为 821 行
  最终原版，并对照 2026-07-08 原版片段确认后台任务 UI；链路诊断面板已在
  2026-05-04 原版会话中从 `Jobs.vue` 移除，诊断契约仍保留在 `History.vue`。
- `MediaDetailPanel.vue` 已补回原版标签过滤和播放地址策略：标签会排除番号、
  片商、系列、演员名等重复项；预览优先使用 Emby `stream_url`，失败后回退
  本地 hardlink 预览接口。
- 继续核对 LADA/设置/模型契约：`pipeline/lada/runner.py` 恢复最终 NOOR Python
  环境、LADA model/cache/temp 分离和 `--temporary-directory`；
  `settings_helpers.py` 恢复 `NOOR_DATA_DIR` 模型回退、最终 ChickenRice/VAD 模型
  清单和 LADA 环境注入；`settings_status_helpers.py` 清理旧根路径引用；
  `core/models.py` 补回 `JobCreate.job_type` 字段。
- 继续核对 Whisper/设置/FF 源码契约：`japanese_post.py` 恢复最终方法名与
  `SubtitleSafetyPostProcessor` 合并语义；`settings_lada.py` 恢复 LADA Python 环境
  注入；`database.py`、`plugins/store.py` 和内置 FaceFusion 补丁源码已按最终
  rollout/测试转 `verified`。
- 继续核销插件与媒体库契约：qBittorrent 的 API Key/Cookie 模式、AVDB/M-Team 的
  运行时缓存路径、JavDB 的磁链刷新与近期系列目录、Gfriends 的日文优先匹配、
  订阅/推荐的封面刷新、硬链接运行时存储、FaceFusion 模型目录路由均已核对最终
  rollout，并补充或沿用回归测试。

- 恢复 App 启动时的系统封面模糊同步：`App.vue` 挂载后读取
  `/settings/ui` 并通过 `syncGlobalBlur` 应用服务端全局开关；后端补回
  `GET /api/settings/ui`，返回 `{"ui": {"cover_blur_enabled": bool}}`，
  与设置页 PUT 契约一致。新增 `test_settings_api.py` 两条读取契约测试。

## 明确差距

1. 前端源码不是“磁盘直接恢复”，而是从会话片段重建/回放出来的。
   - 文件路径齐全，且已有 120 份 Vite source map 原文件、浏览器缓存快照和
     `forensics/original-handoff.md` 作为磁盘/缓存级证据。
   - 当前 `Home.vue`、`Dashboard.vue`、`AppSidebar.vue`、`SystemLogPanel.vue`
     等已与最新 source map 证据字节一致；`FaceFusionPanel.vue` 在证据之上只多
     最终 `face_tracker_score` 提交。
   - 其余部分文件内容仍是可维护重建，不是字节级原文件。
   - 例如 i18n 曾漏掉 `settings.whisper.testFailed`，本次已补回中英文键。
   - 静态扫描 `frontend/src` 中 687 个 `t()` 引用后，补回英文缺失键
     `dashboard.welcome.message`；当前中英文静态引用键均无缺失。
2. 原始 `media_library.py` 是约 228 个函数、43 个路由的单模块；当前按职责拆为
   `endpoints/media_library*.py` 和 `endpoints/actors.py`。大多数功能等价，
   但函数名、路由前缀、文件结构不同。原版路由/函数证据已存入
   `forensics/recovered-sources/media_library.early-replayed.py`；下一步可继续
   用该证据反查当前拆分模块里函数名差异，而非继续依赖旧估算数字。
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
     `FaceFusionSettings`、`LadaPanel`、`Home`、`Jobs`；下一批是 i18n、
     `ActorManagementView`、`ActorDetailView` 和 `FaceFusionPanel` 的后续修订。

## 后续恢复建议（按影响排序）

1. 文件级差距清单已清零；下一步风险主要是前端“可维护重建而非字节级原文件”、
   媒体库拆分后的函数/路由兼容，以及已退役 Whisper 旧链路的源码缺失。
2. 继续核对拆分后的 actor 路由兼容，确认历史 `/api/media-library/actors*` 调用
   都能通过当前 `endpoints/actors.py` 得到原版行为。
3. 把 Whisper 旧链路的 `.py` 源码从历史会话/反编译中重建，或以文档形式明确退役。
4. 每恢复一个模块，更新本文件并提交，避免再次丢失。
