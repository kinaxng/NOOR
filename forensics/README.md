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
