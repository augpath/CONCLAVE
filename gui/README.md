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

### Force restart and custom output directories

Phase 1's config step has a **Force restart** checkbox (default on) and an optional **output
directory** field. Leave the directory blank and each run gets its own auto-generated location;
set a fixed path and turn Force restart off to resume an existing run — e.g. go back, add a
clustering method, and re-run: already-completed methods are skipped, only the new one runs.
After a successful run, the output directory field auto-fills with the actual path used and
Force restart flips off by default, so "go back → tweak → re-run" naturally resumes rather than
starting over.

Phase 2's config step has the same output-directory field, plus a **"use a different Phase 1
output directory"** field that accepts *any* Phase 1 output — from the CLI, a notebook, or a
GUI session that's no longer tracked in memory (see the next point) — not just the run from the
previous step.

### Back navigation and job-registry persistence

Every step has a **Back** button, and all form values are preserved when navigating backward —
implemented by lifting config state up to `App.tsx` rather than storing it locally in each step
component. One real limitation this surfaces: **the job registry is in-memory only**. If the
backend process restarts, `GET /api/phase1/jobs` and the review-step endpoints
(heatmap/clusters/annotations) can no longer resolve custom output directories for jobs from
before the restart, since they look up the directory via the in-memory `Job.outdir` field. The
Phase 2 config step's direct-path override (above) is the workaround for this specific case;
there's currently no equivalent for resuming a Phase 1 *review* session after a backend restart
without knowing the exact directory the review endpoints expect.

### Annotation: in-browser or upload

The annotation step lets you choose, per method, between annotating in the browser (as before)
or uploading a CSV you already annotated separately (offline, or by someone else). Uploaded
files are validated before saving — `cluster_id`/`annotation` columns must be present, and the
`cluster_id`s must exactly match that method's real clusters from Phase 1 (rejected with a
specific missing/extra list otherwise, not silently accepted).

## What's been tested, and what hasn't

Every backend endpoint was tested against a **running server with real melanoma spatial
proteomics data** (not synthetic/mocked): upload → Phase 1 job (with live progress polling) →
cluster review → saving annotations → Phase 2 job → plot listing → image serving → CSV download.
Path traversal attempts were also tested and correctly blocked.

The force-restart/custom-output-directory, back-navigation, and annotation-upload features
added later were also tested against real data end-to-end, including: custom output directories
actually landing files at the specified path; resuming from a fresh backend process (no
in-memory job history) using only the on-disk checkpoint state; the Phase 2 direct-path override
resolving a Phase 1 run with zero job tracking; the annotation-upload endpoint's validation
correctly rejecting a missing-column file and a mismatched-cluster_id file; and a full run mixing
annotation sources (two methods annotated via the API, one via upload) flowing correctly into a
completed Phase 2 result. The frontend TypeScript compiles clean and the production build
succeeds; request/response shapes were checked field-by-field against the backend's Pydantic
models. As before, actual browser interaction (clicking through the UI) is not something this
sandbox can verify — that still needs your own click-through.
