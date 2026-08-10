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
