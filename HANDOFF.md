# NOOR Project Handoff

Last updated: 2026-08-24 Asia/Shanghai

### 2026-08-24 第十七轮：推荐到下载提交前闭环

- 只读验证推荐、订阅、资源搜索和下载器解析链路：最新推荐返回 12 项，
  已提交订阅 `CJOD-528` 不再出现在推荐中；推荐资源摘要能选出
  `qbittorrent` 兼容下载器。
- `MIDA-727` 全局资源搜索返回 1 个作品、5 个 JavDB 资源；首项解析保持
  magnet、`preferred_downloader=qbittorrent` 和 compatible downloader，统一
  下载对话框可正常打开。未点击最终“推送下载”，没有创建新任务。
- 页面性能实测：缓存后的推荐首卡约 1.1 秒、首封面约 3.3 秒；订阅卡和
  封面约 0.62 秒。封面代理缓存响应约 4–8ms；离开推荐/订阅页后无动作或
  轮询 API 残留，只有首页复用的插件图标请求。
- 恢复 smoke 新增订阅排除、资源兼容、全局资源搜索及下载对话框提交前检查；
  完整运行通过：`HTTP_ERRORS []` / `CONSOLE_ERRORS []`。未改活动业务源码。

### 2026-08-24 第十六轮：媒体详情 NFO 与演员 TMDB 联合核对

- 使用真实 Emby 项目 `19815` 核对 `DVAJ-727-C.mp4`：详情接口按精确
  stem 读取 `DVAJ-727-C.nfo`，原文标题、简介、演员和文件路径均与 NFO
  一致。该 NFO 不含 director/uniqueid，空 `directors/provider_ids` 属正确空态。
- 演员 `4201` 的 Emby ProviderIds、TMDB/IMDb 外链和详情页图标动作一致；
  当前未配置 TMDB Key 时，单人补全返回明确配置提示，批量预览显示 0 候选、
  空态和禁用的应用按钮，未触发任何写入。
- 恢复 smoke 新增精确 NFO 详情、TMDB 批量空态及演员外链检查，并将 JavDB
  稳定性检查改为等待非 skeleton 卡片。完整 smoke 通过：
  `HTTP_ERRORS []` / `CONSOLE_ERRORS []`。未修改活动业务源码。

### 2026-08-24 第十五轮：FaceFusion / JavDB 逐页行为固化

- 从恢复会话 `019ea647-0e81-7d81-9b62-558364a36e3f` 接续逐页行为核对，
  实测媒体库卡片打开 FaceFusion 并扩展到全宽后，预览区稳定位于右上，
  其下源脸区与执行/输出参数区保持两列且没有重叠。
- JavDB 演员目录实测进入演员详情再返回后，卡片数和三行布局均保持不变；
  实时卡片数量不作为固定契约。
- `forensics/smoke_restored_pages.js` 已加入上述两项回归检查。完整 smoke
  通过：`HTTP_ERRORS []` / `CONSOLE_ERRORS []`。本轮未改活动业务源码。

## Recovery Note (2026-08-23)

- The original `/home/kinax/noor` source tree was deleted. Recovery evidence,
  forensics, and the audit workspace live in `/home/kinax/noor-restored`;
  the active restored application source is `/home/kinax/noor`.
- Restored application source is now running from `/home/kinax/noor`. The
  original path carries the current recovery runtime data; the pre-restore
  `data/` backup is at `/home/kinax/noor-data-original-20260824`.
- The recovered frontend runs at `http://192.168.31.3:5173/` and the recovered
  backend listens on `127.0.0.1:9898`, both launched from `/home/kinax/noor`.
- Original-handoff evidence is archived at
  `/home/kinax/noor-restored/forensics/original-handoff.md`.
- Disk/browser source-map evidence is archived under
  `/home/kinax/noor-restored/forensics/raw-vite-sourcemaps/` and
  `/home/kinax/noor-restored/forensics/frontend-snapshots/`.
- The original Git pack was not recovered from the raw disk image. Current source
  is a mix of byte-level source-map evidence, early pre-takeover backup, rollout
  replay, preserved bytecode contracts, and verified reconstruction. The gap
  audit is in `/home/kinax/noor-restored/forensics/recovery-gap-audit.md`.
- Do not restore retired subscription/wash recommendation modes, online actor
  mapping upload, or the old Whisper multi-chain source.

### 2026-08-24 第九轮：候选池后台 stale 状态恢复

- `data/av_recommend/candidate_pool.json` 中残留 `background.running=true`，且
  `finished_at` 早于 `started_at`，导致完整推荐候选池后台扫描在非 force 路径
  上永久跳过。
- `plugins/av-recommend/backend.py` 新增 stale 状态识别：存在 `finished_at`、
  `last_full_scan.at` 新于 `started_at`，或启动时间超过 24 小时时，后台任务会
  被修正为 idle，`background_tasks()` 不再展示为 running。
- 后端重启后已验证 `127.0.0.1:9898/api/health` 健康，候选池任务
  `av-recommend.candidate-pool` 状态为 `idle`，后台任务总数仍为 7。
- 验证：后端 `310 passed, 8 skipped, 1 warning`；前端生产构建通过；14 个官方
  插件全部 `NOOR_PLUGIN_OK`；恢复页 smoke 为 `HTTP_ERRORS []` /
  `CONSOLE_ERRORS []`。

### 2026-08-24 第十轮：后台任务页纳入浏览器冒烟

- `forensics/smoke_restored_pages.js` 新增 `/jobs/background` 路由覆盖，并验证
  `完整推荐候选池` 后台卡片存在、状态为 `待命`。
- 当前恢复页 smoke 仍为 `HTTP_ERRORS []` / `CONSOLE_ERRORS []`。

### 2026-08-24 第十一轮：审计工作区端口文档收敛

- `/home/kinax/noor-restored` 内残留的恢复期 `9899` 引用已统一收敛回 `9898`，
  包括 `AGENTS.md`、`frontend/vite.config.ts`、`HANDOFF.md`、`RECOVERY.md`。

### 2026-08-24 第十二轮：JavDB 移除失效 Gfriends 自动接管

- `plugins/javdb/frontend/page.js` 清除调用已不存在的 `sdk.avatar.resolve`
  死代码。最终 SDK 契约只提供 `sdk.avatar.candidates`，Gfriends 只作为演员
  资料编辑时的候选头像库，不再尝试全局接管 JavDB 头像。
- `backend/tests/test_final_frontend_recovery_contract.py` 新增回归断言，
  锁定 JavDB 不再出现旧 `avatarResolve` / `detectAvatarProvider` 路径。
- 验证：JavDB 演员深链面板仍正常渲染，`node --check` 通过，14 个官方插件
  全部 `NOOR_PLUGIN_OK`。

### 2026-08-24 第十三轮：补齐插件 SDK 已声明基础 UI

- `PluginHost.vue` 补齐 `page`、`search`、`textarea`、`skeletonGrid`、
  `dialog` 和 `previewImage` 等 SDK 组件，`button`/`input` 也补上
  `active`、`disabled`、`onKeydown` 等文档契约字段。
- `previewImage` 现在为 JavDB / 推荐中心详情图库提供统一的 NOOR 预览弹窗；
  qBittorrent / Xunlei / MDC-NG 的文本域已切换到共享 `sdk.ui.textarea`。
- `PLUGIN_SDK.md` 的已可用清单与实现对齐；恢复页 smoke 新增 qBittorrent
  新建任务共享文本域、系统 Webhook 教程/复制、Whisper 保存验证。
- 验证：后端 `311 passed, 8 skipped, 1 warning`；前端生产构建通过；14 个官方
  插件全部 `NOOR_PLUGIN_OK`；恢复页 smoke 为 `HTTP_ERRORS []` /
  `CONSOLE_ERRORS []`。

### Latest Recovery Update (2026-08-24)
### Latest Recovery Update (2026-08-24 第八轮)
- Restored `frontend/src/components/ui/Tabs.vue` to the original sliding-indicator
  implementation. The recovery-time `scrollIntoView`/`offsetLeft` variant was a
  reconstruction-only drift; original read snapshots and the Chromium Vite cache
  both use `getBoundingClientRect()` for the active tab indicator. The file is now
  byte-identical to `vite-cache-chromium/latest/src/components/ui/Tabs.vue`.
- Verification after the restoration: backend full pytest `308 passed, 8 skipped,
  1 warning`; frontend production build passes; all 14 official plugins report
  `NOOR_PLUGIN_OK`; restored-page smoke has no HTTP/console errors.

- Restored recommendation Emby-library exclusion and filtered summaries in
  `plugins/av-recommend/backend.py`: `_library_profile()` now reads persisted
  `EmbyItemCache` codes so already-imported works stay excluded after backend
  restarts, and the recommendation cache key includes the library code count and
  fingerprint. The API response now returns `filtered` with reason counts and
  examples for missing code, ignored, disliked, upgrade-not-improved, and
  score-too-low candidates. Added regression coverage. Backend full pytest:
  `308 passed, 8 skipped, 1 warning`; frontend production build passes; all 14
  official plugins report `NOOR_PLUGIN_OK`; restored-page smoke has no
  HTTP/console errors.
- Restored history/whisper diagnostics in `History.vue` and
  `useJobRuntimePresentation.ts`: recommended-diagnostic summaries and report
  scoring are back, task cards again show Whisper strategy chips, external tasks
  honor `can_cancel`, and completion times use the current UI language.
- Restored recommendation-card volume in `plugins/av-recommend/backend.py`:
  recommendation cache keys now include the requested limit, so switching
  between 最新推荐/完整推荐 no longer returns one fixed 48-item page. Added
  normalized-code dedupe so stale candidate-pool duplicates such as `MIDA-727`
  and `FC2-PPV-1844862` do not appear twice.
- Added regression coverage for both fixes and verified the recommendation API
  returns requested counts for latest/full modes (`20/48/60/100`). Backend full
  pytest: `305 passed, 8 skipped, 1 warning`; frontend production build passes;
  all 14 official plugins report `NOOR_PLUGIN_OK`; restored-page smoke has no
  HTTP/console errors.
- Restored the original local backend port contract: frontend proxy and runtime
  documentation now target `127.0.0.1:9898` instead of the recovery-time `9899`.
  Browser smoke after the switch reports no HTTP 4xx/5xx or console errors.
- Locked two remaining final contracts found during the port recheck:
  `backend/app/api/local_library.py` now returns `source_key=local-subtitle-library`
  exactly as the 2026-06-26 original snapshot, and `settings_helpers.WHISPER_MODELS`
  restores the original order plus the `ChickenRice JA→ZH` display name. Added
  regression assertions for both. Backend full pytest: `302 passed, 8 skipped,
  1 warning`; frontend production build passes; all 14 official plugins report
  `NOOR_PLUGIN_OK`.
- Final convergence recheck after the last FaceFusion fix: refreshed the 2026-07-08 final-window missing-line scan, reran `version_gap_audit.py` (`131 verified / 0 pending / 0 missing / 6 intentional`), exercised FaceFusion metadata/source-image/background-task APIs, and reran backend tests, frontend build, plugin validation, and restored-page smoke. Backend: `301 passed, 8 skipped, 1 warning`; frontend production build passes; all 14 official plugins report `NOOR_PLUGIN_OK`; browser smoke has no HTTP 4xx/5xx or console errors.
- Restored the final FaceFusion source-image library interaction in
  `frontend/src/components/noor/FaceFusionPanel.vue`: library images now toggle
  directly between 使用/移除 on click, removing the intermediate multi-select and
  add-selected state. This matches the 2026-07-08 21:04 final snapshot and the
  `eaae7fcbb85d` final session diff. Updated the two frontend recovery contracts
  to lock the final behavior. Backend full pytest: `301 passed, 8 skipped, 1 warning`;
  frontend production build passes; restored-page smoke has no HTTP/console errors.
- Refreshed the original snapshot audit after the FaceFusion correction:
  `39 exact / 11 likely / 116 review / 515 drift / 7 expected_absent / 0 missing`.
- Restored the original `NOOR_ENV_FILE` behavior in
  `backend/app/api/settings_helpers.py`: `ENV_FILE` now falls back to
  `PROJECT_ROOT/.env` only when `NOOR_ENV_FILE` is unset, matching the
  2026-07-07 original read snapshot and the env-backed config path used by
  `core/config.py`. Added a regression test that reloads the helper under a
  custom `NOOR_ENV_FILE` and verifies both `ENV_FILE` and `read_env_file()`.
  Verification: backend full `pytest` passes with `294 passed, 8 skipped`,
  frontend production build passes, all plugins validate `NOOR_PLUGIN_OK`,
  and the restored-page smoke run has no HTTP/console errors.
- Continued the final-window missing-line review and fixed the remaining real
  gaps: JAVDB actor-directory pagination now uses filtered actor count after
  local search, JAVDB loading skeletons match the original meta/badge structure,
  and `MediaDetailPanel.vue` returns to the original desktop width
  `lg:w-[min(50vw,960px)]`. The refreshed read-snapshot audit is now
  `36 exact / 10 likely / 120 review / 515 drift / 7 expected_absent / 0 missing`; verification is
  backend `293 passed, 8 skipped`, frontend production build, all plugins
  `NOOR_PLUGIN_OK`, and a clean restored-page smoke run.
- Completed the remaining read-snapshot review classification. The 120 `review`
  rows are accounted for as earlier evidence, documented evolutions, or final
  behavior that must not be reverted; examples include Jobs background tab,
  MDC-NG actor mapping, qBittorrent 5.2 API mode, Xunlei residual delete-and-search,
  and JAVDB deliberately ignoring title-only crack keywords. No further real
  source gap was found in this pass.
- Rechecked the active tree after the latest convergence: backend full `pytest`
  passes with `293 passed, 8 skipped`, frontend production build passes, all
  plugins validate `NOOR_PLUGIN_OK`, the read-snapshot audit remains
  `36 exact / 10 likely / 120 review / 515 drift / 7 expected_absent / 0 missing`,
  and the restored-page browser smoke has no HTTP 4xx/5xx or console errors.
- Completed another backup sweep: `/volume1/noor-recovery-20260810`,
  `/volume1/.1panel_clash`, and the local `noor-*` directories contain no later
  full original source snapshot. The only complete pre-takeover snapshot remains
  the 2026-04-12 tarball; later source is reconstructed from session/source-map/
  runtime evidence rather than a byte-for-byte backup.
- Restored the Whisper translator to the original final behavior: native Ollama
  `/api/chat` plus full `/v1/chat` / `/v1/chat/completions` endpoint preservation,
  structured JSON output, local collapse of nonverbal/repetitive subtitle cues,
  and sanitization of runaway translation loops. Regression tests cover native
  Ollama, structured output, non-dialogue prefiltering, single unnumbered replies,
  and repetitive translation cleanup. Verification: backend full `pytest` passes
  with `293 passed, 8 skipped`, frontend production build passes, plugin validation
  remains all `NOOR_PLUGIN_OK`, and restored-page smoke reports no HTTP/console errors.
- Verified the restored translator against the live Ollama at
  `192.168.31.3:11434` through both `/v1/chat/completions` and `/api/chat`; the
  restored backend on `127.0.0.1:9898` was restarted so the new translator code is
  active for real Whisper/translation tasks.
- Rechecked the remaining high-similarity restored files against their final
  session diffs and original snapshots: JavDB backend/page/style, subscription
  backend/page, `MediaDetailPanel.vue`, `WhisperSettings.vue`,
  `SubtitlePanel.vue`, and `japanese_post.py`. Final behavior is present,
  including the JavDB recent-series directory, subscription cover refresh,
  Emby stream preview fallback, ChickenRice runtime tier/single-chain UI, and
  the recommended subtitle postprocessor. Added a regression test proving the
  recommended postprocessor removes adjacent duplicates and noise-only segments
  while preserving meaningful short dialogue. Verification is now
  `292 passed, 8 skipped`; frontend production build, plugin validation, and the
  restored-page smoke all remain clean.
- Corrected the forensic read-snapshot audit and regression contract. The original
  snapshots through `2026-07-25` are the authoritative evidence set; the
  `2026-08-23` recovery reads are not original final source. The contract now
  locks the 35 original snapshot segments that still match the restored tree at
  `1.000` within the drift window.
- FaceFusion source-map evidence is a baseline, not the final file. Current
  `FaceFusionPanel.vue` now matches the final source-image library direct
  click-to-use/remove behavior, and current `FaceFusionSettings.vue` retains
  `badgeAlwaysVisible` / `faceTrackerScore`; do not overwrite them with the older
  raw source-map versions.
- Verification after the audit correction: recovery-workspace backend full
  `pytest` passes with `290 passed, 1 warning`, and the frontend production build
  passes.
- Expanded byte-level original-source matches from the pre-takeover backup: stable backend/frontend config, tooling, docs, and UI files that were unchanged in the original commit index now have 52 verified rows in `forensics/current-byte-level-matches.tsv`. `test_forensic_byte_matches.py` still rechecks every row against the current tree.
- Verification after the evidence expansion: recovery-workspace backend full `pytest` passes with `283 passed, 1 warning`, frontend production build passes, and plugin validation remains all `NOOR_PLUGIN_OK`.
- Restored the subscription center original card workflow: source/quality metadata, expanded candidate comparison, edit mode, and old-version acknowledgment are back.
- Recommendation center now returns `type: recommendation` and renders maker/series/director as clean names when DBOnline returns Python-style dict strings. Latest mode pulls 最新更新 plus 日榜/周榜/月榜 and keeps only those latest source tags on cards. Full candidate-pool background scans also enrich up to `detail_limit` candidates with actors, categories, maker/series/director, covers, subtitles, cracked signals, and magnet metadata.
- Restored missing scoped styles in `SystemSettings.vue` and `StorageSettings.vue` from original Vite cache evidence: library chips, Webhook box/guide, settings toggle, field rows, directory picker, scan groups, and save/action buttons now use the NOOR visual system again.
- JAVDB actor panels now keep 快速筛选 and 年份/排序 in the same capsule row with a visible divider, matching the requested DBOnline-style compact control bar. Browser smoke also now exercises subscription edit/compare/cancel and JAVDB actor relation deep-link refresh.
- Recommendation exclusion is now locked by a regression test: both live Emby codes and subscription codes are removed before scoring, and a real latest-mode response returns no subscribed `CJOD-528` item.
- Reverted `HardlinkView.vue` to the original MDC-NG direct action path from the 2026-08-23 read evidence. The recovery-time generic `hardlink_source_actions` loader and `/files/hardlinks?q=` route handling were removed; the confirmed duplicate `summary.total_groups` fix is kept, and `test_hardlink_view_source_evidence.py` locks the final source shape.
- Re-checked all three 2026-08-23 HardlinkView read snapshots segment-by-segment; the only remaining difference from the preserved original segments is the confirmed duplicate `summary.total_groups` deletion.
- Restored the visible `文件` page title in `FilesView.vue` and its mobile layout behavior from the original early evidence, while keeping the current `/files` route normalization and actor tab. Added `backend/tests/test_files_view_contract.py` so the `文件 -> 硬链接/演员管理` structure and `/hardlinks` redirect cannot drift back silently.
- Verification: frontend production build passes; backend full pytest passes with `266 passed, 6 skipped`; restored-page smoke covers `/files` plus all main/plugin routes and reports no HTTP errors and no console errors.
- Added a reproducible read-snapshot audit (`forensics/audit_read_snapshots.py`):
  corrected reports are `read-snapshot-audit-original.tsv/.md` and
  `read-snapshot-audit-recovery-session.tsv/.md`. The original snapshot run is
  `35 exact / 11 likely / 119 review / 516 drift / 7 missing`; drift is expected
  for early revisions, final module splits, and retired Whisper multi-chain files
  as classified in `forensics/read-snapshot-audit-classification.md`.
- Locked the final Whisper runtime contract with `backend/tests/test_subtitle_panel_runtime_contract.py`: `SubtitlePanel.vue` starts Whisper with `runtime_tier`, `vad_backend`, and `timing_refiner`, and the settings/profile files keep the runtime-tier UI and payload. Verification is now `269 passed, 6 skipped` plus a clean frontend production build.
- Added reproducible session-diff and final-commit audits under `forensics/audit_session_diffs.py` and `forensics/audit_final_commit_paths.py`. The session-diff manifest covers 520 sections / 477 unique diffs / 126 paths; final commits after 2026-07-14 are all present, and the embedded FaceFusion runtime reports 3.8.0.
- Restored the final FaceFusion `facefusion_face_tracker_score` core setting and added `backend/tests/test_facefusion_final_contract.py` to lock the tracker score, direct source-image library click-to-use/remove behavior, and deletion cleanup.
- Added `backend/tests/test_javdb_series_directory_contract.py` for the recent series directory: series normalization, bounded directory aggregation, series tab/routing, and series cards.
- Verification now passes with `277 passed, 6 skipped`, a clean frontend production
  build, plugin validation, and no restored-page HTTP/console errors.

- File-level recovery inventory is complete: `131 verified / 0 pending / 0 missing / 6 intentional`.
- Restored repo-level `AGENTS.md` with the NOOR recovery search boundaries and runtime commands.
- Added `backend/tests/test_forensic_byte_matches.py` so every row in `forensics/current-byte-level-matches.tsv` is re-verified against the current tree during backend tests.
- Final-window original read-snapshot review is now classified in
  `forensics/read-snapshot-audit-classification.md`. The 2026-07-07 to
  2026-07-25 `review` rows were checked against the current tree at 92.6%-100%
  line containment; missing lines are old imports, old comments, retired layout
  rules, or earlier FaceFusion upstream source, not final behavior gaps.
- Added a final-window recovery contract to `test_final_frontend_recovery_contract.py`
  covering Home badge preference, MediaCard facefusion tag behavior, FaceFusion
  reference/model/source-library markers, and the two-column panel layout.
- Verification: backend full `pytest` now passes with `293 passed, 8 skipped`;
  frontend production build and restored-page smoke remain clean.
- Browser smoke coverage now also opens the M-Team `添加片单` modal and the qBittorrent `qB 设置` / `新建分类` SDK modals. The restored-page run reports `HTTP_ERRORS []` and `CONSOLE_ERRORS []`.
- Restored `App.vue` and `AppSidebar.vue` byte-for-byte from the original DevTools cache snapshot, and restored `PluginManager.loadData()` to the original `/api/plugins` array handling. Recovery-only sidebar viewport/active-path changes were removed to bring the app shell back to the deleted project.
- Unified recommendation resource quality features: resource enrichment now separates real uncensored resources from cracked/leak signals, exposes `has_uncensored`, and returns a consistent `resource_summary.quality_score`.
- Converged plugin API calls in `av-recommend`, `mteam-plugin`, and `subscription-core` frontends onto `sdk.api.plugin()` with a raw fetch fallback; plugin validation no longer reports `PLUGIN_API_SHOULD_USE_SDK`.
- Migrated M-Team's add-album dialog to `sdk.ui.modal`; the shared NOOR modal shell is verified in the browser.
- Migrated qBittorrent's category, settings, and task-removal dialogs to `sdk.ui.modal`; the shared modal shell and category editor are verified in the browser.
- Restored the original qBittorrent management page shape: NOOR topbar tabs, original search card, new-task modal, task time column, 10-per-page pagination, and the original 8-second polling fallback are back. The page now opens a live WebSocket when the plugin SDK exposes `net.webSocket`, sends `overview` updates every 4 seconds, and falls back to polling on any socket failure.
- Restored the original generic plugin WebSocket route `/{plugin_id}/ws/{action}` in `backend/app/api/plugins.py`; noisy overview/metrics streams remain excluded from system logs. `test_plugin_compat_api.py` now locks the route with a WebSocket round trip.
- Converted `av-graph` and `subscription-core` CSS to NOOR design tokens for surface/border/radius colors.
- Restored the final FaceFusion source-image library direct click-to-use/remove interaction and cached-image deletion cleanup.
- Removed two runtime 400s found in restored-page checks: Gfriends avatar helper now returns `ok:false` when the plugin is disabled, and TMDB actor preview returns `ok:false` when no TMDB API key/TMDB ID is available. Actor detail no longer sends an automatic TMDB preview unless a key is configured.
- Plugin host now skips standalone page loading when a plugin has no `frontend.entry`; AVDB is restored as a resource provider only and no longer triggers an assets `page.js` 404.
- Disabled read-only plugin actions (`stats/sync/overview/device_info/tasks/about/device_config`) now return `200 ok:false` empty state instead of 400. Gfriends, MDC-NG manual, qBittorrent, and Xunlei remote pages render an unavailable state without console errors.
- JavDB actor directory now probes Gfriends plugin state once on mount and skips per-actor avatar resolution when Gfriends is disabled; it no longer fires a redundant `resolve` request for every actor card.
- Restored qBittorrent runtime config from original evidence and enabled the plugin. qBittorrent is reachable as v5.2.3, resource search now reports `qbittorrent` as compatible/preferred, and the pending subscription `CJOD-528` was successfully submitted to qBittorrent.
- Added `forensics/restore_plugin_downloader_config.py` so downloader config can be restored reproducibly from the preserved original read snapshots without hardcoding credentials in the script.
- Hardened resource download resolution: `PluginRuntime.resolve_resource_download()` now derives requirements from the resolved URL, backfills compatible enabled downloaders, and restores the preferred downloader when a provider/cache returns a stripped resource. This prevents subscription push from incorrectly reporting "没有已启用的兼容下载器" for old cached resources.
- Recommendation live-library exclusion and Knowledge Core indexing now use the original media-library adapter only. The recovery-only Items fallback has been removed from both core paths, so Emby failures surface as normal warnings/errors instead of silently switching data sources.
- Restored the pre-split `media_library` module surface: every top-level symbol from the final recovered `media_library.final-replayed.py` except the intentionally omitted `base64` import is now resolvable from `app.api.endpoints.media_library`. Public helpers and actor APIs delegate to the current split implementation; remaining legacy actor helper names are backed by a lazy compatibility module so old callers do not need the retired one-module implementation.
- Removed the recovery override from `main.py`; media library now uses the original Emby adapter routes. Emby calls in the media library were hardened with `trust_env=False` so the host system proxy cannot turn LAN Emby requests into 502s.
- Restored media-library NFO lookup for exact video stems such as `DVAJ-727-C.nfo`; detail responses now also expose `original_title`, `overview`, `provider_ids`, and `directors` again.
- Added a reproducible browser smoke at `forensics/smoke_restored_pages.js`; it covers main routes, actor routes, media detail, JavDB actor routing, recommendation/subscription/qBittorrent pages, and resource search. Current run has no HTTP 4xx/5xx and no console errors.
- Second evidence pass: rehashed current source against the original read snapshots, Vite source maps, browser cache snapshots, and full path inventory. The recovered raw Git packs are unrelated to NOOR (`forensics/raw-pack-provenance.md`), and LADA's embedded `pyproject.toml` was added as the newest byte-level match.
- Media-library legacy private signatures now match the original recovered surface: actor listing uses `q`/`include_ignored`, hardlink scan/save/enrich helpers use their original parameter names, mapping index/save/preview wrappers were restored with the original arity and keyword order, and `_fetch_emby_item_info` is again the original config-only wrapper. A signature regression test was added beside the symbol-parity tests.
- Verification: frontend production build passes; backend full pytest passes with `262 passed, 1 warning`; media-library libraries/items/detail, qBittorrent overview, FaceFusion preview metadata, source image library, Emby webhook system log, and full-mode recommendation responses all returned healthy results.

## Latest Recovery Update (2026-08-24 第四轮)

- Restored the Whisper runtime path contract in `backend/app/pipeline/whisper/engine.py`:
  `_resolve_whisper_storage()` now returns NOOR `whisper_model_dir` /
  `whisper_cache_dir` / `whisper_temp_dir`, applies network and HuggingFace cache
  environment, and `_get_model_runtime()` uses it when loading faster-whisper
  models.
- Restored the same runtime path wiring in `whisper/orchestrator.py`:
  `_get_output_dir()` falls back to `whisper_temp_dir/whisper_jav` and segment WAV
  files are written under `whisper_temp_dir` instead of the OS temp directory.
- Added regression tests for runtime directory return values and orchestrator
  output placement. Backend full pytest: `301 passed, 8 skipped, 1 warning`.
- Refreshed the original snapshot audit after these fixes:
  `37 exact / 10 likely / 120 review / 514 drift / 7 expected_absent / 0 missing`.
- Restarted the recovered backend on `127.0.0.1:9898`; `/api/health` is healthy.
- Source changes since the previous audit commit are `df2d4fd`, `3b79fa6`,
  `33c4e75`, and the Whisper runtime-path commit in this round.

- Restored the missing `WhisperSettings.vue` strategy-card CSS from the original
  `2026-07-07T0857_37b2f1b9..._800-875` snapshot, plus the card head/title/meta/chip
  styles used by the current runtime-tier and model-backend cards. Added contract
  assertions so this style surface cannot disappear again. Frontend production
  build passes; computed Whisper strategy card styling is active in the browser.

# Hard Rules

- Audit/evidence workspace: `/home/kinax/noor-restored`
- Active source workspace: `/home/kinax/noor`
- Frontend dev server: Vite on `5173`
- Recovered backend dev server: FastAPI/Uvicorn on `9898`
- Do **not** touch Docker backend on `19898`.
- Do **not** recursively search `/home/kinax`, `$HOME`, `/`, `/home/kinax/Videos`, or `/home/kinax/Music`.
- NFS mounts under home:
  - `/home/kinax/Videos`
  - `/home/kinax/Music`
- Safe code search pattern:
  ```bash
  cd /home/kinax/noor
  grep -R -n "pattern" backend frontend plugins \
    --exclude-dir=node_modules \
    --exclude-dir=dist \
    --exclude-dir=__pycache__ \
    --exclude='*.pyc' \
    --exclude='*.map'
  ```
- Prefer scoped paths. Never add `/home/kinax` as a search root.

## Current Runtime Commands

Backend restart:

```bash
tmux kill-session -t noor-backend-9898 2>/dev/null || true
tmux new-session -d -s noor-backend-9898 -c /home/kinax/noor/backend \
  "/home/kinax/.venvs/noor-backend/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 9898 --forwarded-allow-ips='*'"
sleep 3
curl -s http://127.0.0.1:9898/api/health
```

Frontend usually runs on `5173`; check before restarting:

```bash
ps -eo pid,ppid,etime,stat,comm,args | grep -E 'vite|npm run dev|pnpm run dev' | grep -v grep
```

## Git / Workspace Notes

- Source changes are committed regularly; runtime files under `data/` are ignored.
- Do not assume `git status` noise is from the current task.
- `plugins/av-recommend/` is formally tracked and functional.
- Plugin cache files under `data/plugin_cache/` are ignored and do not create git status noise.
- A repo-level `AGENTS.md` was added to prevent future agents from scanning NFS mounts.

## Architecture Direction

### Plugin/UI Strategy

- Main program defines the visual standard.
- Plugins should use shared SDK/components where practical.
- Avoid each plugin reimplementing tabs, pagination, drawers, filter panels, toasts, submit buttons, and downloader dialogs.
- Existing reusable concepts:
  - `FilterPanel`
  - `MediaCard`
  - `DrawerPanel`
  - `DownloaderDialog`
  - `SubscriptionDialog`
  - `SubmitButton`
  - `Toast`
  - `Pagination`
- `sdk.ui.select()` has been upgraded from a native `<select>` to a capsule-style custom dropdown with NOOR-themed popover options. The shared downloader dialog uses the same visual pattern for its internal selects.
- Goal: plugin SDK proxies/uses real common components, not visually-similar duplicated implementations.

### Resource / Download Flow

- Content/resource plugins provide resources.
- Downloader plugins own push/download dialog and actual submission.
- Resource plugins include/target:
  - `javdb`
  - `avdb`
  - `mteam-plugin`
- Downloader plugins include:
  - `xunlei-remote`
  - `qbittorrent`
  - `transmission`
- PT resources from M-Team should only go to qBittorrent/Transmission.
- Public/non-PT resources can go to Xunlei/qB/TR depending on compatibility.
- Download submission should only report success after the downloader confirms task creation/detection.

## Important Current Config Facts

### Subscription Center Save Path

File: `data/plugins_config.json`

`subscription-core.default_savepath` should be:

```json
"/volume1/data/downloads/av/"
```

`xunlei-remote.savepath` should also be:

```json
"/volume1/data/downloads/av/"
```

Xunlei plugin currently detects paths:

- `/volume1/data/downloads/av/`
- `/volume1/data/downloads/porn/`
- `/volume1/data/downloads/uc/`

### Xunlei Save Path Guard

File: `plugins/xunlei-remote/backend.py`

Current important behavior:

- If payload explicitly sends `savepath`, Xunlei must resolve it to a folder id.
- If it cannot resolve, fail closed with a clear error.
- Do not silently fallback to `mobile_parent_folder_id`, because that downloads to Xunlei default directory.

## Recently Completed / Important Fixes

### Xunlei Remote

- Fixed subscription downloads landing in Xunlei default folder.
- Root cause: subscription sent `/downloads/av`; real NAS path is `/volume1/data/downloads/av/`.
- Added fail-closed path resolution for explicit savepaths.
- Fixed prior issues around:
  - quota limit misreported as unauthenticated
  - retry feedback being wrong
  - delete showing failure after success
  - delete dialog should include deleting downloaded files

### Subscription Core

File: `plugins/subscription-core/backend.py`

Important behavior:

- Xunlei quota-limited subscriptions retry next day at Beijing time `00:05`.
- Old UTC-looking retry values were normalized.
- Duplicate resource re-push guard was added after PRED-757 downloaded multiple times.
- Consumed resource keys are remembered so the same resource is not repeatedly pushed.
- Subscriptions/wash upgrades should be as automatic as possible; avoid unnecessary manual confirmation flows.
- Default save path is unified, not separate subscription/wash paths.

### JAVDB Plugin

- Uses DBOnline API, not direct JavDB API.
- Current tabs are conceptually:
  - 最近更新
  - 榜单
  - 演员
  - 查看记录
- Relation pages are now routed under the plugin subpath so refresh/deep links work:
  - `/plugins/javdb/actor/{id}/{label?}`
  - `/plugins/javdb/series/{id}/{label?}`
  - `/plugins/javdb/director/{id}/{label?}`
  - `/plugins/javdb/maker/{id}/{label?}`
  - `/plugins/javdb/publisher/{id}/{label?}`
  - `/plugins/javdb/category/{id}/{label?}`
- Detail-panel relation badges and actor-ranking cards both push these relation routes and then load `related_movies`.
- Actor relation pages use remote pagination. DBOnline returns `current_page` + `movies` without total, so the plugin estimates one more page only when a full 48-item page is returned.
- The standalone 演员 tab uses DBOnline `/api/options/actors` as the full actor directory and merges `/api/actors?type=0..3` metadata when available:
  - full directory currently returns about 2440 actors with `external_id/name`
  - ranking metadata adds avatar, aliases, Chinese names, and uncensored flags for overlapping actors
  - actor directory UI is compact actor cards; click routes to `/plugins/javdb/actor/{id}/{label?}`
  - actor directory is stable 3 rows per desktop page / 5 rows on mobile, independent of header height
  - actor directory sorts actors with ranking metadata first, then the remaining full options by name; do not foreground-sort all actors by recent updates because that would require expensive per-actor movie probes
  - actor cards and actor relation profile intentionally do not display the raw actor ID
  - actor relation routes default/highlight the standalone 演员 tab. The actor relation header uses a dedicated actor panel, not the generic JavDB control panel; it shows avatar/aliases plus actor-specific quick filters, current-page year selector, sort selector, and current-page genre/category filters, then normal JavDB media cards below
- 推荐 was removed from JAVDB tab and moved to a dashboard widget / recommendation plugin direction.
- Recent update should default to magnet resources and support sort by update/release.
- Filtering includes magnets, Chinese subtitles, cracked where supported/derived.
- Detail drawer should follow main media panel style.
- Resource area in detail should aggregate AVDB / M-Team / JavDB resources.
- Resource source display should avoid heavy nested cards.

### Global Search / Resource Search

- Search should be work-oriented by title/work, not raw resource-name oriented.
- Resource results page should group resources under a work/card.
- If media library already has the work, show an in-library tag and provide media-library entry plus JavDB entry where available.
- Global search modal should show small result counts, then a more-results row.
- Resource result page should support more/lazy loading per provider, but avoid endless high-cost fetches.

### Dashboard / Sidebar

- Dashboard supports grid-style resizable/movable cards.
- Edit mode is entered via floating button.
- Hidden panels should be treated like unmounted to avoid data polling.
- Sidebar system metrics should be plugin-provided via a slot/capability, not hardcoded in main UI.
- System monitor plugin config should decide whether to show on sidebar and overview.

### Logs

- System log panel should behave like a right-side sidebar, not take space inside main content.
- Logging is for development/debugging and should help reveal hidden polling bugs.
- Avoid high-frequency noise such as system monitor metrics.
- Previous logs exposed Xunlei plugin polling while not open; that was treated as a plugin behavior bug, not merely a logging noise issue.

## AV Recommend Plugin Current State

Directory: `plugins/av-recommend/`

Status:

- Functional and staged as a real plugin.
- Official plugin direction: recommendation center built from media-library profile, Knowledge Core, JavDB candidates, resource availability, candidate-pool history, and user feedback.

Files:

- `plugins/av-recommend/backend.py`
- `plugins/av-recommend/frontend/page.js`
- `plugins/av-recommend/frontend/style.css`
- `plugins/av-recommend/plugin.json`

Current capabilities:

- Reads media-library profile from Knowledge Core:
  - media count
  - codes
  - actors
  - genres
  - tags
  - studios/labels
  - actor + category combinations
  - local features such as subtitle/cracked hints
- Pulls candidates from JavDB by recommendation mode:
  - `latest` / 最新推荐:
    - 最新更新
    - 日榜
    - 周榜
    - 月榜
  - `full` / 完整推荐:
    - frontend request reads the persistent candidate pool directly
    - refresh triggers a background pool scan but does not wait for it
    - background scan merges latest update, daily/weekly/monthly rankings, JavDB recommend pages, and JavDB videos pages
    - persistent local candidate pool at `data/av_recommend/candidate_pool.json`
- Full scan depth is controlled by plugin config `full_scan_pages`:
  - default: `5`
  - max: `30`
- Full candidate pool background scheduler:
  - `full_scan_background_enabled`, default `true`
  - `full_scan_interval_minutes`, default `360`
  - plugin runtime now starts/stops plugin `start_background` / `stop_background` hooks generically
  - background scans also enrich details for up to `detail_limit` candidates so full recommendations can rank without foreground JavDB detail calls
- Enriches details for candidates up to config limits.
- Scores recommendations using:
  - actor preference
  - category/tag preference
  - actor+category combination preference
  - studio/label preference
  - magnet availability
  - Chinese subtitles
  - uncensored resources
  - cracked features
  - resource size
  - recency
  - positive/negative feedback
  - weak-personalization penalty
  - generic-label penalty
- Resource enrichment calls `runtime.search_resources` for top items and updates resource summary.
- Diversity pass avoids front page being dominated by one actor/tag.
- Modes:
  - `latest` / 最新推荐
  - `full` / 完整推荐
- Recommendation card display includes:
  - current source tags such as 最新更新 / 日榜 / 周榜 / 月榜 / 完整库 Pn
  - 今日新增 marker
  - scoring breakdown including actors/categories/series/director/resource signals
- Response stats include:
  - current candidate count
  - candidate pool total
  - candidate pool today increment, shown in UI as `total+today` such as `473+12`
- Resource quality model:
  - `_resource_features()` distinguishes `is_uncensored` from `is_cracked`
  - item enrichment sets `is_uncensored` and `resource_summary.has_uncensored`
  - `resource_summary.quality_score` aggregates subtitle/cracked/uncensored/source boosts
- Subscription and wash recommendation flows were removed from this plugin UI/backend:
  - no more 订阅推荐
  - no more 洗版推荐
  - recommendation item `type` is now `recommendation`
- Feedback:
  - like
  - dislike
  - ignore
- Dislike picker lets user choose actor/type tags to reduce future similar recommendations.
- Negative feedback is soft: one dislike does not hard-kill actors/types; repeated selected dislike increases penalty.

Recent validation:

```bash
python3 -m py_compile plugins/av-recommend/backend.py
node --check plugins/av-recommend/frontend/page.js
curl -s -X POST http://127.0.0.1:9898/api/plugins/av-recommend/actions/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"payload":{"limit":3,"refresh":true}}' | jq
```

Last smoke result:

- ok: true
- full mode total: 1180
- returned items: 3 with score breakdown and reasons.

### AV Recommend Next Steps

Recommended next implementation order:

1. Formally add/track `plugins/av-recommend/` and ignore cache noise.
   - `.gitignore` now ignores generated `data/plugin_cache/`, `data/av_recommend/`, and `data/subscription_core/`.
   - `data/` runtime files are no longer tracked in git; no non-destructive index cleanup remains.
2. Add subscription-center state awareness: done in `plugins/av-recommend/`.
   - Recommendation backend merges `subscription-core` overview state into items.
   - Cards show 已订阅 / 洗版中 when a recommendation already has an active subscription.
   - Duplicate subscription/wash actions are disabled in the recommendation card.
3. Improve scoring model:
   - time decay for old library preferences: done in `plugins/av-recommend/backend.py`.
   - separate actor preference from genre/tag preference more explicitly: done via score breakdown fields and card score parts.
   - add series/director if data available: done in `plugins/av-recommend/backend.py` and displayed in recommendation cards.
   - add explanations for negative/filtered-out candidates: done via recommendation response `filtered` summary and examples.
4. Improve resource quality model:
   - unify resource quality schema across AVDB/M-Team/JavDB: done in `plugins/av-recommend/backend.py`
   - score new-model uncensored/cracked/subtitle/size/source more consistently: done via `is_uncensored`, `has_uncensored`, and `resource_summary.quality_score`
5. Add recommendation settings:
   - candidate sources on/off: done as `candidate_latest_enabled` / `candidate_rankings_enabled` / `candidate_recommend_enabled` / `candidate_videos_enabled`
   - exploration ratio: done in `plugins/av-recommend/plugin.json` and backend `_apply_recommendation_controls`
   - subtitle/cracked preference strength: done as `prefer_subtitle_strength` / `prefer_cracked_strength`
   - minimum confidence threshold: done as `minimum_confidence_threshold`
6. Add performance controls:
   - cache recommendations per profile/config/feedback: already implemented via 5-minute in-process `_CACHE`
   - limit concurrent JavDB/detail/resource calls: `resource_enrich_concurrency` added to plugin config
   - avoid plugin calls when dashboard card hidden/unmounted

Latest recommendation verification: full backend pytest passes with
`267 passed, 1 warning`; `test_av_recommend_recovery.py` covers confidence
filtering, exploration slots, legacy preference-strength compatibility, and
uncensored/cracked resource separation.

## Known Pitfalls

- Do not revert large UI/history changes casually; many files have accumulated work.
- Gfriends avatar-provider work is in progress but functional:
  - new plugin directory: `plugins/gfriends/`
  - plugin id: `gfriends`, display name: `Gfriends`
  - manifest type is `knowledge_app` because the current manifest tests do not accept `tool`
  - backend builds an alias index from `https://github.com/gfriends/gfriends` `Filetree.json`
  - default asset URLs use jsDelivr `https://cdn.jsdelivr.net/gh/xinxin8816/gfriends/Content/`
  - file names that include cache query strings such as `?t=1607433807` must preserve the query; `_content_url()` now encodes only path segments
  - plugin actions: `sync`, `stats`, `candidates`; backend keeps `resolve` for legacy compatibility
  - cached avatar route uses `/api/plugins/gfriends/images/{image_id}`
  - `PluginHost.vue` exposes `sdk.avatar.candidates({ name, aliases })`, wired to `/plugins/gfriends/actions/candidates`
  - `plugins/javdb/frontend/page.js` still keeps the older `sdk.avatar.resolve` guard, but the final PluginHost SDK only exposes `candidates`; JavDB auto-replacement is therefore inert and actor-management Gfriends candidate selection is the active avatar workflow
  - current main app has no broader actor-avatar surface beyond plugins; future non-plugin pages need their own call site or a shared frontend avatar helper
- Do not reintroduce Nuxt UI full rewrite; project is currently Vite-based.
- Do not use direct JavDB API credentials/token approach; current chosen path is DBOnline API.
- Do not make AVDB a full standalone page again unless explicitly requested; it is currently best treated as a resource provider.
- Do not make MDC-NG a full page; it is mainly a capability button/task provider.
- Do not let plugins poll in background merely because they are installed; route/widget visibility should control data loading.
- When testing search/recommend/resource features, expect dependent plugin/API slowness. Use timeouts and avoid open-ended loops.

## Good First Commands in a Fresh Context

```bash
cd /home/kinax/noor
cat HANDOFF.md
cat AGENTS.md
git status --short | sed -n '1,120p'
ps -eo pid,ppid,etime,stat,comm,args | grep -E 'uvicorn app.main:app|vite|npm run dev|pnpm run dev' | grep -v grep
curl -s http://127.0.0.1:9898/api/health
```

## Latest Gfriends Validation

```bash
python3 -m py_compile plugins/gfriends/backend.py
node --check plugins/javdb/frontend/page.js
cd frontend && npm run build
/home/kinax/.venvs/noor-backend/bin/python -m pytest -q backend/tests/test_builtin_plugin_manifests.py
```

Notes:

- Gfriends candidates for `波多野結衣` return the expected image URLs, including `AI-Fix-波多野結衣.jpg?t=1607433807`.
- Frontend build passed after locking `sdk.avatar.candidates()` and the final plugin-host contract.
- Plugin validation is clean: `scripts/noor-plugin validate plugins` reports all official plugins as OK.
  - `mteam-plugin` and `qbittorrent` custom modal migration advice

### Latest Recovery Update (2026-08-24)

- Locked final frontend recovery contracts for `SystemSettings.vue`,
  `SettingsIndex.vue`, `FaceFusionSettings.vue`, `PluginHost.vue`,
  `LadaPanel.vue`, and `WhisperSettings.vue` in
  `backend/tests/test_final_frontend_recovery_contract.py`.
- The contract test verifies the final MDC mapping, local subtitle library tab,
  FaceFusion badge/tracker settings, plugin routing/avatar/control-panel SDK,
  LADA job navigation/progress, and the Chicken Rice single-chain Whisper UI.
  It also asserts retired Whisper multi-chain markers do not return.
- Final convergence recheck: the last four pre-delete commits are present
  (ignored ghost actors, FaceFusion 3.8.0, face tracker score, JavDB recent
  series directory), all 52 byte-level evidence matches still validate, and the
  restored runtime smoke passes every main route without HTTP or console errors.

### Latest Recovery Update (2026-08-24 第十四轮)

- Restored the final FileTags field ordering contract in
  `frontend/src/api/types.ts` and locked it with
  `backend/tests/test_final_frontend_recovery_contract.py` (commit `7746f42`).
- Restored Xunlei residual handling to the original task-history matching path:
  `restore_candidates` uses the original `_restore_candidates` signature and
  the frontend residual button calls `delete_restore_file` instead of the
  recovery-time local-scan fallback (commit `9970767`).
- Removed the un-mounted recovery adapter
  `backend/app/api/endpoints/media_library_recovery.py` and its standalone
  tests from the active source tree. The evidence remains in
  `noor-restored/forensics`; `main.py` only mounts the original Emby media
  library router and the actor router. Recommendation live-library exclusion
  now has a source-level contract asserting it cannot import that fallback.
- Refreshed the original read-snapshot audit in `noor-restored`: `688`
  snapshots, `40 exact / 9 likely / 98 review / 534 drift / 7 expected_absent /
  0 missing`.
- Verification: backend `308 passed, 8 skipped, 1 warning`; frontend production
  build passes; all 14 official plugins report `NOOR_PLUGIN_OK`; restored-page
  smoke reports `HTTP_ERRORS []` / `CONSOLE_ERRORS []`.

### Latest Recovery Update (2026-08-25：JavDB 详情抽屉)

- 修正插件 SDK 共享影片详情面板被恢复成桌面端 `100vw` 的问题；JavDB
  点击作品后现在与媒体库一致，从右侧显示 `min(50vw, 960px)` 的抽屉，低于
  `1024px` 时保持全宽。
- 同一共享面板也供推荐中心影片详情使用，因此两处交互保持一致。
- 共享面板补齐与媒体库一致的遮罩淡入淡出和右侧滑入/滑出过渡；关闭完成后
  再移除 DOM，重复关闭不会重复触发回调。
- 前端生产构建通过；浏览器验证 1600px 视口下抽屉宽 800px、贴右侧，800px
  视口下全宽，关闭按钮正常；真实详情没有横向溢出，剧照、作品信息、26 条
  资源及内部滚动完整。完整恢复 smoke 的新增 JavDB 契约持续通过；其余运行中
  偶发的 M-Team 等待、MDC 未配置 400 和 Gfriends 空候选均与本次改动无关。

### Latest Recovery Update (2026-08-25：插件连接测试端点)

- 恢复 `POST /api/plugins/{plugin_id}/test` 的原版路由：直接调用
  `runtime.test(plugin_id)`，不再错误转发为通用 action `test`。原始读取快照
  `20260705T17_7cf1aa8b_backend__app__api__plugins.py_300-340.txt` 明确支持该实现。
- MDC-NG 真实连接测试从 `400 unsupported action: test` 恢复为 HTTP 200，
  当前返回目标目录、3 个监控目录及任务统计。
- Gfriends 演员候选并未丢失：演员 4201 当前可返回 17 个候选；恢复 smoke 将
  冷缓存等待从 6 秒放宽到最多 30 秒，避免逐张建立头像缓存时误报。
- 验证：后端全量 `308 passed, 8 skipped, 1 warning`；完整恢复页 smoke
  `HTTP_ERRORS []` / `CONSOLE_ERRORS []`。
- 继续对全部 14 个插件执行真实连接测试：所有端点均为 HTTP 200。AVDB、
  Transmission、Xunlei Remote 在未配置或凭据失效时按契约返回 `ok:false`，
  其余 11 个返回 `ok:true`；未发现第二个通用测试路由缺口。

### Latest Recovery Update (2026-08-26：演员历史路由兼容)

- 对照原版单体 `media_library.py`，当前拆分后的 `actors.py` 保留了全部历史演员
  路由及 HTTP 方法；另有当前扩展的 `/actors/mapping/source`。
- 真实只读核对通过：演员列表当前 549 人；映射已导入；100 人样本中有 1 个
  重复/映射候选组；TMDB 回填候选 0；名称同步预览为 19 个安全更新、2 个冲突；
  演员 4201 详情、2 部影片、删除诊断均为 HTTP 200。映射组“白峰ミウ”的合并
  计划可正确解析目标演员 1344、1 个源演员和 4 部关联影片，未执行写入。
- 常规测试现直接锁定全部历史演员路径和 HTTP 方法，不再只依赖活动仓库里会被
  跳过的外部取证目录 parity 测试；相关测试 `19 passed, 1 skipped`。

### Latest Recovery Update (2026-08-26：JavDB 资源来源恢复)

- 恢复 M-Team 成人区搜索请求；恢复阶段误用 `mode=normal` 会让番号搜索返回空列表。
- 从原恢复会话找回 M-Team 运行配置，明文未进入源码、测试或审计；`SSIS-001` 实测 3 条。
- AVDB 历史地址和运行凭据已恢复；双模式验证确认该令牌使用 `X-API-Key`，不是 Bearer Token。
- AVDB 插件也补充 Bearer 兼容并保留旧 API Key。聚合实测为 AVDB 4、JavDB 6、M-Team 3。

### Latest Recovery Update (2026-08-26：资源优先级与推荐破解信号)

- 统一资源来源顺序为 AVDB、M-Team、JavDB；JavDB 详情和推荐详情均默认选中 AVDB。
- AVDB 资源特征同时检查标题与 tags，可识别标题中的“无码破解”和中文字幕。
- 推荐资源确认改为初排与最终展示两阶段，避免多样化选卡后卡片漏掉资源信号。
- `PRED-878` 实测恢复 `is_cracked=true`、10 条资源和“资源确认：破解”。
- 验证：后端 `313 passed, 8 skipped, 1 warning`；前端生产构建通过。

### Latest Recovery Update (2026-08-26：资源 UI 契约闭环)

- 浏览器 smoke 发现异步聚合完成后仍保留 fallback JavDB 选中态；现两个详情入口都会在最终资源到达时重选优先来源 AVDB。
- 推荐第二阶段资源确认覆盖全部 60 张默认展示卡，不再因动态排名越过固定窗口而漏掉破解信号。
- 完整 smoke 新增 AVDB 首位且 active、`PRED-878` 破解及资源汇总断言；运行结果 `HTTP_ERRORS []`、`CONSOLE_ERRORS []`。

### Latest Recovery Update (2026-08-26：文件 / 硬链接首轮)

- 修复硬链接无数据空态依赖失效 utility class 导致 SVG 撑满页面的问题；空态现在以 64px 图标居中显示，标题、说明和设置入口均在首屏可见。
- 扫描响应统一从嵌套 `summary` 返回 toast 计数，避免扫描成功提示出现 `undefined`；后端分组补齐 `entry_count`，主文件数排序恢复有效。
- 当前 `MEDIA_LIBRARY_SCAN_GROUPS=[]`，原会话、恢复仓和历史环境样例均没有真实 source/hardlink 配对证据，因此未猜测路径、未运行真实扫描或删除。
- 验证：硬链接定向测试通过；后端全量 `314 passed, 8 skipped, 1 warning`；前端生产构建通过；空态浏览器契约通过。

### Latest Recovery Update (2026-08-26：硬链接真实扫描)

- 用户确认扫描组 `av`：主文件 `/home/kinax/Videos/downloads/av`，硬链接 `/home/kinax/Videos/media/av`；配置写入本机 `.env`，不进入 Git。
- 只读 inode 扫描完成并写入运行缓存：776 个作品组、817 个主文件、797 个硬链接、30 个异常组；746 组正常。
- 30 个异常全部为 `orphan_source`，没有未识别番号；当前另有 27 个多主文件组、14 个多硬链接组、5 个仅主文件组、27 个仅硬链接组。
- 后端重载后全部 group 均返回 `entry_count`，最大单组 6 个主文件；真实页面摘要、排序、筛选和展开内容正常。本轮未调用删除、整理或移动接口。

### Latest Recovery Update (2026-08-26：全局字体与设置页可读性)

- 确认 Tailwind 与三套字体均正常加载；视觉异常源于设置子页长期各自维护 9–11px 微型字号，以及若干全局颜色变量缺失，并非字体资源失效。
- 设置页统一卡片标题、字段标签、说明、提示和插件元数据的可读字号与行高；硬链接页的密集元数据及操作文字提升到 12px。
- 全局明确 16px/1.5 正文基线，补齐 `text-body`、`text-tertiary`、`surface-card` 兼容 token；插件宿主统一继承 14px/1.5，保留状态徽标、快捷键和侧栏指标等有意的小字号。
- 验证：后端 `319 passed, 8 skipped, 1 warning`；前端类型检查与生产构建通过。

### Latest Recovery Update (2026-08-26：文件导航、Webhook 字体与服务超时)

- “文件”下的硬链接与演员管理已改用媒体库、任务、历史和设置共用的 NOOR `VisionTabs`，不再维护一套外观不同的页内按钮。
- 修正设置页统一规则漏掉共享 `FieldRow` 实际类名的问题；Emby Webhook 地址固定为 14px 等宽字体、操作说明为 12px 正文字体。硬链接页统一正文栈，分组元数据和列标签提升至 13px。
- 300000ms 超时根因是异步 API 内直接执行媒体目录 `os.walk`/逐文件 `stat`，慢盘或网络挂载会阻塞 FastAPI 事件循环。硬链接扫描、分组加载/丰富及本地字幕索引重建现均卸载到工作线程。
- 后端已重启。真实 8.17 秒硬链接扫描期间并发 30 次健康检查全部 HTTP 200，扫描结果仍为 776 组、817 个主文件、797 个硬链接。
- 验证：后端 `322 passed, 8 skipped, 1 warning`；前端类型检查与生产构建通过。

### Latest Recovery Update (2026-08-26：文件页标题与内容值字体校正)

- 文件页移除 Tab 左侧重复的“文件”标题；全局 topbar 已展示页面名，内容区只保留 NOOR Tabs。
- 演员管理补齐与硬链接管理完全一致的 20px display 标题及 12px 元信息布局。
- 硬链接作品番号（如 `FC2-4720819`）移除 `font-mono`，改用 NOOR display 字体；Emby Webhook URL 同样从 mono 改为 14px display 字体。
- 字体契约测试 `8 passed`；前端类型检查与生产构建通过。
- 后续按用户复核将主文件与硬链接列中的完整路径也由 mono 改为 13px NOOR display 字体，整张分组卡片的内容值风格保持一致。
- 硬链接排序和筛选从裸文字下划线改为 NOOR 轻量胶囊控件，统一默认、悬停、禁用和品牌蓝选中态。

### Latest Recovery Update (2026-08-26：硬链接内联重命名)

- 主文件大小改为紧随文件路径的 NOOR 胶囊标签。
- 主文件和硬链接路径支持双击内联编辑：输入框只编辑文件名主体，原视频格式后缀独立显示并锁定；Enter/确认保存，Esc/取消退出，单击仍延迟触发预览。
- 新增 `POST /api/media-library/hardlinks/rename`：只允许扫描根目录内的视频文件，拒绝目录穿越、空名称和覆盖同名文件；重命名后同步更新硬链接缓存。
- 后端已重启；目录外请求实测返回 400。临时文件测试覆盖后缀保留、缓存路径更新及非法名称，未对真实媒体执行重命名。
- 验证：后端 `330 passed, 8 skipped, 1 warning`；前端类型检查与生产构建通过。

### Latest Recovery Update (2026-08-26：本地字幕库插件完全独立)

- `local-subtitle-library` 不再导入或读写旧 `app.api.local_library`：插件自身负责配置解析、字幕扫描/搜索、SQLite 索引、索引状态和重建操作。
- 插件索引归属 `data/local-subtitle-library/subtitle_index.db`；首次使用会从旧 `runtime/subtitle_library` 索引复制迁移。配置完全由插件运行时持久化。
- 搜索、测试、索引状态和重建中的文件系统操作均使用工作线程，避免媒体路径阻塞 FastAPI 事件循环。
- 设置页删除重复“字幕库”Tab，唯一用户入口为“设置 → 插件 → 本地字幕库”；旧 `/api/local-library/*` 不再注册，实测返回 404。
- 修正插件索引状态契约为前端实际使用的 `index_exists/indexed_count`。当前插件启用、0 个配置路径、索引未建立，与迁移前状态一致。
- 验证：插件独立功能测试通过；后端 `332 passed, 8 skipped, 1 warning`；前端类型检查与生产构建通过。

### Latest Recovery Update (2026-08-26：统一插件私有存储与卸载生命周期)

- 全部插件运行数据统一归属 `data/plugins/<plugin-id>/`：配置为 `config.json`，持久数据、缓存和日志分别位于 `data/`、`cache/`、`logs/`。插件 ID 会经过安全校验，删除操作只允许命中单个插件根目录。
- 旧全局 `plugins_config.json` 和旧数据/缓存目录采用非破坏式首次复制迁移；`.config_migrated` 标记生成后，旧配置不再参与加载，避免已卸载插件的配置复活。旧目录暂留作恢复回滚证据。
- 禁用和升级保留私有目录；卸载默认删除插件代码、配置及运行数据。插件管理器提供“保留插件数据”选项，重装后可恢复；后端支持插件级 `on_uninstall(config, purge_data=...)` 清理钩子。
- AVDB、M-Team、推荐中心、订阅中心、Gfriends 与本地字幕库均已切换到显式插件私有路径。真实迁移核对的 14 份私有配置与旧配置逐项一致，14 个插件处理器重启后全部加载。
- 验证：卸载保留/删除与重装恢复 smoke 通过；后端 `340 passed, 8 skipped, 1 warning`；前端生产构建通过；重启后健康接口正常。

### Latest Recovery Update (2026-08-26：订阅下载状态闭环与界面整理)

- 订阅中心概览会按下载器批量回查已提交任务：qBittorrent 使用保存的 torrent hash，迅雷使用 task id、资源 URL 与任务名回退匹配；查询失败只降级状态展示，不改写订阅或重复提交。
- 下载阶段明确区分等待下载、下载中、暂停、异常、下载完成等待入库及任务缺失；概览新增“下载中/待入库”统计。当前 `MIDA-727`、`CJOD-528` 均实测为 qBittorrent 100%、`stoppedUP`、等待媒体库入库。
- 订阅卡片增加实时进度、下载器、原始状态、速度和保存路径；筛选区增加“下载中/待入库”，候选列表与版本比较收进展开区，编辑和取消等低频操作一并收拢。
- 后端已重启；验证：订阅状态测试 `4 passed`，后端全量 `342 passed, 8 skipped, 1 warning`，前端生产构建通过。

### Latest Recovery Update (2026-08-26：qB 工具栏与 AV 分类路径校正)

- qB 页面工具栏收敛为筛选 Tabs、连接状态、新建任务、分类设置和刷新；版本/认证信息移入连接状态 tooltip，去掉常驻范围与版本徽章造成的拥挤；所有宽度均保持单行，Tabs 独立横向滚动。
- `CJOD-528` 错误保存到 `/volume1/data/downloads/av` 的根因是订阅中心遗留 `default_savepath` 显式覆盖 qB 分类路径，且 qB 默认分类仍为“默认”。
- 运行配置已校正为 qB `category=AV`、`savepath=""`，订阅中心 `default_savepath=""`；qB 实时返回 AV 分类绑定 `/downloads/av`。新任务将由 qB 分类决定容器路径，已完成的历史任务不自动迁移。
- 前端生产构建通过，真实配置与订阅概览接口复核通过。
- qB 的 `qb-overview-row`（5 个指标卡 + 搜索卡）固定为六列单行，窄宽度使用整排横向滚动，不再响应式折成三行。

### Latest Recovery Update (2026-08-26：资源搜索作品键归一化)

- `MIDV-131` 被拆成两个作品的根因是 M-Team 4K 条目的 `smallDescr=4K` 抢先参与番号提取，失败后未继续从标题提取，最终把完整标题写进 `query_key`。
- M-Team 现在依次尝试简介、描述、标题、DMM 产品号和链接；资源搜索前端也会先从插件声明的 `query_key` 中提取标准番号，再作为作品分组键。
- 真实复搜返回 AVDB 2、M-Team 2、JavDB 6 共 10 条资源，唯一作品键为 `MIDV-131`。后端 `343 passed, 8 skipped`，前端生产构建通过。

### Latest Recovery Update (2026-08-26：资源来源下载器绑定契约)

- 下载器候选严格改为“来源已绑定 ∩ 资源能力兼容 ∩ 插件已启用”，不再在来源未绑定时偷偷补入全部下载器；解析接口也会显式返回空候选，避免沿用插件原始提示。
- 插件管理器的多下载器绑定与默认选择从 JavDB 特例升级为通用资源来源能力。AVDB/JavDB 展示所有已启用且声明允许的下载器；M-Team 作为 PT 来源只声明 qBittorrent / Transmission，未启用项不显示。
- 当前配置迁移为：AVDB 绑定迅雷+qB、默认迅雷；JavDB 保持 qB+迅雷、默认迅雷；M-Team 绑定并默认 qB。RSS 推送同步支持多绑定并使用默认项。
- 真实 `MIDV-131` 搜索验证：AVDB/JavDB 候选仅迅雷+qB，M-Team 仅 qB；Transmission 未启用所以所有设置与推送卡均不出现。验证：后端 `345 passed, 8 skipped, 1 warning`，前端生产构建通过。

### Latest Recovery Update (2026-08-26：订阅入库对账与破解洗版实测)

- `CJOD-528`、`MIDA-727` 已由入库对账识别并从“等待入库”转为洗版监控；当前媒体路径分别正确写回订阅记录。
- 修复入库对账错误使用“曾提交候选”的特征覆盖实际媒体库特征：有码文件不会再因历史破解候选被标成已破解，也不会错误消费一个实际未入库的候选。
- 洗版规则增加显式质量跃迁：当前未破解而候选破解、或候选升级为新模型无码破解时直接允许洗版，不受通用分数阈值误拦。
- `MIDA-727` 实际媒体识别为未破解+有字幕（30 分），破解候选为 40 分，命中“破解版本优先”；已真实提交迅雷远程任务 `VP-yhx2vz4tnVcsC6DUQxq8xA1`，订阅卡实时显示下载中。
- 验证：定向 `6 passed`；后端全量 `347 passed, 8 skipped, 1 warning`；9898 服务健康。

### Latest Recovery Update (2026-08-26：洗版自动清理闭环)

- 洗版终态改为“新版本入库 + 旧版本及其硬链接源链自动删除”，不再只生成人工处理建议。
- 入库确认必须同时满足提交候选的质量特征，且出现新路径或原路径文件指纹确实变化；同番号旧媒体仍在时不会提前确认。
- 删除前使用扫描根路径白名单，并对新文件的解析路径和 inode 进行强保护；删除计划包含新文件、其硬链接或上层目录时直接拒绝。原路径替换则记录为无需额外清理。
- 清理成功、无需清理和清理失败均写入订阅事件与 `cleanup_suggestion` 结果，失败不会被静默忽略。
- 验证：定向 `10 passed`；后端全量 `351 passed, 8 skipped, 1 warning`。

### Latest Recovery Update (2026-08-26：媒体版本 U/C/UC 手动标记)

- 作品详情的当前文件可选“未标记 / U 破解 / C 中文 / UC 破解中文”，多版本作品按当前选中文件分别处理。
- 标记会规范化为文件名末尾 `-U/-C/-UC`，自动替换旧标记并锁定视频扩展名；只重命名媒体硬链接，不改下载器源文件，不影响做种校验。
- NOOR 解析器现将 `-UC` 稳定识别为“破解+中文”；重命名后立即更新硬链接缓存、本地同步状态并请求 Emby 刷新媒体库。
- 验证：后端 `353 passed, 8 skipped, 1 warning`；前端类型检查和生产构建通过。

### Latest Recovery Update (2026-08-27：MIDA-727 洗版闭环实测)

- 迅雷任务 `VP-yhx2vz4tnVcsC6DUQxq8xA1` 已 100% 完成，MDC-NG 已生成新硬链接 `MIDA-727-破解.mp4`，Emby 以 sibling `19840` 收录。
- 修复订阅对账只检查多版本去重代表项的问题；现会读取详情 siblings，选择满足提交候选特征且不同于旧路径的具体新版本。
- 真实对账已 `confirmed=1`：订阅恢复 active，当前媒体改为破解版；旧 4.8G 视频、旧下载源硬链接和旧 NFO 已自动删除，新 5.4G 文件与下载源 inode 保持两个链接。
- 旧版同文件干字幕原未纳入清理；现扩展为删除旧 stem 的 NFO/语言字幕等非视频 sidecar，不会触及 `-U/-C/-UC/破解` 等其他版本文件。本次遗留的旧字幕已删除。

### Latest Recovery Update (2026-08-27：版本标记去歧义与 NFO 配对修复)

- 因外部资源中 `UC` 可能仅代表 uncensored/crack，人工标记改为无歧义的 `-破解`、`-C`、`-破解-C`；旧 `-U/-UC/-破解-U` 在重新选择时会被清理为单一标准后缀。
- 定位 `SNIS-063`/`MXGS-146` 详情丢失原因：旧标记接口只重命名视频，完整 NFO/字幕留在旧 stem，Emby 为新 stem 生成了仅标题的最小 NFO。
- 硬链接重命名现会同步移动同 stem 的 NFO 和语言字幕；目标冲突在执行前拒绝，中途失败则回滚视频和已移动 sidecar。
- 两部作品已修复为 `-破解-C`，完整 NFO/字幕重新对齐，Emby 新 item `19844`/`19843` 已恢复演员、类型、简介等详情。两份最小 NFO 保留在 `~/.local/share/noor-recovery/version-mark-20260827/`。
- 验证：后端 `356 passed, 8 skipped, 1 warning`；前端生产构建通过；真实详情 API 均返回完整 NFO 字段。

### Latest Recovery Update (2026-08-27：演员资源搜索封面补全)

- 演员关键词搜索中 AVDB/M-Team 批量结果普遍不带封面，旧逻辑只能从同批 JavDB 磁链资源借用，而 JavDB 首页磁链只覆盖少量作品；因此点进单番号详情后才会出现封面。
- Runtime 现同时利用 JavDB 演员搜索封面目录和单番号详情缓存，对首屏缺封面的唯一番号并发补全；同番号只请求一次，有 48 个番号、12 并发和单次 8 秒上限。
- 真实搜索“吉泽明步”：AVDB 24 个结果中 23 个可解析番号全部有封面，M-Team 21 个番号中 20 个有封面；仅两个无法提取单番号的合集条目保持无封面，避免错配。实测首次聚合 9.4 秒。
- 验证：后端 `357 passed, 8 skipped, 1 warning`。

### Latest Recovery Update (2026-08-27：资源搜索结构化多关键字)

- 资源搜索不再将“吉泽明步 破解”整串交给各插件自行理解；Runtime 先拆出普通搜索词和结构化条件，插件仅搜索“吉泽明步”，再由 NOOR 对归一化资源执行 AND 过滤。
- 已支持正向/负向 `破解`、`中文/中字/字幕`、`PT`、`流出`、`无码/無碼`，例如 `吉泽明步 破解 中文` 和 `吉泽明步 -中文`；来源过滤支持 `来源:AVDB/JavDB/M-Team`。
- 特征判定优先使用插件声明的 `features/requirements`，并对资源标题与标签作保守词汇兜底；不能证明满足条件的结果不会混入。
- 真实 `吉泽明步 破解` 返回 AVDB 13 条已证明破解资源，M-Team/JavDB 当前批次为 0；修复前 JavDB 会返回 12 条普通资源。
- 验证：后端 `359 passed, 8 skipped, 1 warning`。

### Latest Recovery Update (2026-08-27：自然空格标题 AND 搜索)

- 普通用户无需输入 `标题:` 等语法：第一个非结构化词作为插件召回词，后续普通词自动按资源标题 AND 过滤，并可与破解/中文/PT 等条件任意混排。
- `吉泽明步 人妻 破解` 解释为“用吉泽明步召回，标题包含人妻，且资源为破解”；真实结果仅 `SOE-695`。
- 后续 `-合集` 这类普通负词会排除标题命中项；引号保留含空格短语为单个标题条件。不带空格的查询保持原有行为。
- 验证：后端 `361 passed, 8 skipped, 1 warning`。

### Latest Recovery Update (2026-08-27：推荐中心 30 秒超时修复)

- 真实复现推荐冷启动约 60.3 秒：推荐先对 16 个候选确认资源，多样性排序后又对最多 60 张展示卡二次确认，每个番号的多来源请求累积超过前端 30000ms。
- 推荐资源确认增加页面级时间预算：首轮 4 秒、展示轮默认 6 秒；预算到期后取消未完成任务，已完成结果仍参与评分，剩余卡片不阻塞主页。预算可在插件设置调整。
- 批量演员封面补全的详情查询现仅对非番号交互搜索启用；推荐/订阅的单番号资源确认只借用已有封面，不额外阻塞 JavDB 详情。
- 冷启动真实请求现为 20.9 秒、HTTP 200、返回 60 张卡；后续请求命中推荐缓存。后端全量 `362 passed, 8 skipped, 1 warning`。

### Latest Recovery Update (2026-08-27：推荐结果持久缓存)

- 原推荐缓存只有进程内单槽位、5 分钟 TTL；后端重启即丢失，`latest/full` 或展示数量切换也会彼此覆盖，导致重新进入页面频繁重算。
- 推荐插件现将结果按模式、配置、展示数量、媒体库指纹和偏好状态分别持久保存到插件私有运行目录，最多保留最近 8 组，默认有效期 30 分钟并可在插件设置调整。
- 主动刷新会绕过缓存并覆写当前结果；点赞、踩、忽略、重置反馈和候选池变化会清空持久缓存。媒体库内容变化通过缓存键自动切换，避免继续展示已入库作品。
- 真实验证：冷生成 `21.5s` 并写入约 `153KiB` 缓存；重启 9898 后同请求 `2.0s` 返回且响应完全一致。后端全量 `363 passed, 8 skipped, 1 warning`。
