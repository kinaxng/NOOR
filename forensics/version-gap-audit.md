# NOOR 文件级恢复差距清单

更新时间：2026-08-23

本清单由 `forensics/version_gap_audit.py` 从 `forensics/original-commit-index.json` 生成。
它用于追踪原版历史中改过的路径在恢复树里的状态，不能替代行为/路由/字节级验证。

## 状态说明

- `verified`：已按原版会话/运行契约核对。
- `pending`：文件存在，但尚未完成最终原版逐版本核对。
- `missing`：原版历史中出现，但当前恢复树没有对应路径。
- `intentional`：按用户后续要求或恢复策略有意不复原/改为不同实现。

## 清单

| 路径 | 原版提交数 | 状态 | 原版最后提交 | 当前最后提交 |
| --- | ---: | --- | --- | --- |
| `backend/tests/test_media_library_api.py` | 31 | pending | 7c44237 Import TMDB actor aliases and clean overview links | b29c8d6 Restore media library legacy helper compatibility |
| `backend/app/tasks/manager.py` | 7 | pending | 0184022 Add Whisper runtime tier selection | dd3422d Restore GPU guard and FaceFusion reference worker |
| `backend/app/core/runtime_paths.py` | 4 | pending | 72d45aa Share default data dir constant | 616866a Preserve recovered NOOR backend artifacts |
| `backend/app/api/local_library.py` | 3 | pending | 2ecda9d Migrate legacy subtitle indexes | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_directories.py` | 3 | pending | 41153cc Simplify AI storage path settings | 6b5139e Recover settings directory helpers |
| `backend/app/pipeline/facefusion/preview.py` | 3 | pending | 6a71cd1 Skip FaceFusion content blur in previews | 616866a Preserve recovered NOOR backend artifacts |
| `backend/app/pipeline/lada/runner.py` | 3 | pending | 106df4b Prefer bundled LADA python path | eef5d36 Recover LADA task runner |
| `plugins/av-recommend/frontend/page.js` | 3 | pending | 8ecd4a3 Add fallback image loading for recommendation cards | 2129a70 Restore recommendation cover fallback chain |
| `plugins/qbittorrent/backend.py` | 3 | pending | c0dc3b8 Keep qBittorrent password auth compatible | 01af6da Restore downloader connection tests |
| `plugins/xunlei-remote/frontend/style.css` | 3 | pending | 7d9120d Simplify Xunlei residual cleanup flow | 5ced5cf Recover Xunlei remote management frontend |
| `backend/app` | 2 | pending | 14a3cc3 Add experimental Whisper timing refiner | b29c8d6 Restore media library legacy helper compatibility |
| `backend/app/api/endpoints/media_library_item_detail.py` | 2 | pending | c3b736f Separate uncensored media tagging from cracked titles | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_helpers.py` | 2 | pending | 106df4b Prefer bundled LADA python path | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/app/api/settings_status_helpers.py` | 2 | pending | a382063 Add FaceFusion model management settings tab | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_whisper.py` | 2 | pending | 0184022 Add Whisper runtime tier selection | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_whisper_models.py` | 2 | pending | ed23bfe Fix Whisper HuggingFace cache detection | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_whisper_runtime.py` | 2 | pending | a2195c3 Ignore empty Whisper cache dirs | 558869c Restore settings contract and media library API tests |
| `backend/app/api/whisper.py` | 2 | pending | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/app/core/facefusion_paths.py` | 2 | pending | 91c8a29 Show configured FaceFusion model directory | 24f438b Restore configured FaceFusion model routing |
| `backend/app/core/gpu_guard.py` | 2 | pending | 6a760cc Let GPU guard stop model server processes | dd3422d Restore GPU guard and FaceFusion reference worker |
| `backend/app/core/lada_paths.py` | 2 | pending | 65d39f1 Align Docker runtime paths | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/core/models.py` | 2 | pending | c3b736f Separate uncensored media tagging from cracked titles | 53ea009 Recover core data models from bytecode |
| `backend/app/main.py` | 2 | pending | 43acc3a Add NOOR runtime cleanup task | 8296a65 Restore local subtitle library settings |
| `backend/app/pipeline/facefusion/preview_worker.py` | 2 | pending | 6a71cd1 Skip FaceFusion content blur in previews | 616866a Preserve recovered NOOR backend artifacts |
| `backend/app/pipeline/whisper/timing_refiner.py` | 2 | pending | 442c3af Avoid duration-only subtitle splits | 52ccdef Restore Whisper long subtitle timing refinement |
| `backend/app/pipeline/whisper/types.py` | 2 | pending | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/app/tasks/job_phases.py` | 2 | pending | 20f4ce8 Remove remaining Whisper legacy UI remnants | 7a9f55e Restore external plugin task integration |
| `backend/app/tasks/manager_helpers.py` | 2 | pending | 9716085 Store task runtime files under data dir | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests` | 2 | pending | 14a3cc3 Add experimental Whisper timing refiner | f858014 Lock actor route compatibility with API tests |
| `backend/tests/test_lada_paths.py` | 2 | pending | 65d39f1 Align Docker runtime paths | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_lada_runner_cancel.py` | 2 | pending | e436cc0 Split LADA runtime cache directories | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_runtime_cleanup.py` | 2 | pending | 1a02e32 Add NOOR runtime cleanup task | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_settings_updates.py` | 2 | pending | d9f5a73 Derive AI storage defaults from data dir | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_settings_whisper_runtime.py` | 2 | pending | a2195c3 Ignore empty Whisper cache dirs | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_whisper_strategy.py` | 2 | pending | 0184022 Add Whisper runtime tier selection | 25718e0 Recover ChickenRice Whisper primary chain |
| `backend/tests/test_whisper_timing_refiner.py` | 2 | pending | 442c3af Avoid duration-only subtitle splits | 52ccdef Restore Whisper long subtitle timing refinement |
| `frontend/src` | 2 | pending | 14a3cc3 Add experimental Whisper timing refiner | d8f7414 Restore final AI storage settings and verify settings panels |
| `plugins/av-recommend/backend.py` | 2 | pending | 8ecd4a3 Add fallback image loading for recommendation cards | 2129a70 Restore recommendation cover fallback chain |
| `plugins/av-recommend/frontend/style.css` | 2 | pending | 6ab498a Refine recommendation detail panel layout | 2129a70 Restore recommendation cover fallback chain |
| `plugins/gfriends/backend.py` | 2 | pending | e1697fa Prefer Japanese actor names for Gfriends lookup | 9f74125 Recover core runtime and embedded FaceFusion |
| `plugins/qbittorrent/frontend/page.js` | 2 | pending | fd44ab3 Support qBittorrent API key auth | 4c0e9c1 Recover qBittorrent management frontend |
| `plugins/subscription-core/backend.py` | 2 | pending | 8ecd4a3 Add fallback image loading for recommendation cards | 587ea15 Restore subscription cover persistence |
| `backend/app/api/endpoints/media_library_hardlinks.py` | 1 | pending | ddbf4c0 Move hardlink groups into runtime data | 558869c Restore settings contract and media library API tests |
| `backend/app/api/jobs.py` | 1 | pending | 806de25 Add FaceFusion crack processing integration | 7a9f55e Restore external plugin task integration |
| `backend/app/api/plugins.py` | 1 | pending | 43acc3a Add NOOR runtime cleanup task | f47907b Restore plugin runtime, resource search, and plugin manager |
| `backend/app/api/runtime_cleanup.py` | 1 | pending | 43acc3a Add NOOR runtime cleanup task | 7b84f07 Recover NOOR runtime cleanup background task |
| `backend/app/api/settings_lada.py` | 1 | pending | 106df4b Prefer bundled LADA python path | 03fa0b9 Recover LADA settings inspection |
| `backend/app/core/database.py` | 1 | pending | 2ceba68 Move default database into data dir | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/core/database_paths.py` | 1 | pending | 2ceba68 Move default database into data dir | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/core/runtime_cleanup.py` | 1 | pending | 43acc3a Add NOOR runtime cleanup task | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/pipeline/facefusion` | 1 | pending | 806de25 Add FaceFusion crack processing integration | b3dd5ac Restore FaceFusion upstream revision tracking |
| `backend/app/pipeline/facefusion/reference_faces_worker.py` | 1 | pending | 39c918e Add FaceFusion reference face gallery | dd3422d Restore GPU guard and FaceFusion reference worker |
| `backend/app/pipeline/facefusion/source` | 1 | pending | 217a5e8 Embed FaceFusion runtime in NOOR | b3dd5ac Restore FaceFusion upstream revision tracking |
| `backend/app/pipeline/facefusion/source/NOOR_UPSTREAM.json` | 1 | pending | 0f6ed10 Track FaceFusion upstream revision | b3dd5ac Restore FaceFusion upstream revision tracking |
| `backend/app/pipeline/facefusion/source/facefusion/content_analyser.py` | 1 | pending | 6c51a5c Skip FaceFusion content analysis for NOOR jobs | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/pipeline/facefusion/source/facefusion/download.py` | 1 | pending | 5779f51 Wait for FaceFusion model downloads before validation | 7f4828b Restore FaceFusion model management |
| `backend/app/pipeline/facefusion/source/facefusion/execution.py` | 1 | pending | 70f5263 Keep FaceFusion runtime data outside source | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/app/pipeline/whisper/__init__.py` | 1 | pending | 20f4ce8 Remove remaining Whisper legacy UI remnants | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/app/pipeline/whisper/japanese_post.py` | 1 | pending | 20f4ce8 Remove remaining Whisper legacy UI remnants | 1df5030 Recover Whisper Japanese postprocessing |
| `backend/app/plugins/store.py` | 1 | pending | d5826f0 Route plugin data through runtime storage | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_database_paths.py` | 1 | pending | 2ceba68 Move default database into data dir | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_facefusion_embedded_source.py` | 1 | pending | 70f5263 Keep FaceFusion runtime data outside source | 24f438b Restore configured FaceFusion model routing |
| `backend/tests/test_media_library_hardlinks.py` | 1 | pending | ddbf4c0 Move hardlink groups into runtime data | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_plugin_store_paths.py` | 1 | pending | d5826f0 Route plugin data through runtime storage | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_settings_api.py` | 1 | pending | 106df4b Prefer bundled LADA python path | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_settings_status_helpers.py` | 1 | pending | 9716085 Store task runtime files under data dir | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_settings_whisper_models.py` | 1 | pending | 7f76e42 Restrict Whisper model deletion to configured storage | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_task_runtime_paths.py` | 1 | pending | 9716085 Store task runtime files under data dir | 9f74125 Recover core runtime and embedded FaceFusion |
| `backend/tests/test_whisper_engine_cache.py` | 1 | pending | f176af3 Cover Whisper HuggingFace root layout | 9f68a60 Recover final Whisper single-chain architecture |
| `plugins/avdb/backend.py` | 1 | pending | d5826f0 Route plugin data through runtime storage | 219325a Restore configurable AVDB provider |
| `plugins/javdb/backend.py` | 1 | pending | 2225f1e feat(javdb): add recent series directory | 7c1e884 Restore JavDB recent series directory |
| `plugins/javdb/frontend/page.js` | 1 | pending | 2225f1e feat(javdb): add recent series directory | 7c1e884 Restore JavDB recent series directory |
| `plugins/javdb/frontend/style.css` | 1 | pending | 2225f1e feat(javdb): add recent series directory | 7c1e884 Restore JavDB recent series directory |
| `plugins/mteam-plugin/backend.py` | 1 | pending | d5826f0 Route plugin data through runtime storage | cd825be Recover complete M-Team integration |
| `backend/app/api/endpoints/media_library.py` | 43 | intentional | 2decd18 Exclude ignored ghost actors from merge candidates | b29c8d6 Restore media library legacy helper compatibility |
| `backend/app/pipeline/whisper/decoupled/qwen3.py` | 2 | intentional | c96ca5d Share Whisper cache path candidates | - |
| `backend/app/pipeline/whisper/preprocess.py` | 2 | intentional | ebb5c7e Apply Whisper preprocessing runtime paths | - |
| `backend/app/pipeline/whisper/decoupled/anime_qwen3_chain.py` | 1 | intentional | 17602ad Organize AI runtime storage paths | - |
| `backend/app/pipeline/whisper/enhancer.py` | 1 | intentional | 0458364 Tighten AI runtime path tests | - |
| `backend/tests/test_whisper_preprocess.py` | 1 | intentional | ebb5c7e Apply Whisper preprocessing runtime paths | - |
| `frontend/src/i18n/zh.ts` | 39 | verified | b2aa1f6 Refine FaceFusion media badge behavior | fc04ada Restore missing Whisper connection error copy and recovery audit |
| `frontend/src/i18n/en.ts` | 37 | verified | b2aa1f6 Refine FaceFusion media badge behavior | a26b01a Restore missing English dashboard welcome copy |
| `frontend/src/views/ActorManagementView.vue` | 28 | verified | 9c49a79 Use MDC-NG actor mapping source | 2a7fe62 Restore exact historical actor workspace sources |
| `frontend/src/components/noor/FaceFusionPanel.vue` | 25 | verified | 301d3d8 feat(facefusion): expose face tracker score | 86c250d Restore FaceFusion tracker score |
| `backend/app/api/settings_response.py` | 21 | verified | 301d3d8 feat(facefusion): expose face tracker score | 558869c Restore settings contract and media library API tests |
| `frontend/src/views/settings/FaceFusionSettings.vue` | 19 | verified | 301d3d8 feat(facefusion): expose face tracker score | a994e55 Restore FaceFusion media badge setting |
| `backend/app/api/settings.py` | 18 | verified | 301d3d8 feat(facefusion): expose face tracker score | 558869c Restore settings contract and media library API tests |
| `backend/app/core/config.py` | 17 | verified | 301d3d8 feat(facefusion): expose face tracker score | 558869c Restore settings contract and media library API tests |
| `frontend/src/components/noor/LadaPanel.vue` | 17 | verified | 77c8bb2 Split FaceFusion into dedicated panel | 0ab46ad Recover original LADA panel |
| `backend/app/pipeline/facefusion/runner.py` | 16 | verified | 301d3d8 feat(facefusion): expose face tracker score | 24f438b Restore configured FaceFusion model routing |
| `frontend/src/api/types.ts` | 13 | verified | 301d3d8 feat(facefusion): expose face tracker score | 86c250d Restore FaceFusion tracker score |
| `backend/app/api/settings_updates.py` | 11 | verified | 301d3d8 feat(facefusion): expose face tracker score | 558869c Restore settings contract and media library API tests |
| `backend/app/api/facefusion.py` | 9 | verified | 301d3d8 feat(facefusion): expose face tracker score | 24f438b Restore configured FaceFusion model routing |
| `frontend/src/views/ActorDetailView.vue` | 8 | verified | 3bf46cc Allow removing actor provider IDs | 2a7fe62 Restore exact historical actor workspace sources |
| `backend/tests/test_core_config_storage_defaults.py` | 7 | verified | ebb5c7e Apply Whisper preprocessing runtime paths | 9f68a60 Recover final Whisper single-chain architecture |
| `frontend/src/views/settings/SystemSettings.vue` | 7 | verified | 2aa83bb Derive MDC-NG actor mapping file from root path | a0beb88 Avoid blocking system settings on Emby libraries |
| `backend/app/pipeline/whisper/orchestrator.py` | 6 | verified | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/tests/test_facefusion_runner.py` | 6 | verified | b2cb29b Clean FaceFusion task runtime resources | 24f438b Restore configured FaceFusion model routing |
| `backend/app/api/endpoints/media_library_helpers.py` | 5 | verified | c3b736f Separate uncensored media tagging from cracked titles | 558869c Restore settings contract and media library API tests |
| `backend/app/api/settings_facefusion_upgrade.py` | 5 | verified | a668dcc Preserve FaceFusion content patches on upgrade | b3dd5ac Restore FaceFusion upstream revision tracking |
| `frontend/src/views/settings/StorageSettings.vue` | 5 | verified | 41153cc Simplify AI storage path settings | d8f7414 Restore final AI storage settings and verify settings panels |
| `backend/app/pipeline/whisper/engine.py` | 4 | verified | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/tests/test_settings_response.py` | 4 | verified | 217a5e8 Embed FaceFusion runtime in NOOR | 558869c Restore settings contract and media library API tests |
| `frontend/src/components/noor/MediaCard.vue` | 4 | verified | 4dd6c51 Aggregate FaceFusion variant badge state | 84bb8a7 Recover original media card and tabs |
| `frontend/src/views/Home.vue` | 4 | verified | b2aa1f6 Refine FaceFusion media badge behavior | 3e4cdc0 Recover original media library view |
| `plugins/xunlei-remote/backend.py` | 4 | verified | 1feffc1 Change Xunlei residual handling to search and delete | ef1f76c Recover Xunlei download path management |
| `plugins/xunlei-remote/frontend/page.js` | 4 | verified | 7d9120d Simplify Xunlei residual cleanup flow | 5ced5cf Recover Xunlei remote management frontend |
| `backend/app/pipeline/whisper/strategy.py` | 3 | verified | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `backend/tests/test_env_backed_library_configs.py` | 3 | verified | 2ecda9d Migrate legacy subtitle indexes | 558869c Restore settings contract and media library API tests |
| `backend/tests/test_facefusion_upgrade.py` | 3 | verified | 0f6ed10 Track FaceFusion upstream revision | 0ab32de Verify FaceFusion upgrade content patch |
| `frontend/src/components/noor/SubtitlePanel.vue` | 3 | verified | 0184022 Add Whisper runtime tier selection | ad7302e Recover plugin-based subtitle providers |
| `frontend/src/components/noor/panels/PanelHeader.vue` | 2 | verified | 9f62658 Refine actor detail navigation and actions | 0165575 Recover original FaceFusion panel |
| `frontend/src/composables/useWhisper.ts` | 2 | verified | 0184022 Add Whisper runtime tier selection | 9f68a60 Recover final Whisper single-chain architecture |
| `frontend/src/composables/useWhisperProfiles.ts` | 2 | verified | 0184022 Add Whisper runtime tier selection | b0a6622 Recover subtitle workflow dependencies |
| `frontend/src/views/FilesView.vue` | 2 | verified | 527f96d Add media actor management tab | 2a7fe62 Restore exact historical actor workspace sources |
| `frontend/src/views/settings/LadaSettings.vue` | 2 | verified | 7219ca2 Split FaceFusion settings into dedicated tab | 6ff12d0 Recover original routed application shell |
| `frontend/src/views/settings/WhisperSettings.vue` | 2 | verified | 0184022 Add Whisper runtime tier selection | 6ff12d0 Recover original routed application shell |
| `backend/app/pipeline/whisper/runtime_tier.py` | 1 | verified | 0184022 Add Whisper runtime tier selection | 25718e0 Recover ChickenRice Whisper primary chain |
| `backend/tests/test_gfriends_plugin.py` | 1 | verified | e1697fa Prefer Japanese actor names for Gfriends lookup | 9f74125 Recover core runtime and embedded FaceFusion |
| `frontend/src/App.vue` | 1 | verified | 4f1b075 Move hardlinks under files section | e297426 Restore actor detail navigation identity |
| `frontend/src/components/noor/AppSidebar.vue` | 1 | verified | 4f1b075 Move hardlinks under files section | d8b8188 Recover frontend application shell components |
| `frontend/src/components/noor/BaseIcon.vue` | 1 | verified | 9f62658 Refine actor detail navigation and actions | 82d5e7a Recover frontend modal and button primitives |
| `frontend/src/components/noor/panels/FilePathSelector.vue` | 1 | verified | a7d7d19 Allow file path selector to wrap long paths | 0165575 Recover original FaceFusion panel |
| `frontend/src/components/ui/Tabs.vue` | 1 | verified | 1220755 Keep active tabs visible on mobile | 84bb8a7 Recover original media card and tabs |
| `frontend/src/composables/useJobPresentation.ts` | 1 | verified | 806de25 Add FaceFusion crack processing integration | ee05cd1 Recover original frontend dashboard |
| `frontend/src/router/index.ts` | 1 | verified | 4f1b075 Move hardlinks under files section | 2c31f4a Restore JavDB sidebar workspace |
| `frontend/src/style.css` | 1 | verified | c2b5111 Show database path in storage settings | 6ff12d0 Recover original routed application shell |
| `frontend/src/views/PluginHost.vue` | 1 | verified | 194662f Make Gfriends an avatar library helper | 8e11c67 Restore plugin pill select controls |
| `frontend/src/views/settings/SettingsIndex.vue` | 1 | verified | 7219ca2 Split FaceFusion settings into dedicated tab | 8296a65 Restore local subtitle library settings |
| `plugins/av-recommend` | 1 | verified | 6a80f72 Fix recommendation plugin icon assets | c734bb5 Restore recommendation center icons |
| `plugins/gfriends/frontend/page.js` | 1 | verified | 194662f Make Gfriends an avatar library helper | 364fb38 Restore complete Gfriends plugin assets |
| `plugins/gfriends/frontend/style.css` | 1 | verified | 194662f Make Gfriends an avatar library helper | 364fb38 Restore complete Gfriends plugin assets |
| `plugins/gfriends/plugin.json` | 1 | verified | 194662f Make Gfriends an avatar library helper | 364fb38 Restore complete Gfriends plugin assets |
| `plugins/qbittorrent/plugin.json` | 1 | verified | fd44ab3 Support qBittorrent API key auth | 81940de Restore original plugin service icons |
| `plugins/subscription-core/frontend/page.js` | 1 | verified | 8ecd4a3 Add fallback image loading for recommendation cards | 587ea15 Restore subscription cover persistence |
| `plugins/xunlei-remote/plugin.json` | 1 | verified | 15f6ac8 Add Xunlei residual task restore | 81940de Restore original plugin service icons |
