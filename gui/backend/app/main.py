"""CONCLAVE GUI backend.

A thin FastAPI wrapper around the real conclave package. Not part of the
pip-installable conclave package itself -- this is a separate, optional
local tool (see gui/README.md).
"""
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .jobs import job_manager
from .phase1_runner import run_phase1_job
from .phase2_runner import run_phase2_job

DATA_DIR = Path(os.environ.get("CONCLAVE_GUI_DATA", "/data"))
UPLOADS_DIR = DATA_DIR / "uploads"
PHASE1_DIR = DATA_DIR / "phase1"
PHASE2_DIR = DATA_DIR / "phase2"
for d in (UPLOADS_DIR, PHASE1_DIR, PHASE2_DIR):
    d.mkdir(parents=True, exist_ok=True)

SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _safe_component(name: str) -> str:
    """Guard against path traversal in user-controlled path segments
    (method names, plot filenames, job ids)."""
    if not name or not SAFE_NAME_RE.match(name) or ".." in name:
        raise HTTPException(400, f"Invalid path component: {name!r}")
    return name


def _resolve_outdir(custom_outdir: Optional[str], default_dir: Path, job_id: str) -> Path:
    """A custom path is used as-is (advanced use: point at a directory you
    also use from the CLI/notebooks, or want to find easily on disk).
    Otherwise falls back to the GUI's own UUID-per-job convention."""
    if custom_outdir:
        return Path(custom_outdir)
    return default_dir / job_id


def _warn_if_outside_data_dir(job, outdir: Path) -> None:
    """If running via Docker, only DATA_DIR (mounted as a named volume) is
    visible on the host and survives container removal -- a custom outdir
    outside it is written successfully from the backend's point of view,
    but invisible from outside the container and lost on `docker rm`. This
    puts a clear warning directly in the job's own live log, since that's
    what the GUI's progress view actually shows."""
    try:
        outdir.resolve().relative_to(DATA_DIR.resolve())
    except ValueError:
        job.logs.append(
            f"WARNING: output directory '{outdir}' is not under {DATA_DIR}. "
            f"If running via Docker, only {DATA_DIR} (the mounted volume) is "
            f"visible on your host machine and survives 'docker rm' -- files "
            f"written outside it will appear to vanish. Use a path under "
            f"{DATA_DIR} (e.g. {DATA_DIR}/my_run), or leave this field blank "
            f"for an auto-generated location under {DATA_DIR}."
        )


def _job_summary(job) -> dict:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "label": job.label,
        "outdir": job.outdir,
        "created_at": job.created_at,
        "result": job.result,
    }


app = FastAPI(title="CONCLAVE GUI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Upload
# ============================================================
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    import shutil

    upload_id = str(uuid.uuid4())
    dest = UPLOADS_DIR / f"{upload_id}.csv"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    preview = pd.read_csv(dest, nrows=5)
    with open(dest) as f:
        n_rows = sum(1 for _ in f) - 1

    return {
        "upload_id": upload_id,
        "columns": preview.columns.tolist(),
        "n_rows": n_rows,
        "preview": preview.to_dict(orient="records"),
    }


# ============================================================
# Jobs (generic status endpoint, works for both phases)
# ============================================================
@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.get(_safe_component(job_id))
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "logs": job.logs[-1000:],
        "error": job.error,
        "result": job.result,
        "outdir": job.outdir,
    }


@app.get("/api/phase1/jobs")
async def list_phase1_jobs():
    """List known Phase 1 jobs (most recent first) -- lets the frontend
    offer 'use a previous run' when configuring Phase 2, including runs
    from earlier in the same session that the user has since navigated
    away from with the back button."""
    return {"jobs": [_job_summary(j) for j in job_manager.list(kind="phase1")]}


# ============================================================
# Phase 1
# ============================================================
class Phase1Request(BaseModel):
    upload_id: str
    markers: List[str]
    sample_cols: List[str] = []
    normalization: Optional[str] = "z-score"
    sampling: str = "stratified-notproportional"
    sample_size: int = 20000
    n_tiles_per_axis: int = 4
    dr_method: Optional[str] = None
    dr_n_components: int = 15
    cluster_methods: List[str] = ["phenograph", "kmeans"]
    phenograph_k: int = 25
    derive_kmeans_from: Optional[str] = "phenograph"
    flowsom_rscript: Optional[str] = None
    depeche_rscript: Optional[str] = None
    seed: int = 42
    outdir: Optional[str] = None  # advanced: custom output path instead of the auto-generated one
    force_restart: bool = True    # False resumes from any existing checkpoints in outdir
    label: Optional[str] = None   # optional friendly name for job pickers


@app.post("/api/phase1/jobs")
async def start_phase1(payload: Phase1Request):
    csv_path = UPLOADS_DIR / f"{_safe_component(payload.upload_id)}.csv"
    if not csv_path.exists():
        raise HTTPException(404, "Upload not found")
    if not payload.markers:
        raise HTTPException(400, "No markers selected")

    job = job_manager.create("phase1")
    job.label = payload.label
    outdir = _resolve_outdir(payload.outdir, PHASE1_DIR, job.id)
    job.outdir = str(outdir)
    _warn_if_outside_data_dir(job, outdir)

    job_manager.start(
        job,
        run_phase1_job,
        csv_path=str(csv_path),
        outdir=str(outdir),
        markers=payload.markers,
        sample_cols=payload.sample_cols,
        normalization=payload.normalization,
        sampling=payload.sampling,
        sample_size=payload.sample_size,
        n_tiles_per_axis=payload.n_tiles_per_axis,
        dr_method=payload.dr_method,
        dr_n_components=payload.dr_n_components,
        cluster_methods=payload.cluster_methods,
        phenograph_k=payload.phenograph_k,
        derive_kmeans_from=payload.derive_kmeans_from,
        flowsom_rscript=payload.flowsom_rscript,
        depeche_rscript=payload.depeche_rscript,
        seed=payload.seed,
        force_restart=payload.force_restart,
    )
    return {"job_id": job.id, "outdir": str(outdir)}


def _phase1_outdir_for_job(job_id: str) -> Path:
    job = job_manager.get(job_id)
    if job and job.outdir:
        return Path(job.outdir)
    # Fall back to the default convention, e.g. for jobs from before this
    # field existed
    return PHASE1_DIR / job_id


@app.get("/api/phase1/jobs/{job_id}/clusters")
async def get_phase1_clusters(job_id: str):
    job_id = _safe_component(job_id)
    outdir = _phase1_outdir_for_job(job_id)
    heatmap_dir = outdir / "04_cluster_heatmaps"
    if not heatmap_dir.exists():
        raise HTTPException(404, "No results yet for this job")

    methods = sorted(
        p.stem.replace("annotation_template_", "")
        for p in heatmap_dir.glob("annotation_template_*.csv")
    )
    clusters: Dict[str, list] = {}
    for m in methods:
        df = pd.read_csv(heatmap_dir / f"annotation_template_{m}.csv")
        df["annotation"] = df["annotation"].fillna("")
        clusters[m] = df.to_dict(orient="records")

    # Report which methods already have saved annotations (either saved
    # in-browser or uploaded as a pre-annotated CSV) -- both naming
    # conventions, matching what the core package itself now recognizes
    ann_dir = outdir / "annotations"
    annotated = set()
    if ann_dir.exists():
        for p in ann_dir.glob("*_annotated.csv"):
            annotated.add(p.stem.replace("_annotated", ""))
        for p in ann_dir.glob("annotation_template_*.csv"):
            try:
                df = pd.read_csv(p)
                if "annotation" in df.columns and df["annotation"].notna().any():
                    annotated.add(p.stem.replace("annotation_template_", ""))
            except Exception:
                pass

    return {
        "methods": methods,
        "clusters": clusters,
        "annotated_methods": sorted(annotated),
        "outdir": str(outdir),
    }


@app.get("/api/phase1/jobs/{job_id}/heatmap/{method}")
async def get_heatmap_image(job_id: str, method: str):
    job_id, method = _safe_component(job_id), _safe_component(method)
    outdir = _phase1_outdir_for_job(job_id)
    path = outdir / "04_cluster_heatmaps" / f"heatmap_topN_ranked_{method}.png"
    if not path.exists():
        raise HTTPException(404, "Heatmap not found")
    return FileResponse(path, media_type="image/png")


class AnnotationUpdate(BaseModel):
    method: str
    annotations: Dict[str, str]  # cluster_id (as string) -> annotation text


@app.post("/api/phase1/jobs/{job_id}/annotations")
async def save_annotations(job_id: str, payload: AnnotationUpdate):
    job_id = _safe_component(job_id)
    method = _safe_component(payload.method)
    outdir = _phase1_outdir_for_job(job_id)
    template_path = outdir / "04_cluster_heatmaps" / f"annotation_template_{method}.csv"
    if not template_path.exists():
        raise HTTPException(404, "No cluster template found for this method")

    df = pd.read_csv(template_path)
    df["cluster_id_str"] = df["cluster_id"].astype(str)
    df["annotation"] = df["cluster_id_str"].map(payload.annotations).fillna(df.get("annotation", ""))
    df = df.drop(columns=["cluster_id_str"])

    ann_dir = outdir / "annotations"
    ann_dir.mkdir(exist_ok=True)
    df.to_csv(ann_dir / f"{method}_annotated.csv", index=False)

    n_annotated = int((df["annotation"].astype(str).str.strip() != "").sum())
    return {"status": "saved", "n_clusters": len(df), "n_annotated": n_annotated}


@app.post("/api/phase1/jobs/{job_id}/annotations/upload")
async def upload_annotations(
    job_id: str,
    method: str = Form(...),
    file: UploadFile = File(...),
):
    """Alternative to in-browser annotation: upload a CSV you already
    annotated separately (e.g. offline, or by someone else). Must have
    'cluster_id' and 'annotation' columns, and the cluster_ids must match
    this method's actual clusters from Phase 1 -- checked before saving,
    so a mismatched file is rejected with a clear reason rather than
    silently accepted."""
    job_id = _safe_component(job_id)
    method = _safe_component(method)
    outdir = _phase1_outdir_for_job(job_id)
    template_path = outdir / "04_cluster_heatmaps" / f"annotation_template_{method}.csv"
    if not template_path.exists():
        raise HTTPException(404, "No cluster template found for this method")

    try:
        uploaded = pd.read_csv(file.file)
    except Exception as e:
        raise HTTPException(400, f"Could not read CSV: {e}")

    if "cluster_id" not in uploaded.columns:
        raise HTTPException(400, "Uploaded CSV must have a 'cluster_id' column")
    if "annotation" not in uploaded.columns:
        raise HTTPException(400, "Uploaded CSV must have an 'annotation' column")

    expected = pd.read_csv(template_path)
    expected_ids = set(expected["cluster_id"].astype(str))
    uploaded_ids = set(uploaded["cluster_id"].astype(str))

    missing = expected_ids - uploaded_ids
    extra = uploaded_ids - expected_ids
    if missing:
        raise HTTPException(
            400,
            f"Uploaded file is missing cluster_id(s) {sorted(missing)} that exist in "
            f"this method's Phase 1 output.",
        )
    if extra:
        raise HTTPException(
            400,
            f"Uploaded file has cluster_id(s) {sorted(extra)} that don't exist in "
            f"this method's Phase 1 output (typo, or annotated against a different run?).",
        )

    n_blank = uploaded["annotation"].isna().sum() + (
        uploaded["annotation"].astype(str).str.strip() == ""
    ).sum()

    ann_dir = outdir / "annotations"
    ann_dir.mkdir(exist_ok=True)
    save_cols = ["cluster_id", "n_cells", "annotation"] if "n_cells" in uploaded.columns else ["cluster_id", "annotation"]
    uploaded[save_cols].to_csv(ann_dir / f"{method}_annotated.csv", index=False)

    n_annotated = len(uploaded) - n_blank
    return {"status": "saved", "n_clusters": len(uploaded), "n_annotated": int(n_annotated)}


# ============================================================
# Phase 2
# ============================================================
class Phase2Request(BaseModel):
    phase1_job_id: Optional[str] = None   # use a job tracked by this GUI instance
    phase1_outdir: Optional[str] = None   # OR point directly at any Phase 1 output directory
                                           # (e.g. from the CLI/notebooks, or a different machine's mount)
    methods: List[str]
    knn_k: int = 25
    min_votes: int = 2
    sample_cols: List[str] = []
    template_max_per_label: int = 500
    outdir: Optional[str] = None  # advanced: custom output path instead of the auto-generated one
    label: Optional[str] = None


@app.post("/api/phase2/jobs")
async def start_phase2(payload: Phase2Request):
    if not payload.phase1_job_id and not payload.phase1_outdir:
        raise HTTPException(400, "Provide either phase1_job_id or phase1_outdir")

    if payload.phase1_outdir:
        phase1_outdir = Path(payload.phase1_outdir)
    else:
        phase1_outdir = _phase1_outdir_for_job(_safe_component(payload.phase1_job_id))

    if not phase1_outdir.exists():
        raise HTTPException(404, f"Phase 1 output directory not found: {phase1_outdir}")
    if not payload.methods:
        raise HTTPException(400, "No methods selected")

    job = job_manager.create("phase2")
    job.label = payload.label
    outdir = _resolve_outdir(payload.outdir, PHASE2_DIR, job.id)
    job.outdir = str(outdir)
    _warn_if_outside_data_dir(job, outdir)

    job_manager.start(
        job,
        run_phase2_job,
        phase1_outdir=str(phase1_outdir),
        outdir=str(outdir),
        methods=payload.methods,
        knn_k=payload.knn_k,
        min_votes=payload.min_votes,
        sample_cols=payload.sample_cols,
        template_max_per_label=payload.template_max_per_label,
    )
    return {"job_id": job.id, "outdir": str(outdir)}


def _phase2_outdir_for_job(job_id: str) -> Path:
    job = job_manager.get(job_id)
    if job and job.outdir:
        return Path(job.outdir)
    return PHASE2_DIR / job_id


@app.get("/api/phase2/jobs/{job_id}/plots")
async def list_phase2_plots(job_id: str):
    job_id = _safe_component(job_id)
    plots_dir = _phase2_outdir_for_job(job_id) / "plots"
    if not plots_dir.exists():
        raise HTTPException(404, "No plots yet for this job")
    return {"plots": sorted(p.name for p in plots_dir.glob("*.png"))}


@app.get("/api/phase2/jobs/{job_id}/plot/{name}")
async def get_phase2_plot(job_id: str, name: str):
    job_id, name = _safe_component(job_id), _safe_component(name)
    path = _phase2_outdir_for_job(job_id) / "plots" / name
    if not path.exists():
        raise HTTPException(404, "Plot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/phase2/jobs/{job_id}/download")
async def download_phase2_csv(job_id: str):
    job_id = _safe_component(job_id)
    path = _phase2_outdir_for_job(job_id) / "full_dataset_labeled_complete.csv"
    if not path.exists():
        raise HTTPException(404, "Result file not found")
    return FileResponse(path, filename="full_dataset_labeled_complete.csv")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
