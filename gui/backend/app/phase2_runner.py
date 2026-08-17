"""Wraps conclave.phase2 for the GUI job manager.

Uses the modern run_phase2_complete() function-argument API directly --
markers/sample_cols auto-detect from Phase 1's own pipeline_run_config.json
(written by the core package), so this no longer needs its own separate
gui_config.json bookkeeping.
"""
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
    from conclave.phase2.pipeline_complete import run_phase2_complete

    phase1_outdir_p = Path(phase1_outdir)
    outdir_p = Path(outdir)

    if not phase1_outdir_p.exists():
        raise ValueError(f"Phase 1 output directory not found: {phase1_outdir_p}")

    annotations_dir = phase1_outdir_p / "annotations"
    # A lightweight pre-check for a clearer error message than the
    # underlying pipeline would give -- run_phase2_complete() itself also
    # checks for annotation files (supporting both the annotation_template_
    # and *_annotated.csv naming conventions), this just fails faster with
    # a GUI-relevant message before committing to a full run.
    missing = []
    for m in methods:
        candidates = [
            annotations_dir / f"annotation_template_{m}.csv",
            annotations_dir / f"{m}_annotated.csv",
        ]
        if not any(c.exists() for c in candidates):
            missing.append(m)
    if missing:
        raise ValueError(
            f"Missing annotations for: {missing}. "
            f"Annotate and save them in the Phase 1 review step first, or "
            f"upload an already-annotated CSV for that method."
        )

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(phase1_outdir_p),
        phase2_output=str(outdir_p),
        annotations_dir=str(annotations_dir),
        consensus_methods=methods,
        knn_k=knn_k,
        min_votes=min_votes,
        sample_cols=sample_cols or None,
        template_max_per_label=template_max_per_label,
        # markers not passed -- auto-loaded from phase1_outdir/pipeline_run_config.json
    )

    return {
        "n_cells": int(len(df_labeled)),
        "mean_confidence": float(df_labeled["confidence_score"].mean()),
        "high_confidence_pct": float((df_labeled["confidence_score"] > 0.8).mean() * 100),
        "full_disagreement_pct": float(df_labeled["absolute_no_consensus"].mean() * 100),
        "consensus_label_counts": {
            str(k): int(v) for k, v in df_labeled["consensus_label"].value_counts().items()
        },
    }
