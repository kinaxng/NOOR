# NOOR Active Workspace

This is the active NOOR application source. Recovery evidence, forensics, and
audits live in `/home/kinax/noor-restored`.

## Search Boundaries

- Do not recursively search `/home/kinax`, `/`, `/home/kinax/Videos`, or
  `/home/kinax/Music`. Several directories under the home tree are NFS mounts
  and can stall or overwhelm the host.
- Prefer scoped searches with `rg` or `rg --files` inside `backend`,
  `frontend`, `plugins`, and `scripts`.
- Never search network mounts recursively.

## Runtime

- Active backend: `127.0.0.1:9899`
- Active frontend: `http://192.168.31.3:5173/` or `127.0.0.1:5173`
- Backend tests:

```bash
cd /home/kinax/noor
PYTHONPATH=backend /home/kinax/.venvs/noor-backend/bin/python -m pytest -q backend/tests
```

- Frontend build:

```bash
cd /home/kinax/noor/frontend && npm run build
```

## Workflow

- Keep runtime files under `data/` ignored and out of git.
- Commit source changes in scoped commits.
- Update `HANDOFF.md` and
  `/home/kinax/noor-restored/forensics/recovery-gap-audit.md` when recovery
  status changes.
