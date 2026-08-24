# NOOR Project Handoff

Last updated: 2026-08-24 Asia/Shanghai

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
