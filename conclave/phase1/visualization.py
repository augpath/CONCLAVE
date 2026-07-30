"""CONCLAVE Phase 1 - Visualization"""
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns


# Cell 10
# =========================
# 7) Dimensionality Reduction (Optional)
# =========================
def run_dr(
    df: pd.DataFrame,
    markers: list,
    method=None,
    n_components=15,
    random_state=42,
    umap_params=None,
    pacmap_params=None,
    tsne_params=None,
    logger=None
):
    """
    Apply dimensionality reduction.
    
    Methods:
      - None: No DR (use marker space directly)
      - pca: Principal Component Analysis
      - umap: UMAP
      - pacmap: PaCMAP (if installed)
      - tsne: t-SNE, capped at 3 components. sklearn's fast ("barnes_hut")
        solver only supports up to 3 dimensions, and t-SNE embeddings beyond
        that stop being meaningfully interpretable anyway, so any requested
        n_components > 3 is silently reduced to 3 for this method only
        (other DR methods are unaffected and keep using n_components as given).
    
    Returns:
      - X_reduced: ndarray of shape (n_cells, n_components)
      - info: dict with method metadata
    """
    X = (
        df[markers]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .values
    )

    if method is None or str(method).lower() in ("none", "null", "no"):
        if logger:
            logger.info("Dimensionality reduction: None (using marker space)")
        return X, {"dr_method": None, "n_components": len(markers)}

    method_str = str(method).lower()
    n_components = int(n_components)

    # PCA
    if method_str == "pca":
        from sklearn.decomposition import PCA
        
        if logger:
            logger.info(f"Dimensionality reduction: PCA | n_components={n_components}")
        
        model = PCA(n_components=n_components, random_state=int(random_state))
        Xr = model.fit_transform(X)
        
        return Xr, {
            "dr_method": "pca",
            "n_components": n_components,
            "explained_variance_ratio": model.explained_variance_ratio_.tolist()
        }

    # UMAP
    if method_str == "umap":
        import umap as umap_pkg
        
        umap_params = umap_params or {}
        if logger:
            logger.info(f"Dimensionality reduction: UMAP | n_components={n_components}")
        
        model = umap_pkg.UMAP(
            n_components=n_components,
            n_neighbors=int(umap_params.get("n_neighbors", 15)),
            min_dist=float(umap_params.get("min_dist", 0.1)),
            metric=str(umap_params.get("metric", "euclidean")),
            random_state=int(random_state),
            verbose=False
        )
        Xr = model.fit_transform(X)
        
        return Xr, {"dr_method": "umap", "n_components": n_components, **umap_params}

    # PaCMAP
    if method_str == "pacmap":
        try:
            import pacmap
        except ImportError:
            raise ImportError("PaCMAP not available. Install with: pip install pacmap")
        
        pacmap_params = pacmap_params or {}
        if logger:
            logger.info(f"Dimensionality reduction: PaCMAP | n_components={n_components}")
        
        model = pacmap.PaCMAP(
            n_components=n_components,
            n_neighbors=int(pacmap_params.get("n_neighbors", 10)),
            MN_ratio=float(pacmap_params.get("MN_ratio", 0.5)),
            FP_ratio=float(pacmap_params.get("FP_ratio", 2.0)),
            random_state=int(random_state),
        )
        Xr = model.fit_transform(X)
        
        return Xr, {"dr_method": "pacmap", "n_components": n_components, **pacmap_params}

    # t-SNE
    if method_str in ("tsne", "t-sne"):
        from sklearn.manifold import TSNE

        tsne_params = tsne_params or {}

        tsne_n_components = n_components
        if tsne_n_components > 3:
            if logger:
                logger.warning(
                    f"Dimensionality reduction: t-SNE requested with "
                    f"n_components={n_components}, but t-SNE is capped at 3 "
                    f"(sklearn's fast solver doesn't support more, and the "
                    f"CONCLAVE manuscript restricts t-SNE to 3D). Using 3."
                )
            tsne_n_components = 3

        if logger:
            logger.info(f"Dimensionality reduction: t-SNE | n_components={tsne_n_components}")

        model = TSNE(
            n_components=tsne_n_components,
            perplexity=float(tsne_params.get("perplexity", 30.0)),
            learning_rate=tsne_params.get("learning_rate", "auto"),
            init=tsne_params.get("init", "pca"),
            method="barnes_hut" if tsne_n_components <= 3 else "exact",
            random_state=int(random_state),
        )
        Xr = model.fit_transform(X)

        return Xr, {
            "dr_method": "tsne",
            "n_components": tsne_n_components,
            "requested_n_components": n_components,
            **tsne_params,
        }

    raise ValueError(
        f"Unknown DR method: '{method}'. "
        f"Choose from: None, pca, umap, pacmap, tsne"
    )
# Cell 12

# =========================
# 10) Cluster Visualization: Top-N Markers
# =========================

def make_cluster_topN_long(df, markers, label_col, top_n=15):
    """
    Create long-format table of top N markers per cluster.
    
    Returns cluster_id, rank_in_cluster, marker, mean_value
    """
    top_n = int(top_n)
    
    # Get cluster sizes
    sizes_df = (
        df.groupby(label_col)
        .size()
        .rename("n_cells")
        .reset_index()
        .rename(columns={label_col: "cluster_id"})
    )
    
    # Compute mean expression per cluster
    means_wide = df.groupby(label_col)[markers].mean()
    means_wide.index.name = "cluster_id"
    
    # Extract top N markers per cluster
    rows = []
    for cluster_id, row in means_wide.iterrows():
        sorted_markers = row.sort_values(ascending=False)
        top_markers = sorted_markers.head(top_n)
        
        for rank, (marker, val) in enumerate(top_markers.items(), start=1):
            rows.append({
                "cluster_id": cluster_id,
                "rank_in_cluster": int(rank),
                "marker": str(marker),
                "mean_value": float(val),
            })
    
    long_df = pd.DataFrame(rows)
    return long_df, sizes_df


def make_cluster_topN_wide(long_df, sizes_df, top_n=15):
    """
    Convert long format to wide format for easy viewing.
    """
    top_n = int(top_n)
    
    # Sort clusters by size (largest first)
    cluster_order = sizes_df.sort_values("n_cells", ascending=False)["cluster_id"].tolist()
    size_map = sizes_df.set_index("cluster_id")["n_cells"].to_dict()
    
    # Build lookup
    lookup = {
        (r["cluster_id"], int(r["rank_in_cluster"])): (r["marker"], float(r["mean_value"]))
        for _, r in long_df.iterrows()
    }
    
    # Build wide table
    rows = []
    for cluster_id in cluster_order:
        row = {
            "cluster_id": cluster_id,
            "n_cells": int(size_map.get(cluster_id, 0))
        }
        
        for rank in range(1, top_n + 1):
            marker, mean_val = lookup.get((cluster_id, rank), ("", np.nan))
            row[f"rank_{rank}_marker"] = marker
            row[f"rank_{rank}_mean"] = mean_val
        
        rows.append(row)
    
    return pd.DataFrame(rows)


def save_annotation_template_from_sizes(sizes_df, outpath):
    """
    Create a CSV template for manual annotation.
    """
    outpath = Path(outpath)
    outpath.parent.mkdir(parents=True, exist_ok=True)
    
    template = sizes_df.copy()
    template.sort_values(by="n_cells", ascending=False, inplace=True)
    template["annotation"] = ""
    template.to_csv(outpath, index=False)
    
    return template


def plot_ranked_tile_topN(
    long_df,
    sizes_df,
    top_n,
    title,
    out_png,
    show=True,
    fontsize=7
):
    """
    Create heatmap visualization of top N markers per cluster.
    """
    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    top_n = int(top_n)
    
    # Order clusters by size
    cluster_order = sizes_df.sort_values("n_cells", ascending=False)["cluster_id"].tolist()
    cluster_to_idx = {c: i for i, c in enumerate(cluster_order)}
    
    # Initialize matrices
    n_clusters = len(cluster_order)
    val_matrix = np.full((n_clusters, top_n), np.nan, dtype=float)
    txt_matrix = np.full((n_clusters, top_n), "", dtype=object)
    
    # Fill matrices
    for _, row in long_df.iterrows():
        cluster_id = row["cluster_id"]
        rank = int(row["rank_in_cluster"])
        
        if cluster_id not in cluster_to_idx or rank < 1 or rank > top_n:
            continue
        
        i = cluster_to_idx[cluster_id]
        j = rank - 1
        
        val_matrix[i, j] = float(row["mean_value"])
        txt_matrix[i, j] = str(row["marker"])
    
    # Create figure
    fig_w = max(10, 0.75 * top_n)
    fig_h = max(6, 0.30 * n_clusters)
    
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(val_matrix, aspect="auto", cmap="viridis")
    
    # Labels
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_xlabel("Marker Rank (1 = highest mean in cluster)", fontsize=10)
    ax.set_ylabel("Cluster ID (sorted by size)", fontsize=10)
    
    # Ticks
    ax.set_xticks(np.arange(top_n))
    ax.set_xticklabels([str(i) for i in range(1, top_n + 1)])
    ax.set_yticks(np.arange(n_clusters))
    ax.set_yticklabels([str(c) for c in cluster_order])
    
    # Add marker names as text
    for i in range(n_clusters):
        for j in range(top_n):
            marker_name = txt_matrix[i, j]
            if marker_name:
                val = val_matrix[i, j]
                if not np.isnan(val):
                    text_color = 'white' if val > np.nanmean(val_matrix) else 'black'
                else:
                    text_color = 'black'
                
                ax.text(
                    j, i, marker_name,
                    ha="center", va="center",
                    fontsize=fontsize,
                    color=text_color,
                    fontweight='bold'
                )
    
    # Colorbar
    plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="Mean Expression")
    
    plt.tight_layout()
    fig.savefig(out_png, dpi=200, bbox_inches='tight')
    
    if show:
        plt.show()
    
    plt.close(fig)
    
    return out_png


def export_cluster_topN_per_cluster(
    df_labeled,
    markers,
    methods,
    outdir,
    top_n_markers=15,
    logger=None,
    show_heatmaps=True
):
    """
    Export top-N marker visualizations for each clustering method.
    """
    outdir = Path(outdir)
    heatmap_dir = outdir / "04_cluster_heatmaps"
    heatmap_dir.mkdir(parents=True, exist_ok=True)
    
    top_n = int(top_n_markers)
    methods = [m.strip().lower() for m in methods]
    outputs = {}
    
    for method in methods:
        label_col = f"label_{method}"
        
        if label_col not in df_labeled.columns:
            if logger:
                logger.warning(f"⚠️  Skipping {method}: missing column '{label_col}'")
            continue
        
        if logger:
            logger.info(f"Generating visualizations for: {method}")
        
        # Generate data
        long_df, sizes_df = make_cluster_topN_long(
            df_labeled, markers, label_col, top_n=top_n
        )
        wide_df = make_cluster_topN_wide(long_df, sizes_df, top_n=top_n)
        
        # Output paths
        long_csv = heatmap_dir / f"cluster_topN_long_{method}.csv"
        wide_csv = heatmap_dir / f"cluster_topN_wide_{method}.csv"
        sizes_csv = heatmap_dir / f"cluster_sizes_{method}.csv"
        template_csv = heatmap_dir / f"annotation_template_{method}.csv"
        png_path = heatmap_dir / f"heatmap_topN_ranked_{method}.png"
        
        # Save CSVs
        long_df.to_csv(long_csv, index=False)
        wide_df.to_csv(wide_csv, index=False)
        sizes_df.to_csv(sizes_csv, index=False)
        save_annotation_template_from_sizes(sizes_df, template_csv)
        
        # Create heatmap
        plot_ranked_tile_topN(
            long_df=long_df,
            sizes_df=sizes_df,
            top_n=top_n,
            title=f"Top-{top_n} Expressed Markers per Cluster — {method.upper()}",
            out_png=png_path,
            show=show_heatmaps,
            fontsize=7
        )
        
        if logger:
            logger.info(
                f"  ✅ Saved: {long_csv.name}, {wide_csv.name}, "
                f"{template_csv.name}, {png_path.name}"
            )
        
        outputs[method] = {
            "long_csv": str(long_csv),
            "wide_csv": str(wide_csv),
            "sizes_csv": str(sizes_csv),
            "annotation_template_csv": str(template_csv),
            "heatmap_png": str(png_path),
        }
    
    return outputs
