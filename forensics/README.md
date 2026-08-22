# Recovery Evidence

This directory preserves source-recovery evidence separately from the working
application. The `decompiled/` files were produced from disk-recovered Python
bytecode and have not been substituted for a running module until each module
has passed import and endpoint verification.

`backend-files-from-core.txt` is the original recovered-file inventory. It is
kept so later restoration work can distinguish code recovered from storage from
code reconstructed from session records.

The active application remains under `backend/`; do not delete this evidence
while the recovery is in progress.

## Frontend Snapshots

`frontend-snapshots/` preserves NOOR frontend artifacts that were still present
in `/tmp` on August 22, 2026. They were copied byte-for-byte before further
recovery work because `/tmp` is not durable storage.

- `core/App.recovered-full.vue` is a complete 6,122-line Vue SFC. It builds
  successfully with the recovered frontend toolchain, but represents an older
  monolithic NOOR UI and must not replace the newer componentized frontend
  without a feature-by-feature comparison.
- `core/App.recovered-old.vue`, `core/ActorManagement.initial.vue`, and
  `core/SettingsSwitch.vue` preserve earlier source snapshots.
- `core/PluginHost.vite-module.js` is a Vite-transformed module response, not
  original Vue source. It remains useful for verifying recovered behavior.
- `plugins/` contains source or served-module snapshots for the AV Graph,
  recommendation, JavDB, qBittorrent, Xunlei Remote, and MDC-NG manual pages.
- `frontend-snapshots/SHA256SUMS` records the exact copied bytes.

These snapshots are evidence and comparison inputs. Active implementations
remain under `frontend/src/` and `plugins/*/frontend/`.
