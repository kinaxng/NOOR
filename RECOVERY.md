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

## Known Missing Areas

- Application entrypoint and router assembly.
- Job manager, system API, media-library hardlink helpers, and audio enhancer.
- Plugin framework, FaceFusion integration, recommendation/subscription plugins, and
  the Vue frontend source.

The next reconstruction phase should rebuild only these missing modules from session
history and verified API behavior, while keeping the recovered `.pyc` modules unchanged.

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
- Remaining startup blockers are the plugin framework and plugin sources, global
  search, knowledge graph modules, and the Vue frontend. They were not present in the
  recovered disk sectors and must be reconstructed from session records.

The isolated recovery repository has commits `616866a` and `7150e12`. Generated
`__pycache__` files are intentionally ignored; the original recovered `.pyc` artifacts
outside cache directories remain versioned as forensic evidence.
