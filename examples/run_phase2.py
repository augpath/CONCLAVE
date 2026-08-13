"""Run CONCLAVE Phase 2 on the output of run_phase1.py.

Usage:
    python run_phase2.py

Requires run_phase1.py to have been run first, and its cluster annotation
templates (in output_phase1/04_cluster_heatmaps/) filled in and saved to
annotations/<method>_annotated.csv.

If no annotations are found, this script offers to generate PLACEHOLDER
annotations (round-robin fake cell-type labels) so you can see the full
pipeline run end to end -- this is for testing the pipeline mechanics
only, NOT real biology. Don't use placeholder-annotated results for
anything scientific.
"""
from pathlib import Path

import pandas as pd

from conclave.phase2.pipeline_complete import run_phase2_complete

SCRIPT_DIR = Path(__file__).parent
PHASE1_OUTPUT = SCRIPT_DIR / "output_phase1"
PHASE2_OUTPUT = SCRIPT_DIR / "output_phase2"
ANNOTATIONS_DIR = SCRIPT_DIR / "annotations"
CONSENSUS_METHODS = ["phenograph", "kmeans"]

PLACEHOLDER_CELL_TYPES = [
    "Tcell", "Bcell", "Macrophage", "Melanoma", "Endothelial", "DC", "Fibroblast",
]


def _annotations_exist() -> bool:
    return all(
        (ANNOTATIONS_DIR / f"{m}_annotated.csv").exists() for m in CONSENSUS_METHODS
    )


def _write_placeholder_annotations():
    print()
    print("=" * 70)
    print("No annotations found in", ANNOTATIONS_DIR)
    print("Generating PLACEHOLDER annotations (round-robin fake cell types)")
    print("so you can see the full pipeline run end to end.")
    print("These are NOT real biology -- do not use for anything scientific.")
    print("=" * 70)
    print()

    heatmap_dir = PHASE1_OUTPUT / "04_cluster_heatmaps"
    ANNOTATIONS_DIR.mkdir(exist_ok=True)
    for method in CONSENSUS_METHODS:
        template_path = heatmap_dir / f"annotation_template_{method}.csv"
        if not template_path.exists():
            raise FileNotFoundError(
                f"{template_path} not found -- did you run run_phase1.py first, "
                f"and does its CLUSTER_METHODS match {CONSENSUS_METHODS} here?"
            )
        template = pd.read_csv(template_path)
        template["annotation"] = [
            PLACEHOLDER_CELL_TYPES[i % len(PLACEHOLDER_CELL_TYPES)]
            for i in range(len(template))
        ]
        out_path = ANNOTATIONS_DIR / f"{method}_annotated.csv"
        template.to_csv(out_path, index=False)
        print(f"  wrote {out_path}")


def main():
    if not _annotations_exist():
        _write_placeholder_annotations()

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(PHASE1_OUTPUT),
        phase2_output=str(PHASE2_OUTPUT),
        annotations_dir=str(ANNOTATIONS_DIR),
        consensus_methods=CONSENSUS_METHODS,
        knn_k=25,
        # markers not passed -- auto-loaded from output_phase1/pipeline_run_config.json
    )

    print()
    print(f"Labeled {len(df_labeled):,} cells")
    print(f"Consensus confidence: {df_labeled['confidence_score'].mean():.3f}")
    print(f"Full disagreement: {df_labeled['absolute_no_consensus'].mean()*100:.1f}%")
    print()
    print(f"Outputs written to {PHASE2_OUTPUT}")


if __name__ == "__main__":
    main()
