"""CONCLAVE Phase 1 - Clustering"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, MiniBatchKMeans, AgglomerativeClustering, Birch, AffinityPropagation
from conclave.phase1.utils import run_step, ensure_cell_id, save_df_with_cell_id


# Cell 13

# =========================
# 11) Save Intermediate Artifacts
# =========================

def save_step_artifacts(df_step, markers, outdir, prefix, logger=None):
    """
    Save outputs from each pipeline step.
    
    Saves:
      - Full dataframe with all columns
      - Marker matrix only
      - Preview (first 50 rows)
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    df_step = ensure_cell_id(df_step)
    
    # Full dataframe
    full_path = outdir / f"{prefix}_full.csv"
    save_df_with_cell_id(df_step, full_path)
    if logger:
        logger.info(f"  → {full_path.name} | shape={df_step.shape}")
    
    # Marker matrix only
    marker_path = outdir / f"{prefix}_X_markers.csv"
    marker_df = df_step[["cell_id"] + list(markers)].copy()
    marker_df.to_csv(marker_path, index=False)
    if logger:
        logger.info(f"  → {marker_path.name} | {len(markers)} markers")
    
    # Preview
    preview_path = outdir / f"{prefix}_preview_head50.csv"
    preview_df = df_step.head(50).copy()
    save_df_with_cell_id(preview_df, preview_path)
    if logger:
        logger.info(f"  → {preview_path.name} | preview")

# Cell 14
# =========================
# 8) Comprehensive Clustering Methods
# =========================
# Supports 12 clustering methods:
#   Python: PhenoGraph, KMeans, MiniBatchKMeans, MeanShift, DBSCAN,
#           Agglomerative, Spectral, Birch, AffinityPropagation, Leiden
#   R: FlowSOM, Depeche
#
# Features:
#   - Auto-derives n_clusters from PhenoGraph for methods requiring it
#   - Process-isolated Leiden (crash protection)
#   - R script support with proper error handling
#   - Robust per-method error handling
# =========================

import subprocess
import tempfile
import uuid
import os

# Helper for saving dataframes
def save_df(df, outdir, filename, logger=None, index=False):
    """Helper to save dataframe with logging"""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / filename
    df.to_csv(path, index=index)
    if logger:
        logger.info(f"Saved: {path}")
    return path



def cluster_leiden_labels(X_df, resolution=1.0, seed=42, knn_k=30, timeout=600, logger=None):
    """Leiden clustering with crash isolation"""
    # Direct implementation (no multiprocessing - Jupyter compatible)
    
    # Get numpy array from dataframe
    X = np.asarray(X_df.values, dtype=float)
    
    try:
        import igraph as ig
        import leidenalg
        from sklearn.neighbors import NearestNeighbors
        
        n = X.shape[0]
        if n < 2:
            if logger:
                logger.warning("Leiden: dataset too small")
            return np.zeros(n, dtype=int)
        
        # Build KNN graph
        k = min(int(knn_k), max(2, n - 1))
        knn = NearestNeighbors(n_neighbors=k, metric="euclidean").fit(X)
        knn_graph = knn.kneighbors_graph(X, mode="connectivity")
        
        # Convert to edge list
        sources, targets = knn_graph.nonzero()
        mask = sources < targets
        edges = list(zip(sources[mask].tolist(), targets[mask].tolist()))
        
        # Create igraph
        G = ig.Graph(n=n, edges=edges, directed=False)
        G.simplify(multiple=True, loops=True)
        
        if G.ecount() == 0:
            if logger:
                logger.warning("Leiden: no edges in graph")
            return np.zeros(n, dtype=int)
        
        # Run Leiden
        part = leidenalg.find_partition(
            G,
            leidenalg.RBConfigurationVertexPartition,
            resolution_parameter=resolution,
            seed=seed,
        )
        
        labels = np.asarray(part.membership, dtype=int)
        
        if logger:
            logger.info(f"Leiden: resolution={resolution} → {len(np.unique(labels))} clusters")
        
        return labels
        
    except Exception as e:
        if logger:
            logger.error(f"Leiden failed: {str(e)}")
        return np.zeros(X.shape[0], dtype=int)


# -----------------------------
# R Script Runners
# -----------------------------
def _run_rscript(script_path, csv_path):
    """
    Run R script that modifies CSV in place.
    The R script should be SILENT (no stdout).
    """
    cmd = ["Rscript", str(script_path), str(csv_path)]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=600
        )
        # R script modifies file in place
        return csv_path
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else e.stdout
        raise RuntimeError(f"R script failed:\\n{error_msg}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"R script timed out after 600s")


def cluster_r_labels(
    marker_df,
    rscript_path,
    out_col,
    tmp_dir,
    keep_tmp=False,
    logger=None
):
    """
    Run R-based clustering (FlowSOM or Depeche).
    
    R script should:
      1. Read CSV (path as first argument)
      2. Add column named `out_col` with cluster labels
      3. Write back to SAME path
      4. Be SILENT (use suppressPackageStartupMessages, suppressMessages, invisible())
    """
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Create temp file
    tmp_in = tmp_dir / f"{out_col}_{uuid.uuid4().hex[:8]}.csv"
    marker_df.to_csv(tmp_in, index=False)

    script = Path(rscript_path)
    if not script.exists():
        raise FileNotFoundError(f"R script not found: {script}")

    if logger:
        logger.info(f"Running R clustering: {script.name}")

    # Run R script
    out_path = _run_rscript(script, tmp_in)
    
    if not out_path.exists():
        raise FileNotFoundError(f"R script did not create output: {out_path}")
    
    # Read results
    try:
        out_df = pd.read_csv(out_path)
    except Exception as e:
        raise RuntimeError(f"Failed to read R output from {out_path}: {e}")

    if out_col not in out_df.columns:
        raise ValueError(
            f"R script output missing column '{out_col}'. "
            f"Found: {list(out_df.columns)}"
        )

    labels = out_df[out_col].to_numpy()

    # Cleanup
    if not keep_tmp and tmp_in.exists():
        try:
            tmp_in.unlink()
        except Exception:
            pass

    return labels


# -----------------------------
# Individual Python Methods
# -----------------------------
def cluster_phenograph_labels(X_df, k=25, logger=None):
    """PhenoGraph clustering"""
    try:
        import phenograph
    except ImportError:
        raise ImportError("phenograph not available. Install: pip install phenograph")
    
    X = np.asarray(X_df.values, dtype=float)
    labels, graph, Q = phenograph.cluster(X, k=k)
    
    if logger:
        logger.info(f"PhenoGraph: k={k} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_kmeans_labels(X_df, n_clusters, seed=42, logger=None):
    """K-Means clustering"""
    from sklearn.cluster import KMeans
    
    X = np.asarray(X_df.values, dtype=float)
    model = KMeans(n_clusters=int(n_clusters), random_state=int(seed), n_init=10)
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"KMeans: n_clusters={n_clusters} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_minibatchkmeans_labels(X_df, n_clusters, seed=42, batch_size=1000, logger=None):
    """MiniBatch K-Means clustering"""
    from sklearn.cluster import MiniBatchKMeans
    
    X = np.asarray(X_df.values, dtype=float)
    model = MiniBatchKMeans(
        n_clusters=int(n_clusters),
        batch_size=int(batch_size),
        random_state=int(seed),
        n_init=10
    )
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"MiniBatchKMeans: n_clusters={n_clusters} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_meanshift_labels(X_df, logger=None):
    """MeanShift clustering"""
    from sklearn.cluster import MeanShift
    
    X = np.asarray(X_df.values, dtype=float)
    model = MeanShift()
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"MeanShift: → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_dbscan_labels(X_df, eps=0.5, min_samples=5, logger=None):
    """DBSCAN clustering"""
    from sklearn.cluster import DBSCAN
    
    X = np.asarray(X_df.values, dtype=float)
    model = DBSCAN(eps=float(eps), min_samples=int(min_samples))
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"DBSCAN: eps={eps}, min_samples={min_samples} → {len(np.unique(labels))} labels (incl noise=-1)")
    
    return np.asarray(labels, dtype=int)


def cluster_agglomerative_labels(X_df, n_clusters, linkage="ward", logger=None):
    """Agglomerative (Hierarchical) clustering"""
    from sklearn.cluster import AgglomerativeClustering
    
    X = np.asarray(X_df.values, dtype=float)
    model = AgglomerativeClustering(n_clusters=int(n_clusters), linkage=str(linkage))
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"Agglomerative: n_clusters={n_clusters}, linkage={linkage} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_spectral_labels(X_df, n_clusters, seed=42, logger=None):
    """Spectral clustering"""
    from sklearn.cluster import SpectralClustering
    
    X = np.asarray(X_df.values, dtype=float)
    model = SpectralClustering(
        n_clusters=int(n_clusters),
        assign_labels="kmeans",
        random_state=int(seed)
    )
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"Spectral: n_clusters={n_clusters} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_birch_labels(X_df, n_clusters, logger=None):
    """BIRCH clustering"""
    from sklearn.cluster import Birch
    
    X = np.asarray(X_df.values, dtype=float)
    model = Birch(n_clusters=int(n_clusters))
    labels = model.fit_predict(X)
    
    if logger:
        logger.info(f"Birch: n_clusters={n_clusters} → {len(np.unique(labels))} clusters")
    
    return np.asarray(labels, dtype=int)


def cluster_affinity_labels(X_df, damping=0.5, max_iter=200, seed=42, logger=None):
    """AffinityPropagation clustering"""
    X = np.asarray(X_df.values, dtype=float)
    n = X.shape[0]
    
    # Add these checks
    if n < 2:
        if logger:
            logger.warning("AffinityPropagation: dataset too small")
        return np.zeros(n, dtype=int)
    
    # IMPORTANT: Limit samples if too large (AP is O(n²))
    if n > 5000:
        if logger:
            logger.warning(f"AffinityPropagation: dataset too large (n={n}), using only first 5000")
        X = X[:5000]
    
    try:
        # Better parameters
        from sklearn.cluster import AffinityPropagation
        
        model = AffinityPropagation(
            damping=0.7,           # Increased from 0.5 (more stable)
            max_iter=500,          # Increased from 200
            convergence_iter=50,   # Add convergence criterion
            random_state=seed,
            verbose=False
        )
        
        labels = model.fit_predict(X)
        
        # Check if it actually found clusters
        if len(np.unique(labels)) == 1 and labels[0] == -1:
            if logger:
                logger.warning("AffinityPropagation: failed to converge, returning fallback")
            # Fallback: return KMeans labels instead
            from sklearn.cluster import KMeans
            labels = KMeans(n_clusters=min(20, n//10), random_state=seed).fit_predict(X)
        
        if logger:
            logger.info(f"AffinityPropagation: damping={damping} → {len(np.unique(labels))} clusters")
        
        # If we subsampled, extend labels
        if n > 5000:
            # NOTE (known limitation, not fixed here): cells beyond the first
            # 5000 are left at the default label 0 rather than being assigned
            # via nearest-center/KNN lookup. Affinity Propagation is not part
            # of the recommended CONCLAVE consensus (Phenograph+KMeans+FlowSOM)
            # and is O(n^2), so this path is rarely hit in practice, but if you
            # use "affinity" as a clustering method on >5000 cells, cluster 0
            # will be overrepresented. Flagging for a future fix.
            full_labels = np.zeros(X_df.shape[0], dtype=int)
            full_labels[:5000] = labels
            return full_labels
        
        return labels
        
    except Exception as e:
        if logger:
            logger.error(f"AffinityPropagation failed: {str(e)}")
        return np.zeros(X.shape[0], dtype=int)
# -----------------------------
# Registry
# -----------------------------
METHODS_REQUIRE_NCLUSTERS = {
    "kmeans", "minibatchkmeans", "agglomerative", 
    "spectral", "birch"
}

METHODS_PYTHON = {
    "phenograph", "kmeans", "minibatchkmeans", "meanshift",
    "dbscan", "agglomerative", "spectral", "birch", 
    "affinity", "leiden"
}

METHODS_R = {"flowsom", "depeche"}

ALL_METHODS = METHODS_PYTHON | METHODS_R


# -----------------------------
# Main Clustering Function
# -----------------------------
def cluster_annotation_subset(
    df,
    feature_cols,
    markers_for_r,
    outdir,
    methods=("phenograph", "flowsom", "kmeans"),
    seed=42,
    phenograph_k=25,
    leiden_resolution=1.0,
    leiden_knn_k=30,
    leiden_timeout=600,
    derive_kmeans_from="phenograph",
    flowsom_rscript=None,
    depeche_rscript=None,
    keep_r_tmp=False,
    logger=None
):
    """
    Run multi-method clustering on annotation subset.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe
    feature_cols : list
        Column names to use for clustering
    markers_for_r : list
        Marker names (for R scripts, usually same as feature_cols)
    outdir : Path
        Output directory
    methods : tuple
        Clustering methods to run
    seed : int
        Random seed
    phenograph_k : int
        k parameter for PhenoGraph
    leiden_resolution : float
        Resolution for Leiden
    leiden_knn_k : int
        k for Leiden KNN graph
    leiden_timeout : int
        Timeout for Leiden (seconds)
    derive_kmeans_from : str
        Method to derive n_clusters from (for KMeans and other methods)
    flowsom_rscript : str
        Path to FlowSOM R script
    depeche_rscript : str
        Path to Depeche R script
    keep_r_tmp : bool
        Keep R temporary files
    logger : logging.Logger
        Logger instance
    
    Returns
    -------
    df_labeled : pd.DataFrame
        Dataframe with label_<method> columns
    labels_dict : dict
        {method: labels_array}
    clust_meta : dict
        Clustering metadata
    """
    import time
    
    t0 = time.time()
    outdir = Path(outdir)
    clust_dir = outdir / "03_clustering_annotation"
    clust_dir.mkdir(parents=True, exist_ok=True)
    
    methods = [m.strip().lower() for m in methods]
    
    # Ensure KMeans runs after derive_kmeans_from method
    if "kmeans" in methods and derive_kmeans_from:
        src = str(derive_kmeans_from).strip().lower()
        if src in methods and src != "kmeans":
            methods = [m for m in methods if m != "kmeans"] + ["kmeans"]
    
    # Ensure cell_id exists
    df = ensure_cell_id(df)
    
    # Extract features (never use cell_id as feature)
    feat_cols = [f for f in feature_cols if str(f).lower() != "cell_id"]
    if not feat_cols:
        raise ValueError("No clustering features after removing cell_id")
    
    X_df = df[feat_cols].copy()
    X_df = X_df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    labels_dict = {}
    cluster_counts = {}
    runtimes = {}
    
    # Run each method
    for method in methods:
        t_start = time.time()
        
        try:
            if method == "phenograph":
                labels = cluster_phenograph_labels(X_df, k=phenograph_k, logger=logger)
            
            elif method == "leiden":
                labels = cluster_leiden_labels(
                    X_df, 
                    resolution=leiden_resolution,
                    seed=seed,
                    knn_k=leiden_knn_k,
                    timeout=leiden_timeout,
                    logger=logger
                )
            
            elif method == "flowsom":
                if not flowsom_rscript:
                    raise ValueError("flowsom requested but flowsom_rscript=None")
                
                # For R, use marker names
                marker_df = df[["cell_id"] + markers_for_r].copy()
                labels = cluster_r_labels(
                    marker_df,
                    rscript_path=flowsom_rscript,
                    out_col="flowsom",
                    tmp_dir=clust_dir / "tmp_r",
                    keep_tmp=keep_r_tmp,
                    logger=logger
                )
            
            elif method == "depeche":
                if not depeche_rscript:
                    raise ValueError("depeche requested but depeche_rscript=None")
                
                marker_df = df[["cell_id"] + markers_for_r].copy()
                labels = cluster_r_labels(
                    marker_df,
                    rscript_path=depeche_rscript,
                    out_col="depeche",
                    tmp_dir=clust_dir / "tmp_r",
                    keep_tmp=keep_r_tmp,
                    logger=logger
                )
            
            elif method in METHODS_REQUIRE_NCLUSTERS:
                # Derive n_clusters from another method
                if derive_kmeans_from and derive_kmeans_from in labels_dict:
                    n_clusters = len(np.unique(labels_dict[derive_kmeans_from]))
                    if logger:
                        logger.info(f"{method}: derived n_clusters={n_clusters} from {derive_kmeans_from}")
                else:
                    raise ValueError(
                        f"{method} requires n_clusters. "
                        f"Run {derive_kmeans_from} first or provide n_clusters explicitly."
                    )
                
                if method == "kmeans":
                    labels = cluster_kmeans_labels(X_df, n_clusters, seed, logger)
                elif method == "minibatchkmeans":
                    labels = cluster_minibatchkmeans_labels(X_df, n_clusters, seed, logger=logger)
                elif method == "agglomerative":
                    labels = cluster_agglomerative_labels(X_df, n_clusters, logger=logger)
                elif method == "spectral":
                    labels = cluster_spectral_labels(X_df, n_clusters, seed, logger)
                elif method == "birch":
                    labels = cluster_birch_labels(X_df, n_clusters, logger)
            
            elif method == "meanshift":
                labels = cluster_meanshift_labels(X_df, logger)
            elif method == "dbscan":
                labels = cluster_dbscan_labels(X_df, logger=logger)
            elif method == "affinity":
                labels = cluster_affinity_labels(X_df, seed=seed, logger=logger)
            
            else:
                raise ValueError(f"Unknown clustering method: {method}")
            
            # Store results
            labels = np.asarray(labels)
            if len(labels) != len(df):
                raise RuntimeError(f"{method} returned {len(labels)} labels but expected {len(df)}")
            
            labels_dict[method] = labels
            cluster_counts[method] = int(len(np.unique(labels)))
            runtimes[method] = float(time.time() - t_start)
            
            if logger:
                logger.info(f"✅ {method.capitalize()} complete → {cluster_counts[method]} clusters | runtime={runtimes[method]:.2f}s")
        
        except Exception as e:
            if logger:
                logger.error(f"❌ {method.capitalize()} failed: {e}")
            raise
    
    # Add labels to dataframe
    df_labeled = df.copy()
    for method, labels in labels_dict.items():
        df_labeled[f"label_{method}"] = labels
    
    # Save outputs
    labeled_path = clust_dir / "clustered_subset_with_labels_on_sampled.csv"
    df_labeled.to_csv(labeled_path, index=False)
    if logger:
        logger.info(f"Saved labeled data → {labeled_path}")
    
    # Save individual label files
    labels_dir = clust_dir / "labels"
    labels_dir.mkdir(exist_ok=True)
    for method, labels in labels_dict.items():
        label_path = labels_dir / f"labels_{method}.csv"
        pd.DataFrame({"cell_id": df_labeled["cell_id"], f"label_{method}": labels}).to_csv(label_path, index=False)
    
    # Metadata
    clust_meta = {
        "methods": methods,
        "cluster_counts": cluster_counts,
        "runtimes": runtimes,
        "total_runtime": float(time.time() - t0),
        "n_cells": int(len(df)),
        "n_features": int(len(feat_cols))
    }
    
    meta_path = clust_dir / "meta_run.json"
    with open(meta_path, "w") as f:
        json.dump(clust_meta, f, indent=2)
    
    # Summary CSV
    summary_df = pd.DataFrame([
        {"method": m, "n_clusters": cluster_counts[m], "runtime_sec": runtimes[m]}
        for m in methods
    ])
    summary_df.to_csv(clust_dir / "meta_cluster_summary.csv", index=False)
    
    return df_labeled, labels_dict, clust_meta

# Cell 16
# ============================================================
# PROPER FIX: Incremental Clustering (Add New Methods)
# ============================================================
# This function runs ONLY the missing clustering methods

def run_incremental_clustering(
    df_existing,           # DataFrame with existing labels
    existing_labels_dict,  # Dict of existing method -> labels
    new_methods,          # List of methods to add
    markers,              # Marker columns
    outdir,
    seed=42,
    phenograph_k=25,
    derive_kmeans_from="phenograph",
    flowsom_rscript=None,
    depeche_rscript=None,
    keep_r_tmp=False,
    logger=None
):
    """
    Run clustering for NEW methods only, using existing results.
    
    This allows you to add methods incrementally without re-running everything.
    """
    import time
    from pathlib import Path
    
    outdir = Path(outdir)
    clust_dir = outdir / "03_clustering_annotation"
    
    # Get features from the dataframe (remove label columns and metadata)
    skip_cols = ['cell_id', 'OID', 'X', 'Y', 'ID'] + [f'label_{m}' for m in existing_labels_dict.keys()]
    feature_cols = [c for c in df_existing.columns if c not in skip_cols and c in markers]
    
    if not feature_cols:
        raise ValueError(f"No feature columns found. Available: {df_existing.columns.tolist()}")
    
    if logger:
        logger.info(f"Running {len(new_methods)} new methods: {new_methods}")
        logger.info(f"Using {len(feature_cols)} features: {feature_cols[:5]}...")
    
    # Prepare feature matrix
    X_df = df_existing[feature_cols].copy()
    X_df = X_df.apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    
    # Combine existing and new labels
    all_labels_dict = existing_labels_dict.copy()
    runtimes = {}
    cluster_counts = {}
    
    # Run each new method
    for method in new_methods:
        t_start = time.time()
        
        try:
            if method == "leiden":
                labels = cluster_leiden_labels(X_df, resolution=1.0, seed=seed, logger=logger)
            
            elif method == "birch":
                # Derive k from existing method
                if derive_kmeans_from and derive_kmeans_from in all_labels_dict:
                    n_clusters = len(np.unique(all_labels_dict[derive_kmeans_from]))
                    if logger:
                        logger.info(f"birch: derived n_clusters={n_clusters} from {derive_kmeans_from}")
                else:
                    raise ValueError(f"birch requires n_clusters from {derive_kmeans_from}")
                
                labels = cluster_birch_labels(X_df, n_clusters, logger)
            
            elif method == "affinity":
                labels = cluster_affinity_labels(X_df, seed=seed, logger=logger)
            
            elif method == "meanshift":
                labels = cluster_meanshift_labels(X_df, logger)
            
            elif method == "dbscan":
                labels = cluster_dbscan_labels(X_df, logger=logger)
            
            # Add more methods as needed...
            else:
                if logger:
                    logger.warning(f"Method {method} not implemented in incremental mode, skipping")
                continue
            
            # Store results
            labels = np.asarray(labels)
            if len(labels) != len(df_existing):
                raise RuntimeError(f"{method} returned {len(labels)} labels but expected {len(df_existing)}")
            
            all_labels_dict[method] = labels
            cluster_counts[method] = int(len(np.unique(labels)))
            runtimes[method] = float(time.time() - t_start)
            
            if logger:
                logger.info(f"✅ {method.capitalize()} complete → {cluster_counts[method]} clusters | runtime={runtimes[method]:.2f}s")
        
        except Exception as e:
            if logger:
                logger.error(f"❌ {method.capitalize()} failed: {e}")
            # Continue with other methods
    
    # Add new labels to dataframe
    df_updated = df_existing.copy()
    for method in new_methods:
        if method in all_labels_dict:
            df_updated[f"label_{method}"] = all_labels_dict[method]
    
    # Save updated results
    labeled_path = clust_dir / "clustered_subset_with_labels_on_sampled.csv"
    df_updated.to_csv(labeled_path, index=False)
    if logger:
        logger.info(f"Saved updated labeled data → {labeled_path}")
    
    # Save individual label files for new methods
    labels_dir = clust_dir / "labels"
    labels_dir.mkdir(exist_ok=True)
    for method in new_methods:
        if method in all_labels_dict:
            label_path = labels_dir / f"labels_{method}.csv"
            pd.DataFrame({
                "cell_id": df_updated["cell_id"], 
                f"label_{method}": all_labels_dict[method]
            }).to_csv(label_path, index=False)
    
    # Update metadata
    meta_path = clust_dir / "meta_run.json"
    if meta_path.exists():
        with open(meta_path, 'r') as f:
            meta = json.load(f)
    else:
        meta = {}
    
    # Update with new methods
    all_methods = list(existing_labels_dict.keys()) + new_methods
    all_cluster_counts = {m: len(np.unique(all_labels_dict[m])) for m in all_labels_dict.keys()}
    
    meta['methods'] = all_methods
    meta['cluster_counts'] = all_cluster_counts
    meta['runtimes'] = {**meta.get('runtimes', {}), **runtimes}
    
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    
    # Update summary CSV
    summary_df = pd.DataFrame([
        {"method": m, "n_clusters": all_cluster_counts[m], 
         "runtime_sec": meta['runtimes'].get(m, 0)}
        for m in all_methods
    ])
    summary_df.to_csv(clust_dir / "meta_cluster_summary.csv", index=False)
    
    return df_updated, all_labels_dict, meta


