# CONCLAVE GUI

A browser-based interface for CONCLAVE Phase 1 and Phase 2: upload a CSV, pick markers,
configure and run the pipeline, review clusters and annotate them in-browser, then run Phase 2
consensus/projection and browse the results.

This is not part of the `conclave` pip package. It is a separate, optional local tool that lives
in the same GitHub repo, in its own `gui/` folder. Installing `conclave` via pip is unaffected by
this folder.

## Architecture

- **Backend** (`backend/`): FastAPI, wraps the `conclave` package directly (installed from GitHub
  in the Docker image). Runs Phase 1/Phase 2 jobs in a background worker thread, one job at a
  time, with live progress from the pipeline's own logging/print output.
- **Frontend** (`frontend/`): React + TypeScript (Vite). Talks to the backend via `/api/...`.
- **Docker**: two containers (`backend`, `frontend`). The frontend container serves the built
  static app via nginx, which also proxies `/api/*` to the backend container.

## Running it

**Two backend variants exist.** Most people should use the default one:

- **`backend/Dockerfile`** (default) — fast to build (a minute or two), does not include R. All
  10 native Python clustering methods work; `flowsom`/`depeche` will fail with a clear error if
  selected.
- **`backend/Dockerfile.with-r`** (optional) — includes R and compiles FlowSOM/DepecheR from
  Bioconductor. Only build this if you specifically need those two methods — it commonly takes
  20-40+ minutes and produces a much larger image. See [FlowSOM / DepecheR](#flowsom--depecher)
  below.

The instructions below default to the fast variant. Both variants use different image tags
(`conclave-backend` vs `conclave-backend-r`) so you can build either, or both, without one
overwriting the other.

### With Docker (recommended)

```bash
cd gui
docker compose up --build
```

Then open **http://localhost:8080**.

If your Docker installation doesn't have Compose, build and run the containers manually:

```bash
docker build -t conclave-backend ./backend
docker build -t conclave-frontend ./frontend

docker network create conclave-net
docker volume create conclave_gui_data

docker run -d --name backend --network conclave-net \
  -v conclave_gui_data:/data -p 8000:8000 conclave-backend

docker run -d --name frontend --network conclave-net \
  -p 8080:80 conclave-frontend
```

Uploaded data and job outputs persist in the `conclave_gui_data` volume across container
restarts.

### Rebuilding after a `conclave` code update

`backend/requirements.txt` installs `conclave` from an unpinned `git+https://...` URL. Since that
file's content never changes, a plain `docker build` reuses Docker's cached layer and silently
keeps whatever `conclave` version was first built — it does **not** re-fetch the latest code.
After pulling any update to the `conclave` package, rebuild the backend with a cache-busting
build argument:

```bash
docker build --build-arg CACHEBUST=$(date +%s) -t conclave-backend ./backend
```

or force a full rebuild of everything:

```bash
docker build --no-cache -t conclave-backend ./backend
```

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

The default backend image (`conclave-backend`, built from `backend/Dockerfile`) does not include
R — it uses a `python:3.11-slim` base to keep builds fast, and is what most people should use.
`flowsom`/`depeche` will fail with a clear per-method error if selected (the rest of your
clustering methods still complete normally — see "Partial failures" in the main README).

To use `flowsom`/`depeche`, build the separate R-enabled image instead. This uses its own image
tag (`conclave-backend-r`) so it never overwrites your fast default build — both can exist on
your machine at once, and you choose which one to actually run.

```bash
docker build --build-arg CACHEBUST=$(date +%s) -f backend/Dockerfile.with-r -t conclave-backend-r ./backend
```

This installs R and compiles FlowSOM/DepecheR from Bioconductor, which is considerably slower
(commonly 20-40+ minutes) and produces a larger image (several GB more) than the default build.
It has not been built or tested against a real Docker daemon or the actual CRAN/Bioconductor
package servers in the environment this was written in — it follows standard Bioconductor
installation practice, but hasn't been confirmed to actually build successfully yet. If it fails,
the `docker build` output will show which system library or R package failed to compile; that's
the place to start debugging, and `Dockerfile.with-r`'s comments explain what each dependency is
for.

To run it, use the same commands as the default backend, substituting the image name:

```bash
docker stop backend && docker rm backend
docker run -d --name backend --network conclave-net \
  -v conclave_gui_data:/data -p 8000:8000 conclave-backend-r
```

In the Phase 1 config screen, select `flowsom`/`depeche` and leave the script path blank to use
the R scripts bundled with the `conclave` package.

## Features

### Force restart and custom output directories

Phase 1's config screen has a **Force restart** checkbox (on by default) and an optional
**output directory** field. Leave the directory blank for an auto-generated location, or set a
fixed path and turn Force restart off to resume an existing run — for example, go back, add a
clustering method, and re-run: already-completed methods are skipped and only the new one runs.
After a successful run, the output directory field is filled in with the actual path used and
Force restart turns off automatically, so going back and re-running resumes rather than starting
over.

Phase 2's config screen has the same output-directory field, plus a field to point at a
different Phase 1 output directory — any Phase 1 output, including runs from the CLI, a
notebook, or an earlier GUI session, not only the run from the previous step.

### Back navigation

Every step has a Back button, and form values are preserved when navigating backward.

### Annotation: in-browser or upload

Per method, choose between annotating in the browser or uploading a CSV annotated separately
(offline, or by someone else). Uploaded files are validated before saving: `cluster_id` and
`annotation` columns must be present, and the `cluster_id`s must exactly match that method's
clusters from Phase 1.

## Known limitations

- **One job at a time.** The backend runs jobs one at a time rather than in parallel, to keep
  progress-log capture from different jobs from mixing together.
- **No authentication.** Meant for local or trusted use, not public internet exposure. Endpoints
  guard against path traversal in file/job-id parameters, but there is no login, no per-user
  data isolation, and no rate limiting.
- **Polling, not WebSockets.** The progress view polls every ~1.5 seconds rather than pushing
  updates.
- **Phase 2 always processes the full uploaded file**, regardless of Phase 1's sample size —
  Phase 2 projects consensus labels onto every cell. Expect several minutes for large files.
- **The job registry is in-memory only.** If the backend process restarts, `GET
  /api/phase1/jobs` and the review-step endpoints (heatmap/clusters/annotations) can no longer
  resolve custom output directories for jobs from before the restart. Phase 2's direct-path
  override works around this for starting Phase 2 against an existing Phase 1 run, but there is
  no equivalent yet for resuming a Phase 1 review session after a restart.
