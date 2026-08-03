"""CONCLAVE GUI backend.

A thin FastAPI wrapper around the real conclave package. Not part of the
pip-installable conclave package itself -- this is a separate, optional
local tool (see gui/README.md).
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
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
    import uuid

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
    }


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


@app.post("/api/phase1/jobs")
async def start_phase1(payload: Phase1Request):
    csv_path = UPLOADS_DIR / f"{_safe_component(payload.upload_id)}.csv"
    if not csv_path.exists():
        raise HTTPException(404, "Upload not found")
    if not payload.markers:
        raise HTTPException(400, "No markers selected")

    job = job_manager.create("phase1")
    outdir = PHASE1_DIR / job.id
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
    )
    return {"job_id": job.id}


@app.get("/api/phase1/jobs/{job_id}/clusters")
async def get_phase1_clusters(job_id: str):
    job_id = _safe_component(job_id)
    heatmap_dir = PHASE1_DIR / job_id / "04_cluster_heatmaps"
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

    # Report which methods already have saved annotations
    ann_dir = PHASE1_DIR / job_id / "annotations"
    annotated = sorted(
        p.stem.replace("_annotated", "") for p in ann_dir.glob("*_annotated.csv")
    ) if ann_dir.exists() else []

    return {"methods": methods, "clusters": clusters, "annotated_methods": annotated}


@app.get("/api/phase1/jobs/{job_id}/heatmap/{method}")
async def get_heatmap_image(job_id: str, method: str):
    job_id, method = _safe_component(job_id), _safe_component(method)
    path = PHASE1_DIR / job_id / "04_cluster_heatmaps" / f"heatmap_topN_ranked_{method}.png"
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
    template_path = PHASE1_DIR / job_id / "04_cluster_heatmaps" / f"annotation_template_{method}.csv"
    if not template_path.exists():
        raise HTTPException(404, "No cluster template found for this method")

    df = pd.read_csv(template_path)
    df["cluster_id_str"] = df["cluster_id"].astype(str)
    df["annotation"] = df["cluster_id_str"].map(payload.annotations).fillna(df.get("annotation", ""))
    df = df.drop(columns=["cluster_id_str"])

    ann_dir = PHASE1_DIR / job_id / "annotations"
    ann_dir.mkdir(exist_ok=True)
    df.to_csv(ann_dir / f"{method}_annotated.csv", index=False)

    n_annotated = int((df["annotation"].astype(str).str.strip() != "").sum())
    return {"status": "saved", "n_clusters": len(df), "n_annotated": n_annotated}


# ============================================================
# Phase 2
# ============================================================
class Phase2Request(BaseModel):
    phase1_job_id: str
    methods: List[str]
    knn_k: int = 25
    min_votes: int = 2
    sample_cols: List[str] = []
    template_max_per_label: int = 500


@app.post("/api/phase2/jobs")
async def start_phase2(payload: Phase2Request):
    phase1_job_id = _safe_component(payload.phase1_job_id)
    phase1_outdir = PHASE1_DIR / phase1_job_id
    if not phase1_outdir.exists():
        raise HTTPException(404, "Phase 1 job not found")
    if not payload.methods:
        raise HTTPException(400, "No methods selected")

    job = job_manager.create("phase2")
    outdir = PHASE2_DIR / job.id
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
    return {"job_id": job.id}


@app.get("/api/phase2/jobs/{job_id}/plots")
async def list_phase2_plots(job_id: str):
    job_id = _safe_component(job_id)
    plots_dir = PHASE2_DIR / job_id / "plots"
    if not plots_dir.exists():
        raise HTTPException(404, "No plots yet for this job")
    return {"plots": sorted(p.name for p in plots_dir.glob("*.png"))}


@app.get("/api/phase2/jobs/{job_id}/plot/{name}")
async def get_phase2_plot(job_id: str, name: str):
    job_id, name = _safe_component(job_id), _safe_component(name)
    path = PHASE2_DIR / job_id / "plots" / name
    if not path.exists():
        raise HTTPException(404, "Plot not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/phase2/jobs/{job_id}/download")
async def download_phase2_csv(job_id: str):
    job_id = _safe_component(job_id)
    path = PHASE2_DIR / job_id / "full_dataset_labeled_complete.csv"
    if not path.exists():
        raise HTTPException(404, "Result file not found")
    return FileResponse(path, filename="full_dataset_labeled_complete.csv")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
