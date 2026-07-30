"""CONCLAVE Phase 1 - GPU Sampling"""
import numpy as np
import pandas as pd
import gc
from conclave.phase1.utils import ensure_cell_id


# Cell 9
# =========================
# GPU-Accelerated UMAP Sampling with All Three Modes
# =========================

import numpy as np
import gc

def _cuml_gpu_umap(X, n_components=2, n_neighbors=15, min_dist=0.1, random_state=42, logger=None):
    """Pure GPU UMAP using cuML (10-100x faster!)"""
    try:
        import cuml
        import cupy as cp
        
        if logger:
            logger.info(f"🚀 Using cuML GPU UMAP (NVIDIA RAPIDS)")
            logger.info(f"   Processing {X.shape[0]:,} cells × {X.shape[1]} features")
        
        X_gpu = cp.asarray(X, dtype=cp.float32)
        reducer = cuml.UMAP(
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            n_components=n_components,
            random_state=random_state,
            verbose=False
        )
        embedding_gpu = reducer.fit_transform(X_gpu)
        embedding = cp.asnumpy(embedding_gpu)
        
        del X_gpu, embedding_gpu
        gc.collect()
        
        if logger:
            logger.info(f"   ✅ cuML GPU UMAP complete")
        
        return embedding
    except Exception as e:
        if logger:
            logger.warning(f"cuML failed: {str(e)}")
        raise


def _pytorch_gpu_pca(X, n_components=50, logger=None):
    """GPU-accelerated PCA using PyTorch"""
    try:
        import torch
        
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA not available")
        
        if logger:
            logger.info(f"⚡ PyTorch GPU PCA: {X.shape[1]} → {n_components}")
        
        X_tensor = torch.tensor(X, dtype=torch.float32, device='cuda')
        mean = torch.mean(X_tensor, dim=0, keepdim=True)
        X_centered = X_tensor - mean
        
        if X.shape[0] > 100000:
            U, S, Vt = torch.pca_lowrank(X_centered, q=n_components, niter=2)
            X_reduced = torch.matmul(X_centered, Vt.T)
        else:
            cov = torch.matmul(X_centered.T, X_centered) / (X_tensor.shape[0] - 1)
            eigenvalues, eigenvectors = torch.linalg.eigh(cov)
            idx = torch.argsort(eigenvalues, descending=True)[:n_components]
            eigenvectors = eigenvectors[:, idx]
            X_reduced = torch.matmul(X_centered, eigenvectors)
        
        X_reduced_np = X_reduced.cpu().numpy()
        
        del X_tensor, X_centered, mean
        torch.cuda.empty_cache()
        gc.collect()
        
        if logger:
            logger.info(f"   ✅ GPU PCA complete")
        
        return X_reduced_np
    except Exception as e:
        if logger:
            logger.warning(f"GPU PCA failed: {str(e)}")
        raise


def _cpu_pca(X, n_components=50, logger=None):
    """CPU PCA fallback"""
    from sklearn.decomposition import IncrementalPCA
    
    if logger:
        logger.info(f"💻 CPU PCA: {X.shape[1]} → {n_components}")
    
    pca = IncrementalPCA(n_components=n_components, batch_size=10000)
    X_reduced = pca.fit_transform(X)
    
    if logger:
        logger.info(f"   ✅ CPU PCA complete")
    
    return X_reduced


def _cpu_umap(X, n_components=2, n_neighbors=15, min_dist=0.1, random_state=42, logger=None):
    """Standard CPU UMAP"""
    try:
        import umap as umap_pkg
    except ImportError:
        raise ImportError("UMAP not available")
    
    if logger:
        logger.info(f"💻 CPU UMAP: {X.shape[0]:,} cells × {X.shape[1]} features")
    
    model = umap_pkg.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric='euclidean',
        n_components=n_components,
        random_state=random_state,
        verbose=False
    )
    
    embedding = model.fit_transform(X)
    
    if logger:
        logger.info(f"   ✅ CPU UMAP complete")
    
    return embedding


def _safe_umap_embedding(X, n_components=2, random_state=42, umap_params=None,
                         use_gpu=False, gpu_pca_components=50, logger=None):
    """Safe UMAP with GPU acceleration"""
    umap_params = umap_params or {}
    n_neighbors = int(umap_params.get("n_neighbors", 15))
    min_dist = float(umap_params.get("min_dist", 0.1))
    
    if not use_gpu:
        return _cpu_umap(X, n_components, n_neighbors, min_dist, random_state, logger)
    
    # Try cuML
    try:
        if logger:
            logger.info("Attempting cuML GPU UMAP...")
        embedding = _cuml_gpu_umap(X, n_components, n_neighbors, min_dist, random_state, logger)
        if logger:
            logger.info("🚀 Used cuML (10-100x speedup!)")
        return embedding
    except:
        if logger:
            logger.info("cuML not available, trying PyTorch...")
    
    # Try PyTorch GPU PCA
    try:
        if X.shape[1] > gpu_pca_components:
            if logger:
                logger.info("Trying PyTorch GPU PCA...")
            X_reduced = _pytorch_gpu_pca(X, gpu_pca_components, logger)
            embedding = _cpu_umap(X_reduced, n_components, n_neighbors, min_dist, random_state, logger)
            if logger:
                logger.info("⚡ Used PyTorch GPU PCA (3-5x speedup)")
            return embedding
        else:
            return _cpu_umap(X, n_components, n_neighbors, min_dist, random_state, logger)
    except:
        if logger:
            logger.warning("GPU failed, using CPU...")
    
    # CPU fallback
    try:
        if X.shape[1] > gpu_pca_components:
            X_reduced = _cpu_pca(X, gpu_pca_components, logger)
            embedding = _cpu_umap(X_reduced, n_components, n_neighbors, min_dist, random_state, logger)
            if logger:
                logger.info("💻 Used CPU PCA + UMAP")
            return embedding
        else:
            return _cpu_umap(X, n_components, n_neighbors, min_dist, random_state, logger)
    except Exception as e:
        if logger:
            logger.error(f"All failed: {str(e)}")
        raise


def sample_umap_tiles(
    df: pd.DataFrame,
    markers: list,
    sample_size: int = None,
    mode: str = "stratified-notproportional",
    n_tiles_per_axis: int = 4,
    random_state: int = 42,
    umap_params=None,
    use_gpu=False,
    gpu_pca_components=50,
    logger=None,
):
    """
    Sample cells with UMAP-based stratification + GPU acceleration.
    
    Modes:
    - random: Simple random sampling
    - stratified-proportional: Proportional to tile size
    - stratified-notproportional: Equal from each tile
    - none/full: No sampling
    
    GPU: use_gpu=True enables cuML (10-100x) or PyTorch (3-5x) acceleration
    """
    df = ensure_cell_id(df)
    
    if sample_size is None or str(mode).lower() in ("none", "full", "no"):
        if logger:
            logger.info("Sampling: None")
        return df.copy()
    
    sample_size = int(sample_size)
    if sample_size >= len(df):
        if logger:
            logger.info(f"Sampling: Full dataset")
        return df.copy()

    mode = str(mode).lower()
    rng = np.random.default_rng(int(random_state))
    idx = np.arange(len(df))
    
    # Random sampling
    if mode == "random":
        if logger:
            logger.info(f"Sampling: Random | {sample_size:,}/{len(df):,}")
        chosen = rng.choice(idx, size=sample_size, replace=False)
        return df.iloc[chosen].copy()
    
    # Stratified sampling
    elif mode in ("stratified-proportional", "stratified-notproportional",
                  "stratifiedproportional", "stratifiednotproportional"):
        
        X = (
            df[markers]
            .apply(pd.to_numeric, errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .values
        )
        
        if logger:
            if use_gpu:
                logger.info("Computing UMAP with GPU...")
            else:
                logger.info("Computing UMAP...")
        
        emb = _safe_umap_embedding(
            X, 2, random_state, umap_params, use_gpu, gpu_pca_components, logger
        )

        x, y = emb[:, 0], emb[:, 1]
        n = int(n_tiles_per_axis)
        xbins = np.linspace(x.min(), x.max(), n + 1)
        ybins = np.linspace(y.min(), y.max(), n + 1)
        
        xi = np.clip(np.digitize(x, xbins) - 1, 0, n - 1)
        yi = np.clip(np.digitize(y, ybins) - 1, 0, n - 1)
        tile_id = xi * n + yi

        unique_tiles = np.unique(tile_id)
        tiles_with_cells = [t for t in unique_tiles if np.sum(tile_id == t) > 0]
        
        if mode in ("stratified-proportional", "stratifiedproportional"):
            tile_counts = {t: np.sum(tile_id == t) for t in tiles_with_cells}
            total_cells = len(df)
            
            chosen = []
            for t in tiles_with_cells:
                members = idx[tile_id == t]
                n_to_sample = int(sample_size * (tile_counts[t] / total_cells))
                if n_to_sample > 0:
                    n_to_sample = min(n_to_sample, len(members))
                    sampled = rng.choice(members, size=n_to_sample, replace=False)
                    chosen.extend(sampled.tolist())
            
            if len(chosen) < sample_size:
                remaining = np.setdiff1d(idx, np.array(chosen, dtype=int))
                if len(remaining) > 0:
                    extra = min(sample_size - len(chosen), len(remaining))
                    chosen.extend(rng.choice(remaining, size=extra, replace=False).tolist())
            
            chosen = np.array(chosen[:sample_size], dtype=int)
            
            if logger:
                logger.info(f"Sampling: proportional | {len(chosen):,}/{len(df):,} | tiles={n*n}")
        
        else:
            cells_per_tile = max(1, sample_size // len(tiles_with_cells))
            
            chosen = []
            for t in tiles_with_cells:
                members = idx[tile_id == t]
                take = min(cells_per_tile, len(members))
                sampled = rng.choice(members, size=take, replace=False)
                chosen.extend(sampled.tolist())
            
            if len(chosen) < sample_size:
                remaining = np.setdiff1d(idx, np.array(chosen, dtype=int))
                if len(remaining) > 0:
                    extra = min(sample_size - len(chosen), len(remaining))
                    chosen.extend(rng.choice(remaining, size=extra, replace=False).tolist())
            
            chosen = np.array(chosen[:sample_size], dtype=int)
            
            if logger:
                logger.info(f"Sampling: non-proportional | {len(chosen):,}/{len(df):,} | tiles={n*n}")
        
        df_sampled = df.iloc[chosen].copy()
        df_sampled["umap_x"] = x[chosen]
        df_sampled["umap_y"] = y[chosen]
        df_sampled["tile_id"] = tile_id[chosen]
        
        return df_sampled
    
    else:
        raise ValueError(f"Unknown mode: '{mode}'")


