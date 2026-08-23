# Recovered Raw Git Pack Provenance

Checked on 2026-08-24.

The packs under `forensics/extracted-packs-work/` were recovered from raw disk
evidence. Indexing and decoding their commit objects shows they do **not**
contain the original NOOR repository:

- `pack-1112539136.pack` contains `ngx_brotli` history.
- `pack-1885736960.pack` contains OpenClaw / memory-lancedb skill history.
- `pack-3741577216.pack` contains another skill profile history.
- `pack-3919892480.pack` contains unrelated personal-profile workflow history.

Commit subjects are dominated by ngx_brotli development, Claude/OpenClaw skill
installation documentation, memory-lancedb setup, and personal GitHub Actions
workflow updates. None match the NOOR commit hashes or subjects recorded in
`forensics/original-commit-index.json`.

This does not affect the recovered source tree. Current source remains a mix of
byte-level cache/source-map evidence, rollout replay, preserved bytecode
contracts, and verified reconstruction, as recorded in `recovery-gap-audit.md`.
