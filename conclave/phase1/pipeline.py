"""CONCLAVE Phase 1 - Main Pipeline"""
import time
import json
import logging
import shutil
from pathlib import Path
import pandas as pd
import numpy as np

from conclave.phase1.utils import *
from conclave.phase1.normalization import *
from conclave.phase1.sampling import *
from conclave.phase1.clustering import *
from conclave.phase1.visualization import *


# Main Pipeline
# ============================================================
# MODIFIED MAIN PIPELINE WITH CHECKPOINT SUPPORT
# Replace the existing run_annotation_pipeline function with this
# ============================================================

def run_annotation_pipeline(
    df: pd.DataFrame,
    markers: list,
    outdir,
    clustering_markers: list = None,  # NEW: Subset for clustering
    sample_cols=None,
    metadata_cols=None,
    normalization="z-score",
    sampling="stratified-notproportional",
    sample_size=50000,
    n_tiles_per_axis=4,
    use_gpu=False,  # GPU acceleration for UMAP
    gpu_pca_components=50,  # PCA components for GPU
    dr_method=None,
    dr_n_components=15,
    cluster_methods=("phenograph", "flowsom", "kmeans"),
    phenograph_k=25,
    derive_kmeans_from="phenograph",
    flowsom_rscript=None,
    depeche_rscript=None,
    keep_r_tmp=False,
    save_intermediates=True,
    top_n_markers=15,
    seed=42,
    method_params=None,
    _resume=False,  # Internal: resume mode
    _logger=None,  # Internal: reuse logger
):
    """
    Run complete CONCLAVE Phase 1 annotation pipeline with checkpoint support.
    
    New Parameters
    --------------
    Use run_annotation_pipeline_with_resume() instead to enable:
    - resume : bool
        Resume from checkpoints if available
    - force_restart : bool
        Clear checkpoints and start fresh
    
    [... rest of docstring same as before ...]
    """
    
    # Setup
    # Default: use all markers for clustering
    if clustering_markers is None:
        clustering_markers = markers
    
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Reuse logger if provided, otherwise create new
    if _logger:
        logger = _logger
        log_path = outdir / "pipeline_log.txt"
    else:
        logger, log_path = setup_logger(outdir)
        logger.info("="*80)
        logger.info("CONCLAVE PHASE 1: ANNOTATION PIPELINE")
        logger.info("="*80)
    
    logger.info(f"Input: {len(df):,} cells × {len(markers)} markers")
    logger.info(f"Output: {outdir}")
    logger.info(f"Random seed: {seed}")
    logger.info(f"Resume mode: {_resume}")
    logger.info("="*80)
    
    method_params = method_params or {}
    
    # Ensure cell_id exists
    df = ensure_cell_id(df)
    
    # ================================================================
    # STEP 0: Input Validation
    # ================================================================
    if _resume and check_checkpoint_exists(outdir, 'validation'):
        logger.info("")
        logger.info("STEP 0: Input Validation")
        logger.info("-" * 80)
        logger.info("✓ Skipping (using checkpoint)")
    else:
        logger.info("")
        logger.info("STEP 0: Input Validation")
        logger.info("-" * 80)
        validate_input_dataframe(df=df, markers=markers, logger=logger)
        save_checkpoint(outdir, 'validation', {'completed': True}, logger)
    
    # ================================================================
    # STEP 1: Sanity Checks
    # ================================================================
    if _resume and check_checkpoint_exists(outdir, 'sanity_check'):
        logger.info("")
        logger.info("STEP 1: Data Quality Checks")
        logger.info("-" * 80)
        logger.info("✓ Skipping (using checkpoint)")
    else:
        logger.info("")
        logger.info("STEP 1: Data Quality Checks")
        logger.info("-" * 80)
        sanity_check_dataframe(
            df=df,
            markers=markers,
            outdir=outdir / "00_sanitycheck",
            logger=logger
        )
        save_checkpoint(outdir, 'sanity_check', {'completed': True}, logger)
    
    # ================================================================
    # STEP 2: Normalization
    # ================================================================
    norm_checkpoint = outdir / "01_normalized_full.csv"
    
    if _resume and norm_checkpoint.exists():
        logger.info("")
        logger.info("STEP 2: Normalization")
        logger.info("-" * 80)
        logger.info(f"✓ Loading from checkpoint: {norm_checkpoint}")
        df_norm = pd.read_csv(norm_checkpoint)
        df_norm = ensure_cell_id(df_norm)
        logger.info(f"  Loaded: {df_norm.shape}")
        
        # Load report if exists
        report_path = outdir / "00_sanitycheck" / "normalization_report.json"
        if report_path.exists():
            with open(report_path, 'r') as f:
                norm_report = json.load(f)
        else:
            norm_report = {}
    else:
        logger.info("")
        logger.info("STEP 2: Normalization")
        logger.info("-" * 80)
        df_norm, norm_report = run_step(
            "Normalization",
            normalize_markers,
            outdir, logger,
            df=df,
            markers=markers,
            method=normalization,
            sample_cols=sample_cols,
            clip=method_params.get("zscore", {}).get("clip", 5.0),
            q=method_params.get("minmax", {}).get("q", 0.99),
            scale=method_params.get("lognorm", {}).get("scale", 1e4),
            logger=logger
        )
        
        # Save normalization report
        norm_report_path = outdir / "00_sanitycheck" / "normalization_report.json"
        with open(norm_report_path, "w") as f:
            json.dump(norm_report, f, indent=2)
        logger.info(f"Saved normalization report → {norm_report_path}")
        
        if save_intermediates:
            save_step_artifacts(
                df_norm, markers, outdir,
                prefix="01_normalized",
                logger=logger
            )
        
        save_checkpoint(outdir, 'normalization', {
            'shape': list(df_norm.shape),
            'file': str(norm_checkpoint)
        }, logger)
    
    # ================================================================
    # STEP 3: Sampling
    # ================================================================
    samp_checkpoint = outdir / "02_sampled_full.csv"
    
    if _resume and samp_checkpoint.exists():
        logger.info("")
        logger.info("STEP 3: Sampling")
        logger.info("-" * 80)
        logger.info(f"✓ Loading from checkpoint: {samp_checkpoint}")
        df_samp = pd.read_csv(samp_checkpoint)
        df_samp = ensure_cell_id(df_samp)
        logger.info(f"  Loaded: {df_samp.shape}")
    else:
        logger.info("")
        logger.info("STEP 3: Sampling")
        logger.info("-" * 80)
        df_samp = run_step(
            "Sampling",
            sample_umap_tiles,
            outdir, logger,
            df=df_norm,
            markers=markers,
            sample_size=sample_size,
            mode=sampling,
            n_tiles_per_axis=n_tiles_per_axis,
            random_state=seed,
            umap_params=method_params.get("sampling_umap", {
                "n_neighbors": 15,
                "min_dist": 0.1,
                "metric": "euclidean"
            }),
            use_gpu=use_gpu,
            gpu_pca_components=gpu_pca_components,
            logger=logger
        )
        
        df_samp = ensure_cell_id(df_samp)
        
        if save_intermediates:
            save_step_artifacts(
                df_samp, markers, outdir,
                prefix="02_sampled",
                logger=logger
            )
        
        save_checkpoint(outdir, 'sampling', {
            'shape': list(df_samp.shape),
            'file': str(samp_checkpoint)
        }, logger)
    
    # ================================================================
    # STEP 4: Dimensionality Reduction
    # ================================================================
    dr_checkpoint = outdir / "02_dr" / "dr_matrix.csv"
    
    if _resume and dr_checkpoint.exists():
        logger.info("")
        logger.info("STEP 4: Dimensionality Reduction")
        logger.info("-" * 80)
        logger.info(f"✓ Loading from checkpoint: {dr_checkpoint}")
        X_dr_df = pd.read_csv(dr_checkpoint)
        
        # Load DR info
        dr_info_path = outdir / "02_dr" / "dr_info.csv"
        if dr_info_path.exists():
            dr_info = pd.read_csv(dr_info_path).iloc[0].to_dict()
        else:
            dr_info = {'dr_method': None}
        
        logger.info(f"  DR method: {dr_info.get('dr_method')}")
        logger.info(f"  Loaded matrix: {X_dr_df.shape}")
        
        # Determine feature columns. NOTE: dr_info was round-tripped through
        # CSV (see dr_info.csv save below), which turns a Python None into
        # an empty cell that pandas reads back as float NaN, NOT None --
        # so "dr_info.get('dr_method') is None" would incorrectly be False
        # here even when no DR method was used. pd.isna() handles both.
        dr_method_loaded = dr_info.get('dr_method')
        if pd.isna(dr_method_loaded):
            dr_cols = clustering_markers  # Use subset for clustering
            X_for_clustering = X_dr_df[clustering_markers].copy()  # Use subset
        else:
            dr_cols = [c for c in X_dr_df.columns if c.startswith('DR') and c != 'DR']
            X_for_clustering = X_dr_df[dr_cols].copy()
        
        # Create X_dr for compatibility
        if pd.isna(dr_method_loaded):
            X_dr = X_dr_df[markers].values
        else:
            X_dr = X_dr_df[dr_cols].values
    else:
        logger.info("")
        logger.info("STEP 4: Dimensionality Reduction")
        logger.info("-" * 80)
        X_dr, dr_info = run_step(
            "Dimensionality Reduction",
            run_dr,
            outdir, logger,
            df=df_samp,
            markers=markers,
            method=dr_method,
            n_components=dr_n_components,
            random_state=seed,
            umap_params=method_params.get("dr_umap", {
                "n_neighbors": 15,
                "min_dist": 0.1,
                "metric": "euclidean"
            }),
            pacmap_params=method_params.get("dr_pacmap", {
                "n_neighbors": 10,
                "MN_ratio": 0.5,
                "FP_ratio": 2.0
            }),
            logger=logger
        )
        
        # Save DR results
        dr_dir = outdir / "02_dr"
        dr_dir.mkdir(parents=True, exist_ok=True)
        pd.DataFrame([dr_info]).to_csv(dr_dir / "dr_info.csv", index=False)
        
        if dr_info.get("dr_method") is None:
            dr_cols = markers
            X_dr_df = df_samp[["cell_id"] + list(markers)].copy()
            X_dr_df[markers] = X_dr_df[markers].apply(
                pd.to_numeric, errors="coerce"
            ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            X_for_clustering = X_dr_df[clustering_markers].copy()  # Use subset
        else:
            dr_cols = [f"DR{i+1}" for i in range(X_dr.shape[1])]
            X_dr_df = pd.DataFrame(X_dr, columns=dr_cols)
            X_dr_df.insert(0, "cell_id", df_samp["cell_id"].astype(str).values)
            X_for_clustering = X_dr_df[dr_cols].copy()
        
        X_dr_df.to_csv(dr_dir / "dr_matrix.csv", index=False)
        logger.info(f"Saved DR matrix → {dr_dir/'dr_matrix.csv'} | shape={X_dr_df.shape}")
        
        save_checkpoint(outdir, 'dr', {
            'method': dr_info.get('dr_method'),
            'shape': list(X_dr_df.shape),
            'file': str(dr_checkpoint)
        }, logger)
    

    # ================================================================
    # STEP 5: Clustering
    # ================================================================
    clust_checkpoint = outdir / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"
    
    # Check if we can resume clustering
    can_resume_clustering = False
    missing_methods = []
    
    if _resume and clust_checkpoint.exists():
        # Load existing results to check what methods were run
        df_temp = pd.read_csv(clust_checkpoint)
        existing_methods = [m for m in cluster_methods if f"label_{m}" in df_temp.columns]
        missing_methods = [m for m in cluster_methods if f"label_{m}" not in df_temp.columns]
        
        if len(existing_methods) == len(cluster_methods):
            # All requested methods are present - can resume
            can_resume_clustering = True
        elif len(existing_methods) > 0 and len(missing_methods) > 0:
            # Some methods present, some missing
            logger.info("")
            logger.info("STEP 5: Multi-Method Clustering")
        logger.info(f"  Total markers: {len(markers)}")
        logger.info(f"  Clustering markers: {len(clustering_markers)}")
        if len(clustering_markers) < len(markers):
            logger.info(f"    Using marker subset: {clustering_markers}")
            logger.info("-" * 80)
            logger.warning(f"⚠️  Checkpoint found, but missing methods: {missing_methods}")
            logger.warning(f"⚠️  Previous run had: {existing_methods}")
            logger.warning(f"⚠️  Re-running clustering with all {len(cluster_methods)} methods")
            can_resume_clustering = False
        else:
            # No overlap - re-run
            can_resume_clustering = False
    
    if can_resume_clustering:
        logger.info("")
        logger.info("STEP 5: Multi-Method Clustering")
        logger.info(f"  Total markers: {len(markers)}")
        logger.info(f"  Clustering markers: {len(clustering_markers)}")
        if len(clustering_markers) < len(markers):
            logger.info(f"    Using marker subset: {clustering_markers}")
        logger.info("-" * 80)
        logger.info(f"✓ Loading from checkpoint: {clust_checkpoint}")
        df_labeled = pd.read_csv(clust_checkpoint)
        df_labeled = ensure_cell_id(df_labeled)
        
        # Extract labels_dict
        labels_dict = {}
        for method in cluster_methods:
            label_col = f"label_{method}"
            if label_col in df_labeled.columns:
                labels_dict[method] = df_labeled[label_col].values
        
        # Load metadata
        meta_path = outdir / "03_clustering_annotation" / "meta_run.json"
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                clust_meta = json.load(f)
        else:
            clust_meta = {'cluster_counts': {m: len(np.unique(l)) for m, l in labels_dict.items()}}
        
        logger.info(f"  Loaded: {df_labeled.shape}")
        logger.info(f"  Methods: {list(labels_dict.keys())}")
        logger.info(f"  ✓ All {len(cluster_methods)} requested methods found in checkpoint")
        
    else:
        logger.info("")
        logger.info("STEP 5: Multi-Method Clustering")
        logger.info(f"  Total markers: {len(markers)}")
        logger.info(f"  Clustering markers: {len(clustering_markers)}")
        if len(clustering_markers) < len(markers):
            logger.info(f"    Using marker subset: {clustering_markers}")
        logger.info("-" * 80)
        
        if missing_methods:
            logger.info(f"Running clustering with all methods (previously missing: {missing_methods})")
        
        # Create proxy dataframe with DR features attached
        df_proxy = df_samp.copy()
        for col in X_for_clustering.columns:
            df_proxy[col] = X_for_clustering[col].values
        
        feature_cols = list(X_for_clustering.columns)
        
        df_labeled, labels_dict, clust_meta = run_step(
            "Multi-method clustering",
            cluster_annotation_subset,
            outdir, logger,
            df=df_proxy,
            feature_cols=feature_cols,
            markers_for_r=markers,
            outdir=outdir,
            methods=cluster_methods,
            seed=seed,
            phenograph_k=phenograph_k,
            derive_kmeans_from=derive_kmeans_from,
            flowsom_rscript=flowsom_rscript,
            depeche_rscript=depeche_rscript,
            keep_r_tmp=keep_r_tmp,
            logger=logger
        )
        
        save_checkpoint(outdir, 'clustering', {
            'methods': list(clust_meta.get('cluster_counts', {}).keys()),  # methods that actually succeeded, not just requested
            'cluster_counts': clust_meta.get('cluster_counts', {}),
            'failed_methods': clust_meta.get('failed_methods', {}),
            'file': str(clust_checkpoint)
        }, logger)
        
        if clust_meta.get('failed_methods'):
            logger.warning("")
            logger.warning("⚠️  Some clustering methods failed and were skipped:")
            for m, err in clust_meta['failed_methods'].items():
                logger.warning(f"    {m}: {err}")
            logger.warning("  Fix the underlying issue and re-run to retry just these methods.")
        
    # ================================================================
    # STEP 6: Visualization
    # ================================================================
    # Resuming only regenerates visualizations if every requested method's
    # output is already present -- mirrors the same per-method check used
    # for the clustering step above.
    viz_can_resume = False
    if _resume and check_checkpoint_exists(outdir, 'visualization'):
        viz_checkpoint = load_checkpoint(outdir, 'visualization', logger)
        viz_outputs = (viz_checkpoint or {}).get('outputs', {}) or {}
        viz_missing_methods = [
            m for m in cluster_methods
            if m.strip().lower() not in viz_outputs
        ]
        if not viz_missing_methods:
            viz_can_resume = True

    if viz_can_resume:
        logger.info("")
        logger.info("STEP 6: Cluster Visualization")
        logger.info("-" * 80)
        logger.info("✓ Skipping (using checkpoint)")
        
        # Load summary outputs
        viz_checkpoint = load_checkpoint(outdir, 'visualization', logger)
        summary_outputs = viz_checkpoint.get('outputs', {}) if viz_checkpoint else {}
    else:
        logger.info("")
        logger.info("STEP 6: Cluster Visualization")
        logger.info("-" * 80)
        if _resume and check_checkpoint_exists(outdir, 'visualization'):
            logger.info(
                f"  Checkpoint found, but missing methods: {viz_missing_methods} "
                f"-- regenerating visualizations for all {len(cluster_methods)} methods"
            )
        
        summary_outputs = export_cluster_topN_per_cluster(
            df_labeled=df_labeled,
            markers=markers,
            methods=cluster_methods,
            outdir=outdir,
            top_n_markers=top_n_markers,
            logger=logger,
            show_heatmaps=False
        )
        
        save_checkpoint(outdir, 'visualization', {
            'completed': True,
            'outputs': summary_outputs
        }, logger)
    
    # ================================================================
    # STEP 6b: Prepare annotations/ folder
    # ================================================================
    # Copies each method's blank annotation_template_<method>.csv from
    # 04_cluster_heatmaps/ into a dedicated annotations/ folder, ready to
    # edit -- saves the manual "create a folder and copy files" step
    # before Phase 2. Never overwrites a file already there (in case the
    # user has already started filling one in and this step re-runs, e.g.
    # via resume after adding a method).
    logger.info("")
    logger.info("STEP 6b: Preparing annotations/ folder")
    logger.info("-" * 80)
    annotations_dir = outdir / "annotations"
    annotations_dir.mkdir(exist_ok=True)
    heatmap_dir = outdir / "04_cluster_heatmaps"
    copied, skipped_existing = [], []
    for method in cluster_methods:
        src = heatmap_dir / f"annotation_template_{method}.csv"
        dst = annotations_dir / f"annotation_template_{method}.csv"
        if not src.exists():
            continue
        if dst.exists():
            skipped_existing.append(method)
            continue
        shutil.copy2(src, dst)
        copied.append(method)
    if copied:
        logger.info(f"  Copied templates for {copied} -> {annotations_dir}")
    if skipped_existing:
        logger.info(f"  Left existing files untouched for {skipped_existing} (already in annotations/)")
    logger.info(f"  Next: fill in the 'annotation' column in each file in {annotations_dir}, then run Phase 2")

    # ================================================================
    # STEP 7: Save Final Metadata
    # ================================================================
    logger.info("")
    logger.info("STEP 7: Saving Metadata")
    logger.info("-" * 80)
    
    final_meta = {
        "input": {
            "n_cells_original": int(len(df)),
            "n_cells_sampled": int(len(df_labeled)),
            "n_markers": int(len(markers)),
            "markers": list(markers),
            "sample_cols": sample_cols,
            "metadata_cols": metadata_cols
        },
        "parameters": {
            "normalization": normalization,
            "sampling": sampling,
            "sample_size": sample_size,
            "n_tiles_per_axis": int(n_tiles_per_axis),
            "dr_method": dr_method,
            "dr_n_components": int(dr_n_components),
            "cluster_methods": list(cluster_methods),
            "phenograph_k": int(phenograph_k),
            "derive_kmeans_from": derive_kmeans_from,
            "top_n_markers": int(top_n_markers),
            "seed": int(seed),
            "resume_used": _resume
        },
        "results": {
            "cluster_counts": clust_meta.get("cluster_counts", {}),
            "runtimes": clust_meta.get("runtimes", {}),
            "failed_methods": clust_meta.get("failed_methods", {}),
        },
        "outputs": {
            "normalization_report": str(outdir / "00_sanitycheck" / "normalization_report.json"),
            "normalized_full": str(outdir / "01_normalized_full.csv") if save_intermediates else None,
            "sampled_full": str(outdir / "02_sampled_full.csv") if save_intermediates else None,
            "dr_matrix": str(outdir / "02_dr" / "dr_matrix.csv"),
            "labeled_sampled_df": str(outdir / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"),
            "heatmap_dir": str(outdir / "04_cluster_heatmaps"),
            "annotations_dir": str(outdir / "annotations"),
            "visualization_outputs": summary_outputs,
        },
        "log_file": str(log_path),
    }
    
    with open(outdir / "pipeline_run_config.json", "w") as f:
        json.dump(final_meta, f, indent=2)
    
    logger.info(f"Saved pipeline config → {outdir/'pipeline_run_config.json'}")
    
    # Final summary
    logger.info("")
    logger.info("="*80)
    if final_meta["results"]["failed_methods"]:
        logger.info("⚠️  PIPELINE COMPLETE -- WITH FAILURES")
    else:
        logger.info("✅ PIPELINE COMPLETE!")
    logger.info("="*80)
    logger.info(f"Processed: {len(df):,} → {len(df_labeled):,} cells")
    logger.info(f"Clustering methods (succeeded): {list(labels_dict.keys())}")
    logger.info(f"Cluster counts: {final_meta['results']['cluster_counts']}")
    if final_meta["results"]["failed_methods"]:
        logger.info("")
        logger.info("⚠️  FAILED METHODS (skipped, not included above):")
        for m, err in final_meta["results"]["failed_methods"].items():
            logger.info(f"    {m}: {err}")
        logger.info("  Fix the underlying issue and re-run with resume=True to retry just these.")
        logger.info("")
    logger.info(f"Output directory: {outdir}")
    if _resume:
        logger.info("Resume mode was active - some steps may have been skipped")
    logger.info("="*80)
    
    return df_labeled, final_meta


# Wrapper
def run_annotation_pipeline_with_resume(
    df,
    markers,
    outdir,
    clustering_markers=None,  # NEW: Subset for clustering (defaults to markers)
    resume=True,  # NEW PARAMETER
    force_restart=False,  # NEW PARAMETER
    **kwargs  # All other pipeline parameters
):
    """
    Wrapper around run_annotation_pipeline with checkpoint/resume support.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    markers : list
        Marker column names
    outdir : Path
        Output directory
    resume : bool, default=True
        If True, resume from checkpoints if available
    force_restart : bool, default=False
        If True, clear all checkpoints and start fresh
    **kwargs
        All other parameters for run_annotation_pipeline
    
    Returns
    -------
    df_labeled : pd.DataFrame
        Labeled dataframe
    meta : dict
        Pipeline metadata
    
    Examples
    --------
    # Resume from checkpoints if available
    >>> df_labeled, meta = run_annotation_pipeline_with_resume(
    ...     df=df, markers=MARKERS, outdir="./output",
    ...     resume=True
    ... )
    
    # Force restart (ignore checkpoints)
    >>> df_labeled, meta = run_annotation_pipeline_with_resume(
    ...     df=df, markers=MARKERS, outdir="./output",
    ...     force_restart=True
    ... )
    
    # Disable resume (same as force_restart but clearer)
    >>> df_labeled, meta = run_annotation_pipeline_with_resume(
    ...     df=df, markers=MARKERS, outdir="./output",
    ...     resume=False
    ... )
    """
    
    # Default: clustering_markers = markers
    if clustering_markers is None:
        clustering_markers = markers
    
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    # Setup logger
    logger, log_path = setup_logger(outdir)
    
    logger.info("="*80)
    logger.info("CONCLAVE PHASE 1: ANNOTATION PIPELINE (with Resume Support)")
    logger.info("="*80)
    
    # Handle force restart
    if force_restart:
        logger.info("⚠️  Force restart requested - clearing all checkpoints")
        clear_checkpoints(outdir, logger)
        resume = False
    
    # Check if resume is possible
    if resume:
        logger.info("Checking for previous checkpoints...")
        
        # Extract params for validation
        params = {
            'normalization': kwargs.get('normalization', 'z-score'),
            'sampling': kwargs.get('sampling', 'stratified-notproportional'),
            'sample_size': kwargs.get('sample_size', 50000),
            'dr_method': kwargs.get('dr_method', None),
        }
        
        compatible, reason = validate_checkpoint_compatibility(
            outdir, df, markers, params, logger
        )
        
        if not compatible:
            logger.warning(f"⚠️  Checkpoints incompatible: {reason}")
            logger.warning("⚠️  Starting fresh (use force_restart=True to suppress this)")
            clear_checkpoints(outdir, logger)
            resume = False
        else:
            completed_steps = detect_completed_steps(outdir, logger)
            
            if completed_steps:
                logger.info(f"✓ Found {len(completed_steps)} completed steps - resuming")
            else:
                logger.info("No previous checkpoints found - starting fresh")
                resume = False
    else:
        logger.info("Resume disabled - starting fresh")
    
    # Call the actual pipeline with resume flag
    return run_annotation_pipeline(
        df=df,
        markers=markers,
        outdir=outdir,
        clustering_markers=clustering_markers,  # Pass explicitly
        _resume=resume,  # Internal flag
        _logger=logger,  # Reuse logger
        **kwargs
    )


# ============================================================
# USAGE EXAMPLES
# ============================================================

"""
# Example 1: Auto-resume (default behavior)
df_labeled, meta = run_annotation_pipeline_with_resume(
    df=df,
    markers=MARKERS,
    outdir=Path("./output"),
    sample_cols=["ID"],
    cluster_methods=("phenograph", "kmeans", "flowsom"),
    phenograph_k=25,
    seed=42
)
# If pipeline crashed after normalization, this will skip validation,
# sanity check, and normalization - start directly from sampling

# Example 2: Force complete restart
df_labeled, meta = run_annotation_pipeline_with_resume(
    df=df,
    markers=MARKERS,
    outdir=Path("./output"),
    force_restart=True,  # Clear all checkpoints
    cluster_methods=("phenograph", "kmeans"),
    seed=42
)

# Example 3: Disable resume
df_labeled, meta = run_annotation_pipeline_with_resume(
    df=df,
    markers=MARKERS,
    outdir=Path("./output"),
    resume=False,  # Don't check for checkpoints
    cluster_methods=("phenograph", "kmeans"),
    seed=42
)

# Example 4: Change parameters (will auto-restart)
# First run:
df_labeled, meta = run_annotation_pipeline_with_resume(
    df=df, markers=MARKERS, outdir=Path("./output"),
    sample_size=50000
)
# If crashed, then you change sample_size:
df_labeled, meta = run_annotation_pipeline_with_resume(
    df=df, markers=MARKERS, outdir=Path("./output"),
    sample_size=100000  # Changed! Will detect incompatibility and restart
)
"""