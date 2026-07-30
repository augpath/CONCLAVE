"""CONCLAVE Phase 2 - GPU-Accelerated 3D UMAP"""

import time
import gc
import umap


def fit_umap_3d_gpu(X, n_neighbors=15, min_dist=0.1, seed=42):
    """Fit 3D UMAP using cuML (GPU)"""
    print("  🚀 GPU UMAP (cuML)...")
    t0 = time.time()
    
    try:
        import cuml
        import cupy as cp
    except ImportError:
        raise ImportError("cuML/CuPy not available for GPU UMAP")
    
    # CRITICAL: dtype=cp.float32 to avoid FP8 issues
    X_gpu = cp.asarray(X, dtype=cp.float32)
    
    reducer = cuml.UMAP(
        n_neighbors=n_neighbors,
        n_components=3,
        min_dist=min_dist,
        random_state=seed,
        verbose=False
    )
    
    embedding_gpu = reducer.fit_transform(X_gpu)
    embedding = cp.asnumpy(embedding_gpu)
    
    # Cleanup
    del X_gpu, embedding_gpu
    gc.collect()
    
    print(f"  ✅ Complete in {time.time()-t0:.1f}s")
    return reducer, embedding


def fit_umap_3d_cpu(X, n_neighbors=15, min_dist=0.1, seed=42):
    """Fit 3D UMAP using CPU"""
    print("  💻 CPU UMAP...")
    t0 = time.time()
    
    model = umap.UMAP(
        n_neighbors=n_neighbors,
        n_components=3,
        min_dist=min_dist,
        random_state=seed,
        verbose=False
    )
    embedding = model.fit_transform(X)
    
    print(f"  ✅ Complete in {time.time()-t0:.1f}s")
    return model, embedding


def fit_umap_3d(X, use_gpu=True, n_neighbors=15, min_dist=0.1, seed=42):
    """Fit 3D UMAP with GPU fallback"""
    if use_gpu:
        try:
            return fit_umap_3d_gpu(X, n_neighbors, min_dist, seed)
        except Exception as e:
            print(f"  ⚠️  GPU failed: {str(e)[:100]}")
            print("  Falling back to CPU...")
            return fit_umap_3d_cpu(X, n_neighbors, min_dist, seed)
    else:
        return fit_umap_3d_cpu(X, n_neighbors, min_dist, seed)


