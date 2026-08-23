# NOOR Project Handoff

Last updated: 2026-06-10 Asia/Shanghai

## Recovery Note (2026-08-23)

- The original `/home/kinax/noor` source tree was deleted. The isolated recovery
  workspace is `/home/kinax/noor-restored`; do not treat the current
  `/home/kinax/noor` directory as the source of truth.
- The recovered frontend runs at `http://192.168.31.3:5173/` and the recovered
  backend currently listens on `127.0.0.1:9899`.
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

## Hard Rules

- Recovery workspace: `/home/kinax/noor-restored`
- Frontend dev server: Vite on `5173`
- Recovered backend dev server: FastAPI/Uvicorn on `9899`
- Do **not** touch Docker backend on `19898`.
- Do **not** recursively search `/home/kinax`, `$HOME`, `/`, `/home/kinax/Videos`, or `/home/kinax/Music`.
- NFS mounts under home:
  - `/home/kinax/Videos`
  - `/home/kinax/Music`
- Safe code search pattern:
  ```bash
  cd /home/kinax/noor-restored
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
old=$(pgrep -f '^/home/kinax/.venvs/noor-backend/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 9899' || true)
[ -n "$old" ] && kill $old && sleep 1
cd /home/kinax/noor-restored/backend
nohup /home/kinax/.venvs/noor-backend/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 9899 --forwarded-allow-ips='*' > /tmp/noor-backend-9899.log 2>&1 &
sleep 2
curl -s http://127.0.0.1:9899/api/health
```

Frontend usually runs on `5173`; check before restarting:

```bash
ps -eo pid,ppid,etime,stat,comm,args | grep -E 'vite|npm run dev|pnpm run dev' | grep -v grep
```

## Git / Workspace Notes

- The repository has many historical modified/untracked files.
- Do not assume `git status` noise is from the current task.
- `plugins/av-recommend/` is currently untracked but functional; decide whether to formally add it.
- Plugin cache files under `data/plugin_cache/` create large git status noise. Consider `.gitignore` cleanup.
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
- candidates: 122
- recommendations: 42
- first item example had score breakdown and reasons.

### AV Recommend Next Steps

Recommended next implementation order:

1. Formally add/track `plugins/av-recommend/` and ignore cache noise.
   - `.gitignore` now ignores generated `data/plugin_cache/`, `data/av_recommend/`, and `data/subscription_core/`.
   - Existing tracked cache files still need a non-destructive index cleanup such as `git rm -r --cached data/plugin_cache`.
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
   - unify resource quality schema across AVDB/M-Team/JavDB
   - score new-model uncensored/cracked/subtitle/size/source more consistently
5. Add recommendation settings:
   - candidate sources on/off
   - exploration ratio
   - subtitle/cracked preference strength
   - minimum confidence threshold
6. Add performance controls:
   - cache recommendations per profile/config/feedback
   - limit concurrent JavDB/detail/resource calls
   - avoid plugin calls when dashboard card hidden/unmounted

## Known Pitfalls

- Do not revert large UI/history changes casually; many files have accumulated work.
- Gfriends avatar-provider work is in progress but functional:
  - new plugin directory: `plugins/gfriends/`
  - plugin id: `gfriends`, display name: `Gfriends`
  - manifest type is `knowledge_app` because the current manifest tests do not accept `tool`
  - backend builds an alias index from `https://github.com/gfriends/gfriends` `Filetree.json`
  - default asset URLs use jsDelivr `https://cdn.jsdelivr.net/gh/xinxin8816/gfriends/Content/`
  - file names that include cache query strings such as `?t=1607433807` must preserve the query; `_content_url()` now encodes only path segments
  - plugin actions: `sync`, `stats`, `resolve`
  - cached avatar route uses `/api/plugins/gfriends/images/{image_id}`
  - `PluginHost.vue` exposes `sdk.avatar.resolve({ name, aliases })`, currently wired to `/plugins/gfriends/actions/resolve`
  - `plugins/javdb/frontend/page.js` uses `sdk.avatar.resolve()` for actor directory/ranking cards and actor detail header, falling back to JavDB avatars or initial-letter placeholders
  - current main app has no broader actor-avatar surface beyond plugins; future non-plugin pages need their own call site or a shared frontend avatar helper
- Do not reintroduce Nuxt UI full rewrite; project is currently Vite-based.
- Do not use direct JavDB API credentials/token approach; current chosen path is DBOnline API.
- Do not make AVDB a full standalone page again unless explicitly requested; it is currently best treated as a resource provider.
- Do not make MDC-NG a full page; it is mainly a capability button/task provider.
- Do not let plugins poll in background merely because they are installed; route/widget visibility should control data loading.
- When testing search/recommend/resource features, expect dependent plugin/API slowness. Use timeouts and avoid open-ended loops.

## Good First Commands in a Fresh Context

```bash
cd /home/kinax/noor-restored
cat HANDOFF.md
cat AGENTS.md
git status --short | sed -n '1,120p'
ps -eo pid,ppid,etime,stat,comm,args | grep -E 'uvicorn app.main:app|vite|npm run dev|pnpm run dev' | grep -v grep
curl -s http://127.0.0.1:9899/api/health
```

## Latest Gfriends Validation

```bash
python3 -m py_compile plugins/gfriends/backend.py
node --check plugins/javdb/frontend/page.js
cd frontend && npm run build
/home/kinax/.venvs/noor-backend/bin/python -m pytest -q backend/tests/test_builtin_plugin_manifests.py
```

Notes:

- Gfriends direct resolve for `波多野結衣` returns a correct URL ending in `AI-Fix-波多野結衣.jpg?t=1607433807`.
- Frontend build passed after adding `sdk.avatar.resolve()` and JavDB avatar override.
- Manifest test still has 4 unrelated pre-existing failures:
  - `subscription-core` manifest type `tool`
  - `widget-system` frontend missing `type: module`
  - `av-recommend` mount cleanup missing
  - `av-recommend` unscoped CSS classes `is-disabled`, `is-loading`, `is-primary`
