"""Wraps conclave.phase2 for the GUI job manager."""
import json
from pathlib import Path
from typing import List, Optional


def run_phase2_job(
    phase1_outdir: str,
    outdir: str,
    methods: List[str],
    knn_k: int,
    min_votes: int,
    sample_cols: Optional[List[str]],
    template_max_per_label: int,
):
    import conclave.phase2.pipeline_complete as p2

    phase1_outdir_p = Path(phase1_outdir)
    outdir_p = Path(outdir)

    cfg_path = phase1_outdir_p / "gui_config.json"
    if not cfg_path.exists():
        raise ValueError(
            f"No gui_config.json found in {phase1_outdir_p} -- was this a "
            f"Phase 1 job run through the GUI?"
        )
    with open(cfg_path) as f:
        cfg = json.load(f)
    markers = cfg["markers"]

    annotations_dir = phase1_outdir_p / "annotations"
    ann_files = {m: annotations_dir / f"{m}_annotated.csv" for m in methods}
    missing = [m for m, p in ann_files.items() if not p.exists()]
    if missing:
        raise ValueError(
            f"Missing saved annotations for: {missing}. "
            f"Annotate and save them in the Phase 1 review step first."
        )

    p2.PHASE1_OUTPUT = phase1_outdir_p
    p2.PHASE2_OUTPUT = outdir_p
    p2.ANNOTATIONS_DIR = annotations_dir
    p2.CLUSTERED_FILE = (
        phase1_outdir_p / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"
    )
    p2.FULL_DATA_FILE = phase1_outdir_p / "01_normalized_full.csv"
    p2.ANNOTATION_FILES = ann_files
    p2.MARKERS = markers
    p2.CONSENSUS_METHODS = methods
    p2.KNN_K = knn_k
    p2.MIN_VOTES = min_votes
    p2.SAMPLE_COLS = sample_cols or cfg.get("sample_cols") or []
    p2.TEMPLATE_MAX_PER_LABEL = template_max_per_label

    outdir_p.mkdir(parents=True, exist_ok=True)
    (outdir_p / "templates").mkdir(exist_ok=True)
    (outdir_p / "plots").mkdir(exist_ok=True)

    df_labeled, template, single_templates, report = p2.run_phase2_complete()

    return {
        "n_cells": int(len(df_labeled)),
        "mean_confidence": float(df_labeled["confidence_score"].mean()),
        "high_confidence_pct": float((df_labeled["confidence_score"] > 0.8).mean() * 100),
        "full_disagreement_pct": float(df_labeled["absolute_no_consensus"].mean() * 100),
        "consensus_label_counts": {
            str(k): int(v) for k, v in df_labeled["consensus_label"].value_counts().items()
        },
    }
