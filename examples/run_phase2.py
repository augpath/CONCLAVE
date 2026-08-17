"""Run CONCLAVE Phase 2 on the output of run_phase1.py.

Usage:
    python run_phase2.py

Requires run_phase1.py to have been run first. Phase 1 automatically
copies annotation_template_<method>.csv files into output_phase1/annotations/
-- fill in the 'annotation' column in each and save before running this.

If nothing has been annotated yet, this script offers to generate
PLACEHOLDER annotations (round-robin fake cell-type labels) so you can see
the full pipeline run end to end -- this is for testing the pipeline
mechanics only, NOT real biology. Don't use placeholder-annotated results
for anything scientific.

By default, consensus_methods isn't set explicitly -- Phase 2 auto-detects
which methods to use for consensus based on which annotation files are
actually filled in (see run_phase2_complete()'s docstring). Edit
CONSENSUS_METHODS below if you want to pick a specific subset instead.
"""
from pathlib import Path

import pandas as pd

from conclave.phase2.pipeline_complete import run_phase2_complete

SCRIPT_DIR = Path(__file__).parent
PHASE1_OUTPUT = SCRIPT_DIR / "output_phase1"
PHASE2_OUTPUT = SCRIPT_DIR / "output_phase2"
ANNOTATIONS_DIR = PHASE1_OUTPUT / "annotations"  # what run_phase1.py already populates

# ⚙️ config -- leave as None to auto-detect from whichever files in
# ANNOTATIONS_DIR are actually filled in; set explicitly to pick a subset
CONSENSUS_METHODS = None

# Only used for generating placeholder annotations if nothing's been
# annotated yet (see _write_placeholder_annotations below) -- otherwise
# unused, since real annotation state is auto-detected.
METHODS_CLUSTERED_IN_PHASE1 = ["phenograph", "kmeans"]

PLACEHOLDER_CELL_TYPES = [
    "Tcell", "Bcell", "Macrophage", "Melanoma", "Endothelial", "DC", "Fibroblast",
]


def _any_annotations_exist() -> bool:
    if not ANNOTATIONS_DIR.exists():
        return False
    for path in ANNOTATIONS_DIR.glob("annotation_template_*.csv"):
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        if "annotation" in df.columns and df["annotation"].notna().any():
            return True
    return False


def _write_placeholder_annotations():
    print()
    print("=" * 70)
    print("No filled-in annotations found in", ANNOTATIONS_DIR)
    print("Generating PLACEHOLDER annotations (round-robin fake cell types)")
    print("so you can see the full pipeline run end to end.")
    print("These are NOT real biology -- do not use for anything scientific.")
    print("=" * 70)
    print()

    for method in METHODS_CLUSTERED_IN_PHASE1:
        template_path = ANNOTATIONS_DIR / f"annotation_template_{method}.csv"
        if not template_path.exists():
            raise FileNotFoundError(
                f"{template_path} not found -- did you run run_phase1.py first, "
                f"and does its CLUSTER_METHODS include {method}?"
            )
        template = pd.read_csv(template_path)
        template["annotation"] = [
            PLACEHOLDER_CELL_TYPES[i % len(PLACEHOLDER_CELL_TYPES)]
            for i in range(len(template))
        ]
        template.to_csv(template_path, index=False)
        print(f"  filled in {template_path}")


def main():
    if not _any_annotations_exist():
        _write_placeholder_annotations()

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(PHASE1_OUTPUT),
        phase2_output=str(PHASE2_OUTPUT),
        consensus_methods=CONSENSUS_METHODS,
        knn_k=25,
        # annotations_dir not passed -- auto-derived from phase1_output
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
