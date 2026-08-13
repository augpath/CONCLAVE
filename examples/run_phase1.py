"""Run CONCLAVE Phase 1 on the bundled example dataset.

Usage:
    python run_phase1.py

Works regardless of your current working directory -- paths are resolved
relative to this script's own location, not the directory you launch it
from.
"""
from pathlib import Path

import pandas as pd

from conclave.phase1 import run_annotation_pipeline_with_resume
import conclave.r_scripts

SCRIPT_DIR = Path(__file__).parent
CSV_PATH = SCRIPT_DIR / "Melanoma_example.csv"
OUTDIR = SCRIPT_DIR / "output_phase1"

MARKERS = [
    'CD34', 'CD31', 'CD141', 'PNAd', 'CD25', 'CD14', 'CD1c', 'CK', 'CD21',
    'FoxP3', 'CD23', 'GRB7', 'CD1A', 'Podoplanin', 'CD138', 'CD248', 'CD64', 'CD163',
    'Pax5', 'IRF8', 'CD20', 'CD8', 'CD303', 'LYZ', 'CD16', 'CD2', 'HLADR', 'IRF4', 'CD5',
    'CD79a', 'CD68', 'CD3', 'CD4', 'CD27', 'PRDM1', 'MELANA', 'S100B',
]

# ⚙️ config -- edit these to change what Phase 1 runs
CLUSTER_METHODS = ["phenograph", "kmeans"]

# FlowSOM and DepecheR ship with the package as R scripts -- their path is
# auto-detected below, no copy-pasting needed. You still need R itself,
# plus the FlowSOM/DepecheR R packages, installed separately. Both are
# opt-in (flip these to True) so nothing breaks if you don't have R set up.
USE_FLOWSOM = False
USE_DEPECHE = False

R_SCRIPTS_DIR = Path(conclave.r_scripts.__file__).parent
FLOWSOM_RSCRIPT = str(R_SCRIPTS_DIR / "flowsom_clustering.R")  # override with your own path if needed
DEPECHE_RSCRIPT = str(R_SCRIPTS_DIR / "depeche_clustering.R")  # override with your own path if needed

if USE_FLOWSOM:
    CLUSTER_METHODS.append("flowsom")
if USE_DEPECHE:
    CLUSTER_METHODS.append("depeche")


def main():
    print(f"Loading {CSV_PATH} ...")
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {len(df):,} cells x {df.shape[1]} columns")
    print(f"Cluster methods: {CLUSTER_METHODS}")

    df_clustered, metadata = run_annotation_pipeline_with_resume(
        df=df,
        markers=MARKERS,
        outdir=str(OUTDIR),
        sample_cols=["ID"],
        normalization="z-score",
        sampling="stratified-notproportional",
        sample_size=20000,
        cluster_methods=tuple(CLUSTER_METHODS),
        phenograph_k=25,
        derive_kmeans_from="phenograph",
        flowsom_rscript=FLOWSOM_RSCRIPT if USE_FLOWSOM else None,
        depeche_rscript=DEPECHE_RSCRIPT if USE_DEPECHE else None,
    )

    print()
    print(f"Clustered {len(df_clustered):,} cells")
    print(f"Cluster counts: {metadata['results']['cluster_counts']}")
    print()
    print("Next step: annotate the clusters.")
    print(f"  1. Review the heatmaps in {OUTDIR / '04_cluster_heatmaps'}")
    print(f"  2. Fill in the 'annotation' column of each annotation_template_<method>.csv")
    print(f"  3. Save your filled-in files into {SCRIPT_DIR / 'annotations'} as <method>_annotated.csv")
    print(f"  4. Run run_phase2.py")


if __name__ == "__main__":
    main()
