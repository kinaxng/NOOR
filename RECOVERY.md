# NOOR Source Recovery

This tree is an isolated recovery workspace. It does not replace `/home/kinax/noor`.

As of 2026-08-24 the restored application source is also mirrored to
`/home/kinax/noor`. The original path keeps its pre-existing `data/` directory and
does not carry the large `forensics/` recovery archive; the isolated workspace
remains the authoritative recovery/history tree.

The frontend and backend now run from `/home/kinax/noor` through tmux sessions
`noor-original-frontend` and `noor-original-backend`. The current recovery runtime
data was copied into `/home/kinax/noor/data`, and the pre-restore data was backed
up at `/home/kinax/noor-data-original-20260824`.

## Evidence-Preserving Files

- `backend/app/**/*.pyc` contains 45 Python 3.13 modules recovered directly from the
  raw ext4 image. The files are sourceless modules and can be imported by Python.
- `forensics/recovered-pyc-all-manifest.tsv` records the raw-image offset and original
  module path for every recovered module.
- `forensics/decompiled/` contains best-effort readable output. It is forensic aid only:
  Python 3.13 decompilation is incomplete for some modern opcodes and these files must
  not replace the recovered `.pyc` modules without review.

## Confirmed Recovered Areas

- Whisper pipeline, including orchestration, runtime, engines, translation, merge, and
  decoupled Qwen components.
- Settings, subtitle APIs, media-library APIs, database models, and LADA runner.

## Initial Missing Areas

The raw-image recovery did not contain source for the application entrypoint, task
manager, plugin framework, FaceFusion integration, recommendation/subscription plugins,
or every Vue component. Later recovery added byte-level Vite source maps and rollout
replays for the frontend, but not every component has a single original full-file disk
copy.

Those areas are now reconstructed from verified API behavior and session evidence. They
are deliberately kept as normal source files alongside the preserved `.pyc` evidence;
the recovered bytecode modules remain unchanged.

## Reconstruction Status (2026-08-11)

- Recreated the application entrypoint from an exact session-recorded source read.
- Restored the FaceFusion API, runner, preview worker, and path helpers from exact
  session-recorded source reads.
- Rebuilt the task queue around the recovered job/API contract and verified imports
  for Jobs, Settings, Media Library, Whisper, LADA, and FaceFusion.
- Restored LADA 0.11.1-dev source under `backend/app/pipeline/lada/source` and
  reconnected its dedicated CLI to the recovered runtime. The existing NOOR LADA
  model directory, CUDA device, detection models, and restoration models were
  verified without submitting a video job.
- Recovered compatibility helpers required by the Whisper pipeline after the retired
  optional audio-enhancement chain was removed.
- Reconstructed `pipeline/whisper/strategy.py` as maintainable source and verified
  its presets, aliases, and execution plans against the preserved bytecode.
- Reconstructed `api/settings_whisper.py` as maintainable source and verified its
  normalization, environment update, model-status, and model-list payload behavior
  against the preserved bytecode.
- Reconstructed `api/whisper_presets.py` as maintainable source and verified its
  historical `best` preset behavior against the preserved bytecode.
- Reconstructed `core/config.py` as maintainable source and verified its settings
  fields, environment aliases, runtime paths, and network environment behavior
  against the preserved bytecode.
- Reconstructed `core/models.py` as maintainable source and verified its SQLite
  entities, Pydantic request/response fields, default values, and task timestamp
  serialization against the preserved bytecode.
- Reconstructed `core/database.py` as maintainable source and verified its async
  and sync engine configuration, session factories, and legacy Jobs schema update
  behavior against the preserved bytecode.
- Reconstructed `tasks/job_phases.py` as maintainable source and verified its
  phase normalization, terminal state details, and task progress payloads against
  the preserved bytecode.
- Reconstructed `tasks/manager_helpers.py` as maintainable source and verified its
  task log handling and LADA output-path mirroring against the preserved bytecode.
- Reconstructed `api/settings_response.py` as maintainable source and verified its
  Emby fallback, storage, LADA, Whisper, and network settings payloads against the
  preserved bytecode.
- Reconstructed `api/settings_updates.py` as maintainable source and verified its
  Emby, storage, LADA, and network environment update mappings against the
  preserved bytecode.
- Reconstructed `api/settings_directories.py` as maintainable source and verified
  its allowed-directory checks and browse payloads against the preserved bytecode.
- Reconstructed `api/settings_status_helpers.py` as maintainable source and verified
  its persistent install/model-download status-file behavior and response payloads
  against the preserved bytecode.
- Reconstructed `api/settings_helpers.py` as maintainable source and verified its
  environment-file handling, model catalogue, feature flags, LADA installation
  inspection, version cache, and size formatting against the preserved bytecode.
- Reconstructed `api/settings_lada.py` as maintainable source and verified its LADA
  device parsing, model inventory, local model-size detection, and upgrade metadata
  payloads against the preserved bytecode.
- Reconstructed `api/settings_lada_defaults.py` and `api/settings_lada_upgrade.py`
  as maintainable source and verified their settings persistence, proxy filtering,
  branch selection, and user-facing upgrade failure behavior against bytecode.
- Reconstructed `api/settings_whisper_models.py` as maintainable source and verified
  its Transformers, faster-whisper, and Reazon model-cache lookup and deletion
  behavior against the preserved bytecode using temporary cache layouts.
- Reconstructed `api/settings_whisper_runtime.py` as maintainable source and verified
  its runtime dependency/CUDA inspection, cache detection, status logging, and
  install-requirement decisions against the preserved bytecode.
- Reconstructed the main `api/settings.py` router as maintainable source. Its 18
  routes and all request-model schemas match the bytecode router; the settings,
  Whisper runtime/model/status, and dependency-check endpoints were exercised
  against the isolated running backend.
- Reconstructed the shared `api/jobs.py` router as maintainable source and verified
  its create/list/detail/delete/log/cancel/download/cleanup route contract against
  bytecode; the running task-list endpoint was exercised successfully.
- Reconstructed `api/whisper.py` as maintainable source and verified its task and
  translation route contract, request schemas, strategy selection, and local-path
  handling against bytecode. The running translation health-check and missing-task
  responses were exercised through the isolated backend.
- Reconstructed `api/subtitles.py` as maintainable source and verified its local
  subtitle, online-source, file-content, unique-name, and deletion contracts against
  bytecode. The isolated backend exercised local reads and invalid-download handling.
- Reconstructed the internal `api/local_library.py` subtitle-index module as
  maintainable source and verified its environment configuration, paths, index
  matching, result shape, and router contract against bytecode. The application does
  not register this router; it is imported directly by the subtitle search route.
- Reconstructed `api/endpoints/media_library_helpers.py` as maintainable source and
  verified its environment-backed configuration, media-path mapping, release-tag
  classification, Emby poster URL generation, and local subtitle counting against
  the preserved bytecode.
- Reconstructed `api/endpoints/media_library_item_detail.py` as maintainable source
  and verified item retrieval fallback, sibling sorting, version-tag aggregation,
  preferred-poster selection, and NFO lookup against the preserved bytecode.
- Reconstructed the media-library router's listing and version-deduplication helpers
  in `api/endpoints/media_library_listing.py`. Representative selection, tag
  aggregation, poster fallback, search, filtering, and pagination were verified
  against the matching functions in the preserved router bytecode; the full router
  replacement remains in progress.
- Reconstructed the media-library router's safe deletion helpers in
  `api/endpoints/media_library_deletion.py`. Scan-root restrictions, code-bucket
  folder deletion, sibling-NFO handling, dry-run target previews, and error response
  behavior were verified against the preserved router bytecode using a temporary
  media tree.
- Reconstructed the media-library router's local preview streaming helpers in
  `api/endpoints/media_library_streaming.py`. HTTP Range parsing, invalid-range
  response semantics, suffix-range support, and chunked local-file streaming were
  verified against the preserved router bytecode.
- Reconstructed `api/endpoints/media_library.py` as source, retaining all 13 media
  library routes and the compatibility helpers used by actor and recovery adapters.
  The isolated backend was restarted with the source module active; status and live
  item-list responses were verified successfully.
- Reconstructed `api/events.py` as source and verified its SSE missing-job contract
  after restarting the isolated backend. The router preserves connected, progress,
  log, queued, blocked, terminal, and keepalive event formats.
- Reconstructed the Whisper package entrypoint, core task/type dataclasses, progress
  reporter, decoupled alignment types, and framer selector. The remaining Whisper
  engine, orchestration, post-processing, and merge implementations
  remain preserved bytecode until they can be fully verified.
- Reconstructed `pipeline/whisper/translator.py` as maintainable source. Numbered
  batch parsing, reasoning-field extraction, local-service timeout selection,
  refusal detection, and health-check behavior were verified against preserved
  bytecode and mocked OpenAI-compatible responses. Explicit `/v1/chat` and
  `/v1/chat/completions` endpoints are retained exactly as entered.
- Recovered `pipeline/lada/runner.py` from complete June 25 session captures and
  verified its progress mapping against preserved bytecode. A simulated LADA CLI
  run exercised command construction, subprocess output parsing, phase events,
  completion handling, and the model-directory environment contract.
- Recovered `pipeline/whisper/preprocess.py` from its complete June 29 source
  capture. Separator preset resolution, output selection, passthrough behavior,
  and user-facing errors were compared with the preserved bytecode.
- Recovered `pipeline/whisper/scene_detector.py` from overlapping July 5 source
  captures. Short-segment merging and low-energy long-segment splitting were
  compared against preserved bytecode using synthetic audio arrays.
- Reconstructed `pipeline/whisper/decoupled/recommended.py` from preserved
  bytecode. Noise scoring, Qwen retry gating, lazy model lifecycle, fallback
  metadata, and forced-alignment result construction retain the original contract.
- Recovered `pipeline/whisper/runtime.py` from the complete June source capture,
  the later ChickenRice consolidation diff, and function-level bytecode. Source
  and bytecode produced identical translation queue events and SRT output under
  the same mocked translator, in addition to matching parsing and batching tests.
- Recovered `pipeline/whisper/decoupled/qwen3.py` from its source capture and
  preserved bytecode. Model-cache resolution, language normalization, timestamp
  merging, and all segmentation/merge rules matched across 300 randomized word
  timelines.
- Recovered `pipeline/whisper/decoupled/anime_qwen3_chain.py` from the final
  historical source capture and preserved bytecode. Retry classification matched
  across 2,000 randomized Japanese strings, while accepted Anime, large-v3 retry,
  Qwen3 retry, empty-alignment, and successful-alignment branches produced
  identical result text, source labels, and metadata.
- Recovered `pipeline/whisper/japanese_post.py` from overlapping historical source
  snapshots plus the preserved bytecode's later short-dialogue protection and
  moan-edge trimming behavior. All cleanup helpers matched across 3,000 randomized
  texts, and 400 randomized multi-segment results matched the bytecode end to end.
- Recovered `pipeline/whisper/merge.py` from overlapping source snapshots and the
  preserved bytecode's overlap-collapse and timeline-sanitization additions. All
  merge strategies matched over 1,200 randomized dual-pass inputs, with a further
  1,000 randomized malformed timelines matching the bytecode sanitizer.
- Recovered `pipeline/whisper/engine.py` from four contiguous historical source
  captures and reconciled the later storage edits against preserved bytecode. Every
  function and processor method retains the bytecode constant contract; cache-path
  helpers, sensitivity presets, a mocked Faster-Whisper stream, and generated SRT
  bytes were behaviorally compared.
- Recovered `pipeline/whisper/orchestrator.py` from overlapping historical source
  captures and reconciled preprocessing, Anime-Qwen3 step-down, Reazon, Kotoba,
  phase-based execution, diagnostics, and cancellation against preserved bytecode.
  All 39 pipeline methods and the three task wrapper functions match the Python 3.13
  bytecode instruction shape, constants, names, local variables, and nested code
  objects; the prepared-segment schema and pipeline-enhancer mapping also match.
- Rebuilt the plugin runtime and recovered functional first-party plugin sources for
  JavDB, recommendations, subscriptions, Gfriends, qBittorrent, Transmission,
  Xunlei Remote, M-Team, and AVDB.
- Rebuilt global resource search, browser History API routes, and the Vue recovery UI.
- The full original component tree and several historical advanced interaction surfaces
  remain unavailable as source artifacts; they must continue to be recreated from
  verified behavior rather than treated as byte-for-byte recovery.

- 已恢复 App 启动时系统封面模糊同步：前端读取 `GET /settings/ui`，后端恢复对应读取路由。

- 2026-08-23 新增字节级前端证据恢复：`composables/useTheme.ts`、`main.ts` 按原始
  Vite source map 恢复；`components/noor/SubtitlePreview.vue` 与 4 月预接管原始
  工作树字节一致；`components/ui/FilterPanel.vue` 与早期会话补丁回放字节一致。
  `forensics/current-byte-level-matches.tsv` 已更新到 32 个字节级匹配文件，
  新增回放证据已归档到 `forensics/recovered-sources/`。

- 2026-08-24 将预接管原始工作树中无后续提交证据的稳定文件并入字节级匹配清单，
  新增 `backend/requirements.txt`、前端工具链/配置/文档/主题/背景图等 12 个路径，
  `forensics/current-byte-level-matches.tsv` 当前为 53 个有效匹配。

- 2026-08-23 新增原始 `git status` 路径清单
  `forensics/original-status-inventory.tsv`，并汇总全部 diff/status/stat 输出为
  `forensics/original-path-inventory.tsv`，补上了原版 710 文件 checkpoint 的路径
  记录缺口；清单中的旧组件、旧测试名和已收敛 Whisper 链已逐一核销为更名/退役项，
  当前恢复树不因此产生新的最终版源码缺失。

## Validated Recovery Progress (2026-08-11)

- The isolated frontend and backend are running at `http://192.168.31.3:5173/` and
  `127.0.0.1:9899` respectively.
- Emby media paths returned as `/data/...` or `/volume1/data/...` are translated to
  the host's `~/Videos/...` mount before being passed to LADA, Whisper, FaceFusion,
  or subtitle operations.
- LADA and the recovered Whisper queue have each completed an isolated one-second
  test job. This validates runner integration, queue state, progress callbacks, and
  result writing, but not quality on production videos.
- The file page restores manual hardlink scanning and a dry-run-first deletion flow.
  Deletion is blocked unless scan groups are configured, and the media library's
  right-click delete entry resolves only an already scanned hardlink group before it
  presents the same confirmation dialog.
- `POST /api/webhooks/emby` accepts Emby JSON or text notifications and records a
  concise event in the system log using the actual request address (or the first
  `X-Forwarded-For` address). The settings page exposes the URL, copy action,
  Emby JSON-content-type guidance, and the recent audit log. The legacy route and
  the token-protected media-library route both invalidate the media-library cache
  and expose the sync-state payload used by the frontend.
- The surviving actor APIs support Emby actor browsing, mapped multilingual names,
  duplicate detection, movie lookup, and explicitly selected GFriends avatar writes.
  The list filters invalid Emby people before paginating, supports mapped-name search,
  and browser actor detail routes load independently of the complete actor scan.
  Actor merge, empty-actor cleanup, selected actor deletion, editable actor metadata,
  MDC-NG mapping ingestion, mapping review diagnostics, and guarded TMDB/Emby sync
  flows have been recreated from available behavior. Emby orphan-person deletion
  remains limited by the remote Emby server's metadata/provider state.
- FaceFusion source-image management and frame-preview controls are restored. Opening a
  media detail reads only preview metadata; a preview is generated only after a source
  image is selected and the frame slider is released.
- Storage settings were restored to the final "two roots" contract: model root,
  runtime root, NOOR data dir, and database path are the editable AI storage fields;
  per-module Whisper/LADA/FaceFusion cache and temp inputs were removed from the page.
- System settings, media card FaceFusion badge behavior, and the subtitle/Whisper panel
  were verified against the final rollout patches, including MDC-NG root path,
  fixed/hover FF badge modes, has_facefusion aggregation, and runtime-tier submission.
- FaceFusion source upgrade verification now covers both TensorRT cache routing and
  NOOR's content-analysis skip patch, including idempotent preservation on an already
  patched 3.8-style source.
- qBittorrent and Xunlei Remote plugin contracts were verified against final rollout:
  qBittorrent supports 5.2+ Bearer API-key auth and start/stop control, while Xunlei
  residual cleanup is the simplified delete-then-search flow for `.xltd/.xtld` files.
- Recommendation and subscription plugin pages keep the final latest/full recommendation
  modes, merged candidate-pool stats (`total+today`), subscribe actions, inline detail
  panels, and fallback cover loading after refresh.
- The recovered settings contract, Whisper single-chain modules, and FaceFusion
  runner/API modules were marked verified against the preserved bytecode, final
  parameter defaults, and current test coverage.
- Gfriends was verified as the final avatar-library helper: it no longer takes over
  every avatar, and its plugin page/plugin host expose searchable candidate avatars
  for actor editing.
- Browser Vite source maps from `/tmp/chromium-shared`, `/tmp/cdp-v1WmoE`,
  and the Chrome DevTools profile were extracted and archived under
  `forensics/frontend-snapshots/`. This added original frontend source files as
  byte-level evidence, including the May component tree, `GlobalSearch.vue`,
  early `ResourceSearch.vue`, and late `Home.vue` / `AppSidebar.vue` /
  `FaceFusionPanel.vue` versions.
- Inline Vite source maps in the raw ext4 image were scanned independently and
  extracted with `forensics/extract_vite_sourcemaps.py`. The 120 recovered
  `sourcesContent` files are archived under `forensics/raw-vite-sourcemaps/`
  with the original image offsets and parse log. The current `Home.vue` is
  byte-identical to the latest recovered disk copy.
- The task history page was restored from original May source plus the June/July
  rollout patches. It now includes the original expandable report card: task
  duration, score, metadata, diagnostics summary, and `/jobs/{id}/logs` tail.
  The recommended-chain diagnostics contract remains on `History.vue`; the
  original `Jobs.vue` removed that panel in the May session and instead contains
  the final running/queued/completed/failed/background tabs.
- `MediaDetailPanel.vue` now uses the original genre filter that removes code,
  studio, series, and actor duplicate tags. Preview playback also prefers the
  Emby `stream_url` from the detail payload and falls back to the local
  hardlink preview endpoint when streaming fails.

## Plugin SDK Recovery (2026-08-23)

- `frontend/src/views/PluginHost.vue` now exposes `sdk.avatar.resolve` and
  `sdk.avatar.candidates` again, based on the final rollout evidence.
  The original final session used the old `sdkPost` helper; this recovery uses the
  same host's `pluginFetch('/actions/...')` so Gfriends avatar candidates remain
  available to actor editing without relying on the retired helper.

- Restored plugin development/CLI artifacts from the original rollout:
  `plugins/README.md`, `PLUGIN_DESIGN.md`, `PLUGIN_DEVELOPMENT.md`,
  `PLUGIN_SDK.md`, `PLUGIN_CLI.md`, `mteam-plugin/MTEAM_API.md`,
  `tools/noor_plugin/{validate,create,pack}.py`, and `scripts/noor-plugin`.
  `scripts/noor-plugin create demo-plugin --type rss_source` and
  `scripts/noor-plugin pack plugins/local-subtitle-library --force` both pass,
  and `scripts/noor-plugin validate plugins` exits 0 with only non-fatal warnings.
- Restored Docker-oriented docs from the June evidence:
  `README.md`, `DOCKER.md`, and `docs/DEV_DOCKER_ALIGNMENT.md`. These document the
  deployment direction without changing backend or Docker runtime source, matching
  the user's instruction to keep Docker work out of this recovery step.
- Corrected the recovered M-Team page to the final original toast helper:
  `sdk.toast?.[type] || sdk.toast?.info || sdk.toast?.success` is used instead of the
  older `alert(msg)` fallback, which also resolves the plugin validator false positive.

- Ran a top-level symbol audit across 27 modules that have both preserved `.pyc`
  and current `.py` sources. Only legacy custom-pipeline and inline Xunlei subtitle
  helpers are missing (`CustomPipelineConfig`, `_assert_custom_pipeline_supported`,
  `parse_custom_config`, `module_installed`, `_search_xunlei`); those belong to
  intentionally retired Whisper and subtitle-search chains and are documented as
  `intentional` in the recovery audit.

- Static API-reference audit found no route gaps: all 96 frontend/plugin references
  resolve against static routes or the dynamic plugin action route. The recovered
  backend starts successfully on a test port; health, settings, plugins, and jobs
  endpoints return 200, and OpenAPI exposes 150 paths. Component function-entry
  comparison also found no missing behavior after accounting for intentional moves
  such as downloader dialog helpers and local subtitle settings.

## HardlinkView Original Action Recovery (2026-08-24)

- `HardlinkView.vue` now matches the 2026-08-23 original read evidence again:
  it checks only the `mdc-ng-manual` plugin, calls `/plugins/mdc-ng-manual/test`,
  and submits source reorg through `/plugins/mdc-ng-manual/actions/create`.
  The recovery-time generic `hardlink_source_actions` loader was removed.
- `/files/hardlinks?q=` route query handling was removed because the original
  final HardlinkView snapshot does not contain it.
- Kept the confirmed final fix that removes the duplicated
  `summary.total_groups` value in the summary card.

## Media Library Legacy Compatibility (2026-08-23)

- `backend/app/api/endpoints/media_library.py` now re-exports the pre-split public
  actor-management function names and request models, including actor profile,
  duplicate detection, mapping matches/status, TMDB/name-sync progress, batch merge,
  and media-item chain deletion. Older plugin or test imports that referenced the
  original single-module `media_library` API continue to resolve without circular
  import failures.
- `backend/app/api/endpoints/actors.py` restores the four legacy mapping routes:
  `POST /actors/mapping/upload`, `GET /actors/mapping/latest-upload`,
  `POST /actors/mapping/import-latest`, and `POST /actors/mapping/sync-online`.
  `sync-online` intentionally delegates to the current MDC-NG mapping sync so the
  old route remains compatible without re-introducing the retired online workflow.
- `backend/tests/test_actor_routes.py` now asserts the full original 43-route media
  library contract again. The backend suite still passes with 216 tests.
- Final JavDB and recommendation-plugin snapshots were re-checked against the
  current plugin pages. JavDB retains every function entry from the archived
  `served`/`coherent` snapshots plus the later routed actor/series work; the
  recommendation plugin only drops `openJavDB`, which was intentionally replaced
  by the later inline work-detail panel.

## Recovery Consistency (2026-08-23)

- Backend `compileall` is clean and the full test suite currently passes: 216 passed.
- An isolated runtime smoke was run against the recovered tree on temporary ports:
  backend health/settings/plugins/jobs endpoints returned 200 and OpenAPI exposed
  150 paths; CDP browser smoke rendered the main app, plugins list, M-Team, hardlinks,
  actors, jobs, history, recommendation, JavDB, and Gfriends pages with no runtime
  exceptions. The two 400 responses on `/plugins/gfriends` are expected because the
  plugin is disabled in this recovery worktree and its host actions return
  `plugin disabled`.
- The recovered media-library recovery endpoints now have stable OpenAPI
  `operation_id` values, and the final replayed `Jobs.vue` is archived and
  verified byte-for-byte in `forensics/recovered-sources/`.
- Frontend production build passes with `npm run build`.
- The task manager is restored to the full queue contract: persisted queued-job
  recovery, phase/SSE state, queued and running cancellation, dependent activation
  and skipping, orphaned `running` cleanup, GPU Guard, log persistence, LADA,
  FaceFusion, and isolated Whisper/translation worker processes with graceful cancel
  followed by forced termination. Regression coverage was added in
  `backend/tests/test_job_manager_recovery.py`.
- `backend/tests/test_media_library_api.py` was restored as a test module for NFO/CDATA
  parsing, local-NFO item detail, media-library 503/502 error handling, and hardlink
  scan/response contracts.
- Final FaceFusion runtime directory, Python path, and full parameter defaults were
  restored into `core/config.py`; `facefusion_defaults.py` remains as the compatibility
  layer for the separate overrides file.
- Whisper settings now expose a storage-root contract (`model_root_dir`,
  `runtime_root_dir`, `database_url`, `database_path`) without retired Reazon fields.
- `forensics/version-gap-audit.md` reports no missing indexed paths and no remaining
  `pending` paths: all 130 indexed paths are marked verified against the preserved
  rollout evidence, bytecode contracts, or focused regression tests. Runtime and
  derived data remain outside the commit.
- Runtime cleanup, data/runtime path helpers, database migration, LADA Python paths,
  GPU Guard, Whisper timing refinement, local subtitle-library indexing, and directory
  browsing were checked against the original rollout. The restored local subtitle index
  now lives under `runtime/subtitle_library` and migrates the strongest legacy
  `subtitle_index.db`; settings-directory browsing accepts all final model/runtime
  roots instead of only two legacy paths.
- Job/events API contract tests now cover task listing/detail/cancel/delete/cleanup and
  the SSE connected/done sequence, including the original job-type allowlist for
  `POST /api/jobs`. GPU Guard regression tests cover NOOR process protection and
  restricting cleanup to NOOR plus model-server processes.
- LADA runner, settings helpers, settings status helpers, and core job models were
  checked against the final rollout: LADA now uses the NOOR Python environment,
  split cache/TMPDIR layout, and `--temporary-directory`; settings helpers use the
  data-dir model fallback and final ChickenRice model catalogue; `JobCreate` keeps
  the `job_type` API field.
- Whisper Japanese post-processing and safety post-processing now match the final
  rollout names and merge semantics. LADA settings inspection, database startup
  migration, plugin store paths, and embedded FaceFusion source patches are also
  covered by regression tests and marked verified.
- The final rollout paths for jobs, plugin background tasks, runtime cleanup,
  hardlink runtime storage, FaceFusion model routing, recommendation/subscription
  cover refresh, JavDB magnet refresh and recent-series directory, qBittorrent
  API-key auth, and plugin runtime cache/data routing were replayed and verified.
  `forensics/version-gap-audit.md` now reports 130 verified and 0 pending indexed
  paths; only the documented intentional differences remain.
- JavDB plugin manifest now matches the original capability contract, including
  `dashboard_widget`; the overview page again renders the `JAVDB 推荐` widget and
  the recommendation center reports the merged candidate-pool stats (currently
  `1548+273`).
- `media_library.py` now re-exports every helper name present in the preserved
  `media_library.pyc` (listing, deletion, hardlink, stream, and detail helpers),
  so split-module recovery does not break older plugin imports.

## Session Diff Archive and Whisper Contract Recovery (2026-08-23)

- Added `forensics/extract_session_diffs.py` and archived 477 unique unified-diff
  sections from the original June/August rollout under
  `forensics/recovered-sources/session-diffs/` with a SHA256 manifest. The script
  also runs `git apply --reverse --check`; 63 diffs already apply reversibly to the
  current tree, 376 require equivalence review, and 38 were truncated by the editor
  when originally printed and are retained only as evidence.
- Restored the original Whisper translator line-retry behavior in
  `backend/app/pipeline/whisper/runtime.py`: batch results are normalized to the
  batch length, suspected untranslated lines are repaired one by one, and a failed
  batch is retried per line before falling back to source text.
- Added `backend/tests/test_whisper_translator.py` covering full
  `/v1/chat` and `/v1/chat/completions` endpoint preservation, Ollama detection,
  request shape, and refusal handling. Extended `backend/tests/test_whisper_runtime.py`
  with untranslated-line detection, failed-batch recovery, and successful-batch
  repair tests.
- Restored the original `facefusion_restore` phase defaults/terminal labels and the
  exported `legacy_hardlink_groups_path_impl()` compatibility helper, with regression
  coverage in `backend/tests/test_job_phases.py` and
  `backend/tests/test_media_library_hardlinks.py`.

- Restored the final JavDB actor panel from the June session-diff sequence: actor
  routing keeps the actors tab active on refresh, actor pages render a dedicated
  avatar/bio panel with quick filters, capsule year/sort badges, and genre chips,
  and both relation-panel and actor-list avatars consult `sdk.avatar.resolve` with
  a per-name cache before falling back to the provided URL or initial.
  The final `javdb-actor-select-badge` styles and dark native option styling were
  also restored from the archived session diffs.
- Full verification currently passes: 223 backend tests, frontend production build,
  and plugin validation.

## 2026-08-24 FilesView Original Structure Recovery

- `FilesView.vue` restored the visible `文件` page title and mobile heading/tab
  stacking from the original early evidence. `/files` still canonicalizes to
  `/files/hardlinks`, and the 演员管理 tab remains under the same Files page.
- Added `backend/tests/test_files_view_contract.py` to lock the Files tabs,
  `/files/:fileTab?` route, `/hardlinks` redirect, and sidebar `文件` entry.
- HardlinkView was re-checked against all three 2026-08-23 read snapshots;
  the only difference from the preserved segments is the intentional duplicate
  `summary.total_groups` deletion.
- Full backend pytest: `266 passed, 6 skipped`; frontend production build passes;
  restored-page smoke covers `/files` and still reports no HTTP/console errors.

## Read Snapshot Audit and Whisper Contract Lock (2026-08-24)

- Added `forensics/audit_read_snapshots.py` to reproduce the snapshot comparison
  against the active `/home/kinax/noor` tree. The 2026-08-23 final window is
  79/79 exact within drift; actor, actor-management, and actor-detail snapshots
  are also exact within drift.
- The full-history scan reports 676 exact, 6 review, 138 drift, and 5 missing.
  Those rows are classified in `forensics/read-snapshot-audit-classification.md`
  as older revisions, final module splits, or intentionally retired Whisper
  multi-chain files.
- Added `backend/tests/test_subtitle_panel_runtime_contract.py` so the final
  Whisper runtime-tier payload cannot be removed as apparent recovery drift.
- Verification: frontend production build passes; backend full pytest passes
  with `269 passed, 6 skipped`.


The isolated recovery repository history records each reconstruction step. Generated
`__pycache__` files are intentionally ignored; the original recovered `.pyc` artifacts
outside cache directories remain versioned as forensic evidence.

- Restored original plugin icon assets: MDC-NG `frontend/icons/{service,sidebar}.svg` and AV graph `frontend/icons/service.svg`; all plugin manifest icons and frontend entries now resolve through the backend with HTTP 200.
- Restored `frontend/public/img/body-background.png` from the pre-takeover backup. The production build no longer reports the unresolved `/img/body-background.png` warning.
- Removed `data/av_recommend/candidate_pool.json` and `data/subscription_core/subscriptions.json` from the Git index while keeping the files on disk. `.gitignore` now covers both runtime directories.
- Restored original frontend TypeScript strictness: `tsconfig.json` now matches the pre-takeover configuration, `tsconfig.node.json` was restored, and six unused/dead frontend declarations were removed. `vue-tsc` and the production build both pass.
- Restored the original Tailwind theme token map and the `/whisper` Vite proxy. Custom classes such as `text-accent-cyan` and `bg-bg-elevated` are generated again in the production CSS; the frontend build passes.
- Restored missing original config/docs from the pre-takeover backup: `backend/requirements.txt`, `backend/run.py`, `frontend/nginx.conf`, and the frontend design/consistency documents. The backend entry imports and all declared runtime modules resolve in the current NOOR environment.
