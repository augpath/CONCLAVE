# CONCLAVE GUI

A browser-based interface for CONCLAVE Phase 1 and Phase 2: upload a CSV, pick markers,
configure and run the pipeline, review clusters and annotate them in-browser, then run Phase 2
consensus/projection and browse the results.

**This is not part of the `conclave` pip package.** It's a separate, optional local tool that
happens to live in the same GitHub repo, in its own `gui/` folder. Installing `conclave` via pip
is completely unaffected by this folder's existence.

## Architecture

- **Backend** (`backend/`): FastAPI, wraps the real `conclave` package directly (installed from
  GitHub in the Docker image). Runs Phase 1/Phase 2 jobs in a background worker thread, one job
  at a time (deliberate for v1 — see "Design notes" below), with live progress captured from the
  pipeline's own logging/print output.
- **Frontend** (`frontend/`): React + TypeScript (Vite). Talks to the backend via `/api/...`.
- **Docker**: two containers (`backend`, `frontend`) via `docker-compose.yml`. The frontend
  container serves the built static app via nginx, which also proxies `/api/*` to the backend
  container.

## Running it

### With Docker (recommended)

```bash
cd gui
docker compose up --build
```

Then open **http://localhost:8080**.

Uploaded data and job outputs persist in a named Docker volume (`conclave_gui_data`), so they
survive container restarts. To wipe everything: `docker compose down -v`.

### Without Docker (development)

```bash
# Backend
cd gui/backend
pip install -r requirements.txt
CONCLAVE_GUI_DATA=./data uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd gui/frontend
npm install
VITE_API_PROXY_TARGET=http://localhost:8000 npm run dev
```

Then open the URL Vite prints (usually http://localhost:5173).

## FlowSOM / DepecheR

The backend Docker image does **not** include R — it's a `python:3.11-slim` base to keep builds
fast. If you want to use `flowsom`/`depeche` as clustering methods:

1. Install R + the FlowSOM/DepecheR Bioconductor packages inside the backend container (or
   extend `backend/Dockerfile` with your own R install step)
2. In the GUI's Phase 1 config, select `flowsom`/`depeche` and either leave the script path blank
   (uses the R scripts bundled with the `conclave` package) or point at your own

## Design notes / known limitations (v1)

- **One job at a time.** The backend runs a single background worker thread, not a real job
  queue. This was a deliberate simplification for a fast v1, and also sidesteps a real technical
  issue: Python's `sys.stdout`/`sys.stderr` are process-global, so redirecting them to capture
  live progress (which both Phase 1's logger and Phase 2's `print()` calls need) would
  cross-contaminate logs between concurrent jobs if more than one ran at once.
- **No authentication.** This is meant for local/trusted use, not public internet exposure.
  Endpoints do guard against path traversal in file/job-id parameters, but there's no login,
  no per-user data isolation, and no rate limiting.
- **Polling, not WebSockets.** The progress view polls `/api/jobs/{id}` every ~1.5s. Simpler to
  get right for v1; a websocket-based push model would reduce latency/overhead but isn't
  necessary at this scale.
- **Phase 2 always processes your full uploaded file**, regardless of Phase 1's sample size —
  that's inherent to what Phase 2 does (projects consensus labels onto every cell), not a GUI
  limitation. Expect several minutes for large files.

## What's been tested, and what hasn't

Every backend endpoint was tested against a **running server with real melanoma spatial
proteomics data** (not synthetic/mocked): upload → Phase 1 job (with live progress polling) →
cluster review → saving annotations → Phase 2 job → plot listing → image serving → CSV download.
Path traversal attempts were also tested and correctly blocked.

The frontend TypeScript compiles with zero errors, the production build succeeds, and the dev
proxy was verified to correctly forward real requests (including a real file upload) from the
frontend dev server through to the backend.

**Not tested**: actual browser rendering/interaction (clicking through the UI). The sandbox this
was built in can't download a browser binary (network-restricted), so there's no automated or
manual confirmation that, e.g., the annotation table renders correctly or the multi-step
navigation behaves as expected when actually clicked through. Also not tested: `docker compose
up` itself (Docker isn't runnable in this sandbox) — the Dockerfiles and compose config follow
standard patterns and each piece (Python deps, npm build, nginx serving/proxying) was verified
independently, but the full containerized boot has not been confirmed end-to-end.

**If you hit issues after `docker compose up`, they're most likely in one of these two
unverified areas — let me know what breaks and I'll fix it.**
