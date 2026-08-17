"""Wraps conclave.phase1 for the GUI job manager."""
import json
from pathlib import Path
from typing import List, Optional


def run_phase1_job(
    csv_path: str,
    outdir: str,
    markers: List[str],
    sample_cols: Optional[List[str]],
    normalization: Optional[str],
    sampling: str,
    sample_size: int,
    n_tiles_per_axis: int,
    dr_method: Optional[str],
    dr_n_components: int,
    cluster_methods: List[str],
    phenograph_k: int,
    derive_kmeans_from: Optional[str],
    flowsom_rscript: Optional[str],
    depeche_rscript: Optional[str],
    seed: int,
    force_restart: bool = True,
):
    import pandas as pd
    from conclave.phase1 import run_annotation_pipeline_with_resume

    # Auto-detect the bundled R scripts, same as the Jupyter notebooks do,
    # so the user doesn't have to know/type a container-internal path.
    if not flowsom_rscript and "flowsom" in cluster_methods:
        import conclave.r_scripts
        flowsom_rscript = str(Path(conclave.r_scripts.__file__).parent / "flowsom_clustering.R")
    if not depeche_rscript and "depeche" in cluster_methods:
        import conclave.r_scripts
        depeche_rscript = str(Path(conclave.r_scripts.__file__).parent / "depeche_clustering.R")

    outdir_p = Path(outdir)
    outdir_p.mkdir(parents=True, exist_ok=True)

    print(f"Loading {csv_path} ...")
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df):,} cells x {df.shape[1]} columns")
    if force_restart:
        print("force_restart=True -- ignoring any existing checkpoints in this output directory")
    else:
        print("force_restart=False -- resuming from any existing checkpoints in this output directory")

    df_labeled, meta = run_annotation_pipeline_with_resume(
        df=df,
        markers=markers,
        outdir=str(outdir_p),
        sample_cols=sample_cols or None,
        normalization=normalization,
        sampling=sampling,
        sample_size=sample_size,
        n_tiles_per_axis=n_tiles_per_axis,
        dr_method=dr_method,
        dr_n_components=dr_n_components,
        cluster_methods=tuple(cluster_methods),
        phenograph_k=phenograph_k,
        derive_kmeans_from=derive_kmeans_from,
        flowsom_rscript=flowsom_rscript,
        depeche_rscript=depeche_rscript,
        seed=seed,
        resume=not force_restart,
        force_restart=force_restart,
    )

    # Persist the config Phase 2 needs (markers, sample_cols) so the GUI
    # doesn't have to ask the user to retype it for Phase 2.
    with open(outdir_p / "gui_config.json", "w") as f:
        json.dump(
            {
                "markers": markers,
                "sample_cols": sample_cols or [],
                "cluster_methods": list(cluster_methods),
            },
            f,
        )

    cluster_counts = meta.get("results", {}).get("cluster_counts", {})
    failed_methods = meta.get("results", {}).get("failed_methods", {})
    return {
        "n_cells_clustered": int(len(df_labeled)),
        "cluster_counts": cluster_counts,
        "failed_methods": failed_methods,
        "methods": list(cluster_counts.keys()),
    }
