# NOOR 恢复差距审计

更新时间：2026-08-24

## 原版证据复核修正（2026-08-23）

- 演员删除诊断属于原版最终功能，不是恢复期自造：
  `GET /actor/{actor_id}/delete-diagnostics` 同时出现在
  `forensics/recovered-sources/media_library.early-replayed.py`、
  `media_library.final-replayed.py`、`forensics/original-symbol-index.json` 和
  `2a7fe62` 历史演员工作区源码中。`ActorDetailView.vue` 的删除诊断 UI、
  i18n 键、后端 `diagnose_actor_delete` 兼容入口及相关测试均已保留。
- `RecommendedDiagnostics` / `RecommendedDiagnosticsSegment` 在原版读取快照和
  Vite 缓存快照中都有证据，已恢复 `frontend/src/api/types.ts`，避免与
  恢复后的 `History.vue` / 任务历史类型契约脱节。
- 当前验证：`frontend` 生产构建通过；后端全量 `pytest` 240 项通过
  （命令需带 `PYTHONPATH=backend`）。

## 本轮收敛（2026-08-24）

- 媒体库改回原版 Emby 适配路由，不再注册恢复期 `media_library_recovery` 覆盖路由；
  对 Emby 的 `httpx` 调用统一关闭 `trust_env`，解决宿主机系统代理导致
  `192.168.31.10:8097` 返回 502 的问题。
- 修复 `get_main_nfo_impl`：优先读取与视频同名的 NFO（如
  `DVAJ-727-C.mp4 -> DVAJ-727-C.nfo`），再回退番号 NFO；详情接口补回
  `original_title`、`overview`、`provider_ids`、`directors` 字段，与恢复期
  详情面板契约保持一致。
- 推荐中心实时媒体库排除与 Knowledge Core 均已移除恢复期 Items fallback，
  统一走原版 `media_library._list_libraries()` / `_list_items()` / `_get_item()`
  主路径。Emby 不可用时推荐中心返回 warning 空集合，不再静默切换数据源；
  推荐中心强制刷新实测无 warning，实时排除链路可用。
- `media_library.py` 兼容层补回原版公开函数名：配置/解析辅助函数，以及演员
  列表、作品、头像、TMDB、映射同步/清除、名称同步、批量合并等旧入口都可从
  `app.api.endpoints.media_library` 解析；当前拆分后的 actor 辅助函数按
  等价名称/别名回填。新增 `media_library_actor_compat.py` 惰性兼容层，
  原版最终回放文件中的全部顶层符号（除有意省略的 `base64` 导入）现在都可
  由 `app.api.endpoints.media_library` 解析；新增全函数名与顶层符号回归测试。
- 新增可复跑浏览器冒烟 `forensics/smoke_restored_pages.js`：覆盖首页、媒体库详情、
  任务/历史/设置/文件/演员、JavDB 演员路由、推荐中心、订阅中心、qBittorrent 与
  资源搜索；当前运行无 HTTP 4xx/5xx、无 console 错误。Emby webhook 也再次验证，
  系统日志显示 `Emby · 127.0.0.1` 真实来源，并正确记录事件类型。
- 修复侧边栏插件轮询重复挂载：桌面/移动两套侧栏原本都会挂载
  `widget-system` 的 `renderSidebarWidget`，隐藏侧栏仍持续调用
  `/plugins/widget-system/actions/metrics`。现在按 `min-width: 1024px`
  视口只挂载当前可见侧栏，移动侧栏也只在抽屉打开时挂载。
- `PluginWidgetRenderer.vue` 增加标签页 `visibilitychange` 保护：页面切到
  后台时卸载插件 widget 并清理轮询/AbortController，回到前台再重新挂载，
  避免隐藏标签继续占用 CPU、网络和 `nvidia-smi`。
- `widget-system` 后端给 metrics 增加 1 秒结果缓存，多个可见标签页重复请求时不再每次触发 `nvidia-smi` 和 `psutil.cpu_percent(interval=0.1)`。
- 本轮验证：`frontend` 生产构建通过；后端全量 `pytest` 266 项通过。

## 原版媒体库私有函数签名补齐（2026-08-24）

- 对 `media_library.final-replayed.py` 做运行时签名扫描，确认当前
  `app.api.endpoints.media_library` 已能按原版参数名和顺序调用所有原版函数。
- `_list_actors` 恢复原版 `q`、`include_ignored` 及默认参数；忽略的
  ghost 演员按原版语义只在非 include 模式下过滤。
- `_apply_filter_and_paginate`、`_scan_inodes`、`_scan_single_group`、
  `_save_hardlink_groups`、`_enrich_hardlink_groups` 恢复原版参数名。
- `_fetch_emby_item_info` 改回原版 config/emby_id 包装，不再直接暴露
  split implementation 的额外依赖参数。
- 原版 `_actor_mapping_name_index`、`_load_actor_mapping_records`、
  `_save_actor_mapping_records`、`_save_actor_profile_overrides`、
  `_configured_mdc_ng_root_path`、`_configured_mdc_ng_actor_mapping_path`、
  `_build_actor_mapping_merge_plan`、`_preview_actor_name_sync`、
  `_preview_actor_tmdb_backfill` 由惰性兼容层提供原版签名，不再直接
  alias 到签名不同的拆分函数。
- 新增 `test_media_library_legacy_private_signatures_remain_compatible` 和
  原版无 target_actor_id 的合并调用回归测试。
- 验证：后端全量 `pytest` 262 项通过；前端生产构建通过；
  `forensics/smoke_restored_pages.js` 无 HTTP 4xx/5xx、无 console error。

## 第二遍证据复核（2026-08-24）

- 扩展 `forensics/smoke_restored_pages.js`：覆盖设置页全部子页
  （system/storage/lada/facefusion/whisper/local-library/plugins）、
  文件硬链接页、AV 图谱、Gfriends、MDC-NG、M-Team、迅雷远程及无独立入口的
  AVDB 页面；当前运行无 HTTP 4xx/5xx、无 console error。
- 推荐中心补回原版交接中仍待实现的控制项：最低置信度、探索比例、中字/破解
  偏好强度；`exploration_ratio` 和 `minimum_confidence_threshold` 已接入推荐
  输出，`prefer_*_strength` 对旧布尔配置保持兼容；资源确认并发数改为
  `resource_enrich_concurrency` 可配置；完整候选池新增
  `candidate_latest_enabled` / `candidate_rankings_enabled` /
  `candidate_recommend_enabled` / `candidate_videos_enabled` 候选源开关。新增
  `test_av_recommend_recovery.py` 回归覆盖，后端全量测试为 264 项通过。
- 推荐资源质量统一：`_resource_features()` 将真正无码资源与破解/流出信号分离，
  不再把普通 `無碼` 误判为破解；资源富化后同时提供
  `item.is_uncensored`、`resource_summary.has_uncensored` 和
  `resource_summary.quality_score`，使 AVDB/M-Team/JavDB 资源信号进入同一评分
  维度。新增无码/破解分离回归测试，后端全量测试为 266 项通过。
- 插件前端 API 收敛：`av-recommend`、`mteam-plugin`、`subscription-core` 的
  自身接口调用统一改走 `sdk.api.plugin()`，并保留原始 fetch 兼容回退；
  `scripts/noor-plugin validate plugins` 不再报告
  `PLUGIN_API_SHOULD_USE_SDK`；M-Team 添加片单弹窗同步迁移到
  `sdk.ui.modal`，`av-graph` / `subscription-core` CSS 也改为复用 NOOR
  design token。前端生产构建和浏览器冒烟均通过。

- 重新哈希当前源码与原始读取快照、Vite source map、浏览器缓存快照和
  `original-path-inventory.tsv`：补登记 `backend/app/pipeline/lada/source/pyproject.toml`
  与 2026-04-25 原始 `backend/app/pipeline/lada/pyproject.toml` 读取快照的字节级
  一致；`forensics/current-byte-level-matches.tsv` 更新为 45 行。
- 将 `forensics/extracted-packs-work/` 中恢复出的 4 个 Git pack 解码并核对
  提交标题：全部属于 ngx_brotli、OpenClaw/memory-lancedb skill、个人主页
  workflow 等无关仓库，与 NOOR 原版提交索引不一致；结论归档为
  `forensics/raw-pack-provenance.md`，后续不再把该组 pack 当作 NOOR 源码线索。
- 再次确认运行主路径没有挂载恢复期媒体库 fallback：
  `main.py` 只注册当前原版适配器和 actor 路由，
  `media_library_recovery.py` 保留为兼容/测试证据文件但不参与 App 启动。
- 验证：后端全量 `pytest` 266 项通过、前端生产构建通过、
  `forensics/smoke_restored_pages.js` 无 HTTP 4xx/5xx、无 console error。

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
- 前端构建通过，后端 `pytest` 238 项通过；`compileall` 无语法错误。
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
- `.env.example` 已从 2026-06-29 原始会话的完整 `sed -n '1,180p'` 输出恢复，
  并按当天后续两笔提交（FaceFusion 模型卷、可选 Whisper 模型卷）应用到最终态；
  当前文件与证据重建结果逐字节一致。

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
- 存储设置回写修复：`StorageSettings.vue` 的“模型路径/运行时路径”目录选择在
  `confirmDirPicker` 中补回 `modelRootDir` / `runtimeRootDir` 赋值，避免点击
  浏览后选择结果不生效。
- 归档最终原版会话中的前端差异证据：
  `forensics/recovered-sources/final-session-diffs/` 收录 `App.vue`、
  `WhisperSettings.vue`、`MediaDetailPanel.vue` 的原始 `git diff` 片段，
  并生成 SHA256SUMS；这些文件用于继续核对当前重建是否覆盖最终提交。
- 用最终差异核对当前实现：`WhisperSettings.vue` 已覆盖 runtime tier、模型后端、
  VAD/timing refiner、NOOR 环境依赖来源与旧链路移除；`MediaDetailPanel.vue`
  已覆盖 Emby stream 优先/本地 hardlink 回退和标签去重；`App.vue` 已覆盖全局
  搜索、封面模糊快捷键、前端诊断日志与启动时 `/settings/ui` 全局模糊同步。
- 本轮新增 4 个字节级恢复点：`composables/useTheme.ts` 与 `main.ts` 按原始 Vite
  source map 恢复（含原版注释/导入），`components/noor/SubtitlePreview.vue` 与
  4 月预接管原始工作树完全一致，`components/ui/FilterPanel.vue` 与早期会话补丁
  回放结果完全一致。
- `FilterPanel.vue` 的早期会话回放结果已归档为
  `forensics/recovered-sources/FilterPanel.vue.early-replayed.vue`，
  `SubtitlePreview.vue` 的 4 月原始文件已归档为
  `forensics/recovered-sources/SubtitlePreview.vue.early-apr12.vue`，
  并加入 `forensics/recovered-sources/SHA256SUMS`。
- 恢复后前端 `npm run build` 通过，后端 `pytest` 仍为 216 项通过；`useTheme.ts`
  和 `main.ts` 恢复原版后不触发 `vue-tsc` 未使用变量错误。

- 字节级匹配扫描：新增 `forensics/current-byte-level-matches.tsv`，当前
  43 个前后端路径已与 Vite source map、浏览器缓存、早期会话证据或完整读取快照完全一致；其中
  `JobCard`、`JobChainPanel`、`MediaCard`、`VuiProgress`、`History`、
  `LadaSettings` 本次按证据补回仅有的空行/换行差异，已恢复字节级一致。
- 给 `backend/app/api/endpoints/media_library_recovery.py` 的恢复路由补独立
  `operation_id`，消除 FastAPI OpenAPI 重复操作名告警；后端全量测试仍为
  216 项通过。

- 从活盘 `/dev/nvme0n1p2` 恢复出早期原版 `media_library.py` 源码种子，并
  用 2026-06/07 NOOR rollout 补丁回放得到
  `forensics/recovered-sources/media_library.early-replayed.py`（4400 行、
  188 个函数、45 条媒体库路由）。随后将 helper/item-detail/stream 契约内联为
  `forensics/recovered-sources/media_library.final-replayed.py`：204 个函数、
  覆盖原版 43 条路由（另含 `/stream` 与 `/sync-mdc-ng`）。原版公共函数名和
  请求模型已通过当前拆分模块的兼容层补回，剩余差异主要是私有 helper 的内部
  命名和已退役映射实现；该文件已通过 `ast.parse`，可作为原版媒体库路由/函数的
  独立证据，不再只依赖会话片段。
- 路由核对：回放版 43 条原版路由已全部由当前
  `endpoints/media_library*.py + endpoints/actors.py` 承接；4 条旧
  XML/在线映射路由以兼容入口恢复在 `actors.py`，其中
  `/actors/mapping/sync-online` 委托当前 MDC-NG 同步实现。当前另有
  `/stream/{item_id}`、`/actors/mapping/source` 和
  `/actors/mapping/sync-mdc-ng` 等恢复期新增/保留路由。
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
  `media_library.pyc` 顶层代码对象逐项比对，原版最终回放文件中的全部顶层
  符号（`base64` 标准库导入除外）均可由 `media_library` 解析。公开函数、
  当前 actor 等价 helper 与遗留私有 helper 分别由 `actors.py` 和
  `media_library_actor_compat.py` 承载，行为仍以当前拆分实现为准。
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

- 已从最终 rollout 证据补回 `PluginHost.vue` 的 `sdk.avatar` 插件能力：
  `resolve` 调用 `/actions/resolve`，`candidates` 调用 `/actions/candidates`。
  原版会话中该能力由旧 `sdkPost` helper 暴露；当前恢复树没有该 helper，因此用
  同一插件宿主内的 `pluginFetch('/actions/...')` 等价实现，Gfriends 演员编辑头像
  候选选择链路已可继续使用。
- `HardlinkView.vue` 已恢复通用 `hardlink_source_actions`：插件贡献的动作会统一
  渲染在源文件行，支持 `requires_test` 检查并按插件动作路由提交；同时补回
  `/files/hardlinks?q=` 路由搜索参数。原版 MDC 专有 `mdcManualAvailable` /
  `reorganizeSource` 已替换为通用 `loadHardlinkSourceActions` /
  `runHardlinkSourceAction`。

- JavDB 详情样式补齐：`plugins/javdb/frontend/style.css` 此前只恢复到
  `javdb-gallery-nav--next`，详情面板实际使用的原版尾部样式缺失。本轮从
  `original-read-snapshots` 与 `all-original-read-snapshots` 证据补回
  `javdb-gallery-nav--next` hover、`javdb-detail-section`、`javdb-detail-hero*`、
  `javdb-detail-overview`、`javdb-overview-card*`、`javdb-detail-section__*`、
  `javdb-resource-providers`、`javdb-resource-pill`、`javdb-resource-group*`、
  `javdb-detail-meta`、`javdb-meta-row/label`、`javdb-magnets`、
  `javdb-magnet-row/info/name/meta` 与 `javdb-no-data`；`page.js` 详情/资源
  渲染段与原版 2026-06-24 快照一致，前端生产构建通过。
- 后端媒体库旧兼容层已收敛：`media_library.py` 补回原版拆分前的公共函数名
  （演员资料、重名、映射、TMDB 补全、批量合并、删除链等）和旧请求模型导出；
  `actors.py` 恢复 4 条旧映射路由。`test_actor_routes.py` 的 OpenAPI 路由一致性
  测试已更新为完整 43 条原版路由，后端全量测试仍为 216 项通过。
- 插件前端快照核对：JavDB 当前 `page.js` 已覆盖 `served`/`coherent` 快照中的
  全部函数入口，并保留路由化演员/系列等后续功能；推荐中心当前版本覆盖
  `av-recommend.*` 快照函数，唯一移除的 `openJavDB` 是用户后来要求改为作品详情
  面板时的有意变更。
- 从原始 rollout 的 `git status` 快照提取 `forensics/original-status-inventory.tsv`，
  覆盖 617 个唯一状态行、114 个源码路径，补上 `dd000a8` 那次 710 文件 checkpoint
  未记录 `staged_paths` 的路径缺口；Docker、运行时数据与插件缓存路径按恢复策略保留
  在清单中但不作为本地源码恢复目标。
- 进一步从所有 diff/status/stat 输出汇总出 `forensics/original-path-inventory.tsv`
  （572 个相对源码/文档路径），覆盖早期组件化架构、旧 Whisper 多链、旧测试名和
  最终已删除文件，便于以后按时间戳判断某个路径是历史版本还是最终版。
- 清单核对后，真正的源码/测试缺失项都已确认不是最终版缺口：`SidebarMetrics.vue`、
  `SystemMetricsCard.vue`、`useSidebarMetrics.ts` 是已被组件化插件槽位取代的旧实现；
  `test_core_config.py`、`test_knowledge_core.py`、`test_settings_lada_upgrade.py`、
  `test_whisper_api.py`、`test_whisper_frontend_profile_sync.py` 对应职责已由
  `test_core_config_storage_defaults.py`、`test_knowledge_codes.py`、
  `test_settings_lada_recovery.py`、当前 Whisper 契约测试覆盖；
  `whisper/merge.py`、`enhancer.py`、`preprocess.py`、旧 decoupled 链是最终版有意
  删除或收敛后的历史路径。

- 恢复原版插件图标：`mdc-ng-manual` 的 `frontend/icons/service.svg` 与
  `sidebar.svg`、`av-graph` 的 `frontend/icons/service.svg` 已按历史 rollout
  路径补回，插件清单声明与静态资源均通过 HTTP 200 校验。
- 从预接管备份恢复 `frontend/public/img/body-background.png`，前端生产构建不再出现
  该静态资源未解析警告。
- 将 `data/av_recommend/` 与 `data/subscription_core/` 加入 `.gitignore`，并从 Git
  索引移除候选池/订阅状态运行数据，磁盘文件保留。

- 恢复原版前端 TypeScript 严格配置：`tsconfig.json` 已还原为预接管配置，
  新增 `tsconfig.node.json`，并清理 6 处未使用/重复声明；`vue-tsc` 与生产构建均通过。

- 恢复原版 Tailwind 主题 token 与 `/whisper` Vite 代理。`text-accent-*`、
  `bg-bg-*`、`border-accent-*`、`font-display` 等自定义工具类重新进入生产 CSS，
  前端生产构建通过。

- 从预接管备份补回原版配置与文档：`backend/requirements.txt`、`backend/run.py`、
  `frontend/nginx.conf` 及前端设计/一致性文档；当前环境可导入 `run.py` 且依赖项齐全。

- 恢复插件开发/CLI 文档与工具：`plugins/README.md`、`PLUGIN_DESIGN.md`、
  `PLUGIN_DEVELOPMENT.md`、`PLUGIN_SDK.md`、`PLUGIN_CLI.md`、
  `mteam-plugin/MTEAM_API.md`、`tools/noor_plugin/{validate,create,pack}.py` 和
  `scripts/noor-plugin`。`validate plugins` 退出码为 0，create/pack 冒烟通过。
- 恢复 Docker 方向文档：`README.md`、`DOCKER.md`、`docs/DEV_DOCKER_ALIGNMENT.md`；
  仅恢复文档，不恢复或改动 Docker 运行源码。
- M-Team 页面按最终 rollout 恢复为纯 SDK toast，去掉旧版 `alert(msg)` 兜底；
  插件验证不再出现 `BROWSER_DIALOG_FORBIDDEN` 误报。
- 对 27 个同时存在原始 `.pyc` 与当前 `.py` 的模块做顶层符号比对：除
  `settings.py` 的 `CustomPipelineConfig` / `_assert_custom_pipeline_supported`、
  `settings_helpers.py` 的 `parse_custom_config` / `module_installed`、
  `subtitles.py` 的 `_search_xunlei` 外无缺失。这些符号属于已退役的
  Whisper custom pipeline 与旧内嵌迅雷字幕链，按 `intentional` 处理，不恢复。
- 对前端/插件中的 96 个静态 API 调用做路由映射比对：常规路径和动态插件
  `/api/plugins/{plugin_id}/actions/{action}` 均能匹配后端路由；
  `/api/actions/*` 只是 `pluginFetch` 的插件内相对前缀。恢复后端实际启动后，
  `/api/health`、`/api/settings`、`/api/plugins`、`/api/jobs` 均返回 200，
  OpenAPI 暴露 150 条路径。
- 前端函数入口快照比对未发现实际缺失：Dashboard 的旧 `fetchMetrics` 已迁移为
  插件 widget 指标，PluginHost 下载器逻辑已迁移到 `useDownloaderDialog`，
  SystemSettings 本地字幕库已迁移到 `LocalSubtitleLibrarySettings`，
  ResourceSearch 的旧 `openItem` 由当前 `openWork` 等价覆盖。
- 对恢复树做了一次隔离运行冒烟：后端启动在临时端口后
  `/api/health`、`/api/settings`、`/api/plugins`、`/api/jobs` 均返回 200，
  OpenAPI 暴露 150 条路径；前端开发服务器启动后，CDP 浏览器依次打开
  `/`、`/plugins`、`/plugins/mteam-plugin`、`/files/hardlinks`、`/actors`、
  `/jobs`、`/history`、`/plugins/av-recommend`、`/plugins/javdb`、
  `/plugins/gfriends`，页面均渲染且没有运行时异常。
- Gfriends 页面打开时会出现两条 `POST .../actions/stats` 和
  `POST .../actions/sync` 的 400，原因是恢复工作区没有启用该插件，
  插件宿主按契约返回 `plugin disabled`；这是当前隔离验证环境的预期行为，
  不是前端或插件源码缺口。

## 会话 diff 证据与 Whisper 补翻恢复（2026-08-23）

- 新增 `forensics/extract_session_diffs.py`，从原始 rollout 提取 520 个 diff 片段，
  去重后归档 477 个唯一 diff、126 个路径到
  `forensics/recovered-sources/session-diffs/`，并生成 manifest。
- 对每个 diff 执行 `git apply --reverse --check`：63 个可直接反向应用到当前树，
  376 个因当前实现已演进/等价而无法直接反向应用，38 个因会话中滚动输出被截断
  仅作为证据。反向检查不能证明行为完全一致，仍需行为测试。
- 已按 2026-06-20 原版补丁恢复 Whisper 翻译逐条补翻逻辑：批次长度补齐、疑似
  未翻译行逐条重试、批量失败后逐行恢复，而不是直接保留原文。
- 新增 `test_whisper_translator.py`，并在 `test_whisper_runtime.py` 补三条补翻
  回归测试；新增 `test_job_phases.py` 锁定 `facefusion_restore` 阶段文案/默认值；
  硬链接兼容测试补回 `legacy_hardlink_groups_path_impl()` 导出。

- 按 2026-06-09/10 的 JavDB 最终 diff 序列恢复演员专用面板：进入演员关系后不再使用
  通用筛选面板，而是渲染头像、简介、快速筛选、胶囊式年份/排序和类型/标签；刷新
  `/actor/...` 路由时保持 actors tab；头像统一走 `sdk.avatar.resolve` 候选解析并带
  缓存。对应 `javdb-actor-panel`、`javdb-actor-select-badge` 样式已从会话 diff 恢复。
- 本轮后端全量测试为 223 项通过，前端生产构建和插件校验均通过。


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
3. 演员映射表工作流以 MDC-NG 路径同步为主，同时保留旧上传/导入兼容入口：
   - 已恢复：`/actors/mapping/upload`、`/actors/mapping/sync-online`、
     `/actors/mapping/import-latest`、`/actors/mapping/latest-upload`。
   - 已保留：`/actors/mapping/source`、`/actors/mapping/sync-mdc-ng`。
   - `sync-online` 与 `sync-mdc-ng` 当前都委托同一份 MDC-NG 映射同步实现；
     上传/导入接口继续服务于旧前端和外部脚本的兼容调用。
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
     `FaceFusionSettings`、`LadaPanel`、`Home`、`Jobs`、`ActorManagementView`；
     `ActorDetailView` 的原版读档已归档，当前文件含最终“移除 Provider ID”和
     删除诊断补丁；`FaceFusionPanel` 在当前 evidence 之上只多最终
     `face_tracker_score` 提交。下一批是 i18n 和剩余面板的后续修订。

## 后续恢复建议（按影响排序）

1. 文件级差距清单已清零；下一步风险主要是前端“可维护重建而非字节级原文件”、
   媒体库拆分后的函数/路由兼容，以及已退役 Whisper 旧链路的源码缺失。
2. 继续核对拆分后的 actor 路由兼容，确认历史 `/api/media-library/actors*` 调用
   都能通过当前 `endpoints/actors.py` 得到原版行为。
3. 把 Whisper 旧链路的 `.py` 源码从历史会话/反编译中重建，或以文档形式明确退役。
4. 每恢复一个模块，更新本文件并提交，避免再次丢失。


## 原始读取快照与 exec 补丁提取（2026-08-23 晚）

- 从 6 月主 rollout 提取 688 份原版直接 `sed/read` 文件快照，覆盖 101 个路径，
  归档到 `forensics/recovered-sources/original-read-snapshots/`。其中
  `media_library.py`、`FaceFusionPanel.vue`、`ActorManagementView.vue`、
  `FaceFusionSettings.vue`、`JavDB page.js` 都是后续逐文件核对的原始证据。
- 发现 6 月主 rollout 的 6 月后段还有 45 个 JavDB 补丁事件被包在 `exec` 的
  `const patch = "..."` 中，原回放器只扫描直接 `apply_patch`，因此漏掉了
  8 月 4 日最终系列目录补丁链。已新增
  `forensics/replay_original_rollout.py`，支持同时扫描直接 `apply_patch` 与
  exec 内嵌补丁，并把补丁路径改写为相对当前工作树后重放。
- 尝试从 `/.1panel_clash/.../noor-full-pre-takeover-20260412-160609.tar.gz`
  作为回放基准时发现：备份时间早于 4 月 12 日主 rollout 首个补丁，但首个补丁
  期望的 WhisperSettings/i18n 状态不在备份中，说明该备份不是 rollout 的精确
  起点。因此“全历史线性回放”不能直接成立；后续应改为按文件使用会话内的
  原始读取快照作为 pre-patch seed，再回放该文件后续成功补丁。
- 当前恢复树字节级直接匹配证据为 43 个路径（`current-byte-level-matches.tsv`），
  另有大量文件已按源 map/缓存/会话 diff 核对为等价恢复，但不是磁盘原文件。
- 本轮验证：后端 `pytest` 228 项通过、前端 `vue-tsc && vite build` 通过、
  插件校验仅剩余已知警告。

## 全会话读取快照与跨格式回放（2026-08-23 深夜）

- 新增 `forensics/extract_read_snapshots.py`，同时识别旧版 `function_call` 与
  新版 `custom_tool_call` 中的 `sed -n` 读取，并升级为可处理链式命令、多文件
  `sed`、`Chunk ID ... Output:` 包装和 `--paths` 过滤。覆盖 4 月/5 月/6 月/7 月
  删除前会话后，归档 1164 份原版读取快照、203 个路径到
  `forensics/recovered-sources/all-original-read-snapshots/`。
- 升级 `forensics/replay_rollout_file.py`，支持多 rollout、旧/新事件格式、
  直接 `apply_patch` 与 exec 内嵌 `const patch = "..."`，并记录成功状态。
- 当前原始读取快照受会话输出截断和 `git status && sed` 混用影响，不是所有
  路径都能直接拼成完整 seed；后续会按路径选择可用 seed，再结合补丁回放。

## 迅雷远程原版账号/移动端链路恢复（2026-08-23）

- `plugins/xunlei-remote/backend.py` 已从 4 月底首版 seed 起按 rollout 回放，
  再与 6/24、6/25、7/25 原版读取快照核对，接回账号远程
  `account_user_me/account_clients/account_paths/account_submit`、移动端
  `mobile_status/mobile_submit`、试用加速 `try_speed_*`、会员流量 `flow_info`
  和残留任务历史匹配的完整实现。
- 保留当前已经过用户验证的 NAS 安全行为：显式 `savepath` 无法解析为目录 ID 时
  fail closed，不会回退到迅雷默认目录；`.xltd/.xtld` 删除仍限制在配置扫描根目录内。
- `plugins/xunlei-remote/plugin.json` 恢复原版 `insecure_skip_verify`、
  `cookie/file_indices/min_file_size_mb/restore_path_mappings`，并补回账号远程与
  移动端 fallback 配置项；源码不包含原版运行配置里的真实 token/cookie。
- 新增 `backend/tests/test_xunlei_remote_plugin.py` 覆盖账号常量/签名、请求头、
  JWT 过期、残留文件安全删除、显式保存路径 fail-closed 和插件配置字段。
- 本轮验证：后端全量 `pytest` 238 项通过，迅雷插件 `compileall` 通过，
  插件校验仅剩已知 capability/CSS 前缀警告。

## MediaDetailPanel 原版最终形态恢复（2026-08-23）

- `frontend/src/components/noor/MediaDetailPanel.vue` 已切回
  `forensics/frontend-snapshots/vite-cache-chromium/latest/src/components/noor/MediaDetailPanel.vue`，
  SHA256 为 `fb1c04a34d4b9fb81cd26b573c76a8b80bb96e44586aeea1a011d4eb5123cc7a`。
- 该版本与 2026-07-07 原版读取快照一致，保留原版顶栏、宽预览遮罩、
  `detail-panel-topbar`、`preview-overlay`、播放按钮与流地址回退逻辑。
- 移除的是当前重建里混入的早期 `BaseModal` 预览、固定关闭按钮和变体标签；
  这些不是最终原版证据，也不属于用户明确要求保留的新行为。
- 验证：`vue-tsc && vite build` 通过。

## i18n 键位补齐（2026-08-23）

- 全前端静态 `t('...')` 键已校验，中英文使用键 617 个均无缺失。
- 中文补齐 `settings.whisper.segmenter.*` 6 个 Whisper 分段器选项文案；
  英文补齐 `jobs.cancelled`、`jobs.emptyCancelled` 2 个任务状态文案。
- 中英文 `zh.ts` / `en.ts` 键集现已完全一致，前端生产构建通过。

## BaseToast 原版恢复（2026-08-23）

- `frontend/src/components/noor/BaseToast.vue` 已切回
  `forensics/frontend-snapshots/vite-cache-chromium/latest/src/components/noor/BaseToast.vue`，
  与原版 2026-04-12 读取快照字节一致。
- 移除此前重建中新增的硬编码中文标题、duration 计时条和 271 行重设计；
  原版是通用 i18n 消息 toast，不绑定中文文案。
- 验证：`vue-tsc && vite build` 通过。

## 媒体库拆分函数清单复核（2026-08-23）

- 以 `forensics/recovered-sources/media_library.final-replayed.py` 为基准，
  对当前 `endpoints/media_library*.py` 与 `endpoints/actors.py` 做顶层名称复核。
- 原版顶层 286 个名称中，公开名称仅有 `base64` 这个标准库导入名未在当前模块重复；
  其余公开函数、类、请求模型和兼容别名均已由当前拆分模块提供。
- 原版最终回放文件中的全部顶层符号（`base64` 导入除外）现已由
  `media_library` 解析；公开名称、等价 actor helper 与遗留私有兼容函数
  分别由当前拆分模块和 `media_library_actor_compat.py` 承载，路由契约由
  `backend/tests/test_actor_routes.py` 与媒体库路由测试继续锁定。
- 新增 `backend/tests/test_media_library_symbol_parity.py`，用 AST 解析原版最终
  回放文件并断言全部原版公开顶层符号已由当前拆分模块提供，防止兼容层再退化。
- `current-byte-level-matches.tsv` 已更新到 43 个字节级匹配文件，
  `MediaDetailPanel.vue` 与 `BaseToast.vue` 均登记证据来源。

## 字节级匹配登记复核（2026-08-23）

- `frontend/src/App.vue` 已与
  `forensics/frontend-snapshots/vite-cache-devtools/latest/src/App.vue` 哈希一致，
  对应最终浏览器缓存证据；`frontend/src/views/History.vue` 已与
  `forensics/recovered-sources/History.vue.replayed.vue` 哈希一致。
- 通过全量读取快照哈希比对，再补上 4 个原版字节级匹配文件：
  `frontend/src/api/index.ts`、`frontend/src/composables/useJobNavigation.ts`、
  `frontend/src/composables/useToast.ts`、`backend/run.py`。
- `current-byte-level-matches.tsv` 当前为 43 个匹配路径；前端生产构建通过，
  后端全量 `pytest` 238 项通过。
- `.env.example` 已作为字节级匹配路径登记，证据来源为 2026-06-29 原始会话完整
  输出及当天 FaceFusion / Whisper 模型卷两笔 `.env.example` diff。
- 新增完整快照扫描：全部会话读取快照中当前有 76 个整段精确一致（含重复证据），
  其中 `backend/app/pipeline/facefusion/source/facefusion/content_analyser.py`
  按 2026-08-23 完整读取快照哈希一致，已补登记为第 43 个字节级匹配路径。

## PluginHost 路由化 tabs 恢复（2026-08-23）

- `frontend/src/views/PluginHost.vue` 的 `makeTabs` 已补回原版
  `routeConfig` 逻辑：`basePath`、`subPath`、`path` 映射、
  `push`/`replace`、`defaultReplace`、初始路由回填和
  `noor-plugin-route-change` 监听/清理。
- 该缺口会让 `sdk.ui.tabs({ route: ... })` 只切换本地状态，刷新或深链后
  回退到默认 tab；JAVDB 的最近更新/榜单/演员/系列/查看记录均依赖它。
- 同时补回原版插件宿主契约：`sdk.route` 提供 `basePath/path/fullPath/subPath`，
  路由变更由 `noor-plugin-route-change` 事件派发；`sdk.ui` 补回
  `filterPanelRow` / `controlPanelRow`。
- `sdkCleanupFns`、`sdkGet`、`sdkPost` 已按原版命名恢复；`sdkGet`/`sdkPost`
  保留请求耗时与失败诊断日志，`avatar.resolve/candidates` 也改走统一 `sdkPost`。
- `mountPlugin` 恢复“插件页面开始加载/加载完成”诊断日志，耗时记录与系统日志
  面板一致。
- 无头 Chrome 实测：从 `/plugins/javdb` 点击“演员”后 URL 变为
  `/plugins/javdb/actors`，刷新后仍保持“演员”tab。
- 继续点击演员卡片后 URL 变为 `/plugins/javdb/actor/{id}/{label}`，
  刷新后仍保持该演员关系页。
- 验证：前端生产构建通过。

## PluginHost 控制面板契约恢复（2026-08-23）

- `frontend/src/views/PluginHost.vue` 的 `makeControlPanel*` 已按原版 6 月
  快照恢复：支持 `body/left/right/footer/headerActions`、`rows/extraRows`，
  折叠时隐藏扩展行、body 与 footer，折叠按钮保留原版 title 状态。
- 折叠状态同时读取新版 `noor:filter-panel:*` 与旧版
  `noor:control-panel:*`，写入仍统一到 `noor:filter-panel:*`，避免旧插件
  之前保存的折叠状态丢失。
- `sdk.ui.filterPanel/controlPanel` 及其 group/section/row 现在直接暴露
  `makeControlPanel*`，与原版 SDK 命名一致；JavDB 与 AV Graph 的筛选面板
  都走同一实现。
- 无头 Chromium 渲染 `/plugins/javdb` 已验证面板节点带
  `is-collapsible is-collapsed`，折叠按钮 title 为“展开筛选面板”。
- 验证：前端生产构建通过。

## PluginHost 弹窗 titleMeta 恢复（2026-08-23）

- `makeModal` 已按原版 6 月快照补回 `options.titleMeta` 渲染：
  JavDB 多选筛选弹窗传入的计数/说明会显示在标题旁。
- SDK 弹窗样式同步恢复原版布局：`noor-plugin-modal` 使用纵向 flex、
  body 独立滚动，标题为 baseline 行内布局，并补回
  `.noor-plugin-modal__title-meta` 样式。
- 验证：前端生产构建通过。

## HardlinkView 重复统计值清理（2026-08-23）

- `frontend/src/views/HardlinkView.vue` 的“总组数”概览卡片中，
  `summary.total_groups` 被重复渲染两次；已按 Vite 缓存原版证据移除
  第二次渲染和多余空行。
- 保留用户明确要求的通用 `hardlink_source_actions` 插件动作与
  `/files/hardlinks?q=` 路由搜索参数，不回退到旧 MDC 专有动作。
- 验证：前端生产构建通过。

## HANDOFF 与最终行为复核（2026-08-24）

- 根目录 `HANDOFF.md` 已恢复，并适配为恢复工作区路径与 9899 后端端口；
  原始证据继续保留在 `forensics/original-handoff.md` 和
  `forensics/recovered-sources/original-read-snapshots/`。
- 无头 Chromium 复核以下最终路由均正常渲染：
  `/library`、`/files/actors`、`/jobs/background`、
  `/settings/facefusion`、`/plugins/av-recommend`。
- 当前 OpenAPI 的 `/api/media-library/actor*` / `/actors*` 路由与原版
  `media_library.early-replayed.py` 清单一致，覆盖映射、重名、合并、批量合并、
  TMDB 补全、名称同步、头像和删除诊断。
- 重新扫描当前源码与全部 Vite 缓存 / source map / 读取快照后，补登记
  LADA `pyproject.toml` 字节级匹配；`forensics/current-byte-level-matches.tsv`
  保持 45 行。
- 文件级审计仍为 131 `verified`、0 `pending`、0 `missing`、6 `intentional`。

## 插件版本与 Whisper 退役配置清理（2026-08-24）

- 清除四个官方插件 manifest 中的恢复期版本后缀：
  `av-recommend` 恢复为 `1.0.0`，`avdb`、`subscription-core`、
  `transmission` 恢复为 `0.1.0`。后端 9899 重启后 `/api/plugins` 已不再返回
  任何 `-recovered` 版本号。
- 收敛 Whisper 已退役多链路/音频预处理配置：
  `.env.example`、`core/config.py`、`settings_response.py`、
  `settings_updates.py` 与 `settings_whisper.py` 均移除
  `AUDIO_SEPARATOR_MODEL_DIR`、`REAZON_MODEL_DIR`、
  `REAZON_NEMO_MODEL_PATH`、`WHISPER_AUDIO_PREPROCESS_*`、
  `WHISPER_PASS1_PIPELINE`、`WHISPER_PASS2_PIPELINE`、
  `WHISPER_CUSTOM_CONFIG` 等旧字段；当前主链字段统一为
  `chickenrice-zh` + runtime tier + energy VAD + optional timing refiner。
- 中英文 i18n 键集清理后仍为 919 键且完全对称；前端生产构建通过，
  后端全量测试 `238 passed`。
- 无头 Chromium 抽查主页与 `/plugins/javdb`，侧栏、JavDB tab、媒体卡片、
  订阅动作与控制面板均正常渲染，DOM 中没有恢复期标记。
- 文件级审计复跑保持 131 `verified`、0 `pending`、0 `missing`、
  6 `intentional`。

## 插件校验器契约对齐（2026-08-24）

- `tools/noor_plugin/validate.py` 的官方类型与能力清单已对齐当前插件集：
  新增 `knowledge_app`、`source` 类型，以及 `knowledge_view`、
  `recommendation_provider`、`resource_search`、`avatar_library`、
  `external_task_provider`、`knowledge_provider`、`subscription_core`、
  `resource_match`、`remote_tasks`、`sidebar_widget` 等能力。
- CSS 前缀校验改为兼容插件 BEM 命名（`prefix__block`），并为
  `av-recommend`、`mdc-ng-manual`、`subscription-core`、`xunlei-remote`
  登记其实际官方短前缀，消除 `.av-rec-*`、`.mdc-*`、`.sub-*`、
  `.xunlei-restore` 等误报。
- 新增 `backend/tests/test_plugin_validation_tool.py`，断言官方插件目录
  校验时不再出现未知 type、未知 capability 或 CSS 前缀误报。
- 全量后端测试更新为 `240 passed`；`./scripts/noor-plugin validate plugins`
  剩余仅 API SDK 建议、自定义弹窗建议和 design token 建议，不再把正式
  插件类型/能力当未知项。

## 演员详情页导航状态收敛（2026-08-24）

- `App.vue` 的 `activeNavName` 对 `/actors/:actorId` 返回
  `files.actors.title`，避免演员详情页顶部误显示“设置”或旧路由名。
- `AppSidebar.vue` 的 `isActivePath` 对 `/actors/:actorId` 视为
  `/files` 子页面，保证从演员管理进入详情后“文件”侧边栏保持高亮。
- 无头 Chromium 复核 `/actors/4201`：顶部显示“演员管理”，侧边栏
  `文件` 为 active；前端生产构建通过。


## 原版路径清单中的非最终文件分类（2026-08-24）

- 最近复核 `forensics/original-path-inventory.tsv` 中 6 个看似缺失的路径后，
  确认它们都不属于最终 NOOR 源码，不恢复也不标记为运行缺口：
  - `ARCHITECTURE.md`：2026-04-13 早期架构文档，描述旧 Whisper 多链、
    Emby 代理和旧任务模型，已被当前 README / RECOVERY / 运行契约取代。
  - `Dockerfile.frontend`：早期 Docker 部署参考；用户当前要求只预留
    Docker 设计，不恢复 Docker 运行源码。
  - `backend/app/api/emby.py`：早期 Emby 代理模块；当前 Emby 连接、媒体库、
    webhook 已由 settings / media-library / actor endpoints 承担。
  - `backend/app/core/events.py`：2026-04-12 早期事件总线快照；当前任务队列、
    SSE 和插件后台任务不使用该事件总线。
  - `frontend/src/stores/emby.ts`：早期 `Home.vue` source map 里的 Emby store；
    当前媒体库使用 `mediaLibrary.ts` 与 `api/media-library*` 契约。
- `frontend/src/views/Settings.vue`：旧单文件设置页，主体来源为
    `lada-webui` 早期 source map；当前已组件化为 `settings/SettingsIndex.vue`
    及对应分 tab 设置页。

## FaceFusionPanel 源脸图片库多选恢复（2026-08-24）

- 比对 2026-07-08 最终原版快照时发现 `FaceFusionPanel.vue` 缺少
  `selectedLibraryImageIds` / `addSelectedLibraryImages`，导致图片库只能
  单张加入/移除，不能像原版一样多选后批量“使用选中”。
- 已按原版恢复多选状态、批量加入源脸、已使用图片禁用再次选择、删除缓存图时
  同步清理选中状态；默认面板与全宽面板的图片库都保留删除按钮，并增加原版
  `is-active` 选中样式。
- 验证：`vue-tsc && vite build` 通过；后端全量 `pytest` 仍为 `240 passed`。

## 运行时 400 收敛（2026-08-24）

- 无头 Chromium 复核 JavDB 演员页与 `/actors/4201` 时发现两个实际 400：
  Gfriends 未启用仍调用 `gfriends/actions/resolve`，以及 TMDB API Key 未配置
  仍调用 `tmdb-preview`。
- Gfriends 头像辅助改为禁用态返回 `200 {"ok":false,"disabled":true}`，
  `resolve`/`candidates` 不再制造错误响应；JavDB 默认头像/当前封面回退保持可用。
- TMDB 演员预览新增 `_tmdb_preview_guard`：未配置 API Key 或演员缺少 TMDB ID
  时返回 `200 {"ok":false,...}`，`tmdb-apply` 继续显式失败；演员详情页自动补全
  会先读取 `/media-library/config`，未配置 TMDB Key 时直接跳过请求。
- 新增 `backend/tests/test_actor_routes.py` 的 TMDB guard/preview 断言，以及
  `backend/tests/test_gfriends_plugin.py` 的禁用态 no-op 断言。
- 验证：后端全量测试 `243 passed`；前端生产构建通过；插件校验仅保留设计/API
  建议；Puppeteer 复核两个页面均无 Gfriends/TMDB 400。

## AVDB 后端插件页面 404 收敛（2026-08-24）

- 全页面无头 Chromium 复核发现 `/plugins/avdb` 请求
  `/api/plugins/avdb/assets/page.js?t=...` 返回 404；AVDB 是纯资源提供插件，
  `plugin.json` 没有 `frontend.entry`，恢复说明也明确不再做成独立页面。
- `PluginHost.vue` 改为仅在有 `frontend.entry` 时加载插件前端；无入口时显示
  资源提供插件提示并记录 info，不再加载默认 `page.js`。
- 验证：前端生产构建通过；Puppeteer 复核 `/plugins/avdb` 无 4xx/console error，
  页面显示无独立页面提示。

## 禁用插件状态接口 400 收敛（2026-08-24）

- 全插件路由无头浏览器复核发现 Gfriends、MDC-NG 手动任务、qBittorrent、
  迅雷远程在未启用时仍请求只读状态接口，返回大量 400。
- `plugins.py` 将禁用态只读动作统一降级为 `200 {"ok":false,"disabled":true,...}`：
  Gfriends `stats/sync`、MDC `overview`、qB `overview`、迅雷
  `device_info/tasks/about/device_config`；写操作仍保持禁用时失败。
- 对应插件前端补齐 `ok:false` 判断：Gfriends 显示未启用提示，MDC/qB 显示
  加载失败/未启用，迅雷继续按设备连接失败处理。
- 新增 `backend/tests/test_plugin_compat_api.py` 的禁用 overview 空状态断言，
  并调整插件 test 转发测试以显式启用 mock 插件。
- 验证：后端全量测试 `244 passed`；插件校验仅设计/API 建议；四个插件页面
  无 4xx、无 console error，并显示不可用状态。
- 最终全路由无头浏览器复核：主路由与全部插件路由均无 4xx/5xx、无 console error。
- JavDB 演员目录在 mount 时读取一次 `/plugins` 判断 Gfriends 是否启用；禁用时不再对每个演员卡片调用 `resolve`。Puppeteer 实测 Gfriends resolve 请求从 9 次降为 0 次，演员列表仍正常加载。

## 下载器运行配置恢复（2026-08-24）

- 从原版读取快照恢复 qBittorrent 配置并启用：`http://192.168.31.10:8089`、v5.2.3、Cookie 认证可连通。
- 订阅中心不再卡在“没有已启用的兼容下载器”；待订阅 `CJOD-528` 已实际推送到 qBittorrent，任务进入下载状态。
- 新增 `forensics/restore_plugin_downloader_config.py`，从取证快照重建 qBittorrent/迅雷基础配置和订阅默认保存路径，脚本不内联凭据。
- 运行数据文件继续被 `.gitignore` 忽略，不会把本地令牌/密码带入 Git 提交。

## 资源下载解析收敛（2026-08-24）

- `PluginRuntime.resolve_resource_download()` 不再直接信任旧缓存或第三方插件返回的精简资源：
  解析后会按最终 URL 补全 requirements，再通过 `resolve_downloaders_for_resource()` 回填
  当前已启用且兼容的下载器列表与首选下载器。
- 这避免了订阅中心对旧 `best_resource` 误报“没有已启用的兼容下载器”；即使资源字段缺失
  `compatible_downloaders` / `preferred_downloader`，只要下载器插件已启用也能正常推送。
- 新增 `test_resource_resolve_download_backfills_compatible_downloaders` 回归测试。
- 验证：后端全量 `pytest` 为 `252 passed, 1 warning`；前端生产构建通过。
