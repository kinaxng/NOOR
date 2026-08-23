# NOOR Restored Workspace

This is the isolated NOOR recovery tree. Work here, not in `/home/kinax/noor`.

## Search Boundaries

- Do not recursively search `/home/kinax`, `/`, `/home/kinax/Videos`, or
  `/home/kinax/Music`. Several directories under the home tree are NFS mounts
  and can stall or overwhelm the host.
- Prefer scoped searches with `rg` or `rg --files` inside `backend`,
  `frontend`, `plugins`, `forensics`, and `scripts`.
- Never search network mounts recursively.

## Runtime

- Recovered backend: `127.0.0.1:9899`
- Recovered frontend: `http://192.168.31.3:5173/` or `127.0.0.1:5173`
- Backend tests:

```bash
cd /home/kinax/noor-restored
PYTHONPATH=backend:. /home/kinax/.venvs/noor-backend/bin/python -m pytest -q
```

- Frontend build:

```bash
cd /home/kinax/noor-restored/frontend && npm run build
```

## Workflow

- Keep runtime files under `data/` ignored and out of git.
- Commit source changes in scoped commits.
- Update `HANDOFF.md` and `forensics/recovery-gap-audit.md` when recovery
  status changes.
