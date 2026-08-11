# NOOR Source Recovery

This tree is an isolated recovery workspace. It does not replace `/home/kinax/noor`.

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
or the Vue frontend. The original Vue sources and router cannot be recovered from disk.

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
- Rebuilt the plugin runtime and recovered functional first-party plugin sources for
  JavDB, recommendations, subscriptions, Gfriends, qBittorrent, Transmission,
  Xunlei Remote, M-Team, and AVDB.
- Rebuilt global resource search, browser History API routes, and the Vue recovery UI.
- The full original component tree and several historical advanced interaction surfaces
  remain unavailable as source artifacts; they must continue to be recreated from
  verified behavior rather than treated as byte-for-byte recovery.

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
  Emby JSON-content-type guidance, and the recent audit log.
- The surviving actor APIs support Emby actor browsing, mapped multilingual names,
  duplicate detection, movie lookup, and explicitly selected GFriends avatar writes.
  The list filters invalid Emby people before paginating, supports mapped-name search,
  and browser actor detail routes load independently of the complete actor scan.
  Actor merge, actor deletion, and arbitrary metadata writes have not been recreated
  because the original Emby mutation contracts could not be verified.
- FaceFusion source-image management and frame-preview controls are restored. Opening a
  media detail reads only preview metadata; a preview is generated only after a source
  image is selected and the frame slider is released.

The isolated recovery repository history records each reconstruction step. Generated
`__pycache__` files are intentionally ignored; the original recovered `.pyc` artifacts
outside cache directories remain versioned as forensic evidence.
