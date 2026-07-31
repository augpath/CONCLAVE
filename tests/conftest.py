"""Shared fixtures for CONCLAVE test suite.

Uses small synthetic marker-expression data (not real patient data) so the
suite runs in seconds. Two synthetic Gaussian blobs are used so clustering
methods have something non-trivial (but fast and deterministic) to find.
"""
import numpy as np
import pandas as pd
import pytest


MARKERS = ["CD3", "CD8", "CD68", "CD20", "Ki67"]


def _make_blob_df(n_per_blob=60, n_blobs=3, n_markers=5, seed=0, n_samples=1):
    """Small synthetic cell x marker matrix with `n_blobs` separable clusters,
    optionally split across `n_samples` sample/slide groups with a per-sample
    additive offset (to exercise sample-aware normalization)."""
    rng = np.random.default_rng(seed)
    markers = MARKERS[:n_markers]

    rows = []
    sample_ids = []
    for b in range(n_blobs):
        center = rng.uniform(-5, 5, size=n_markers)
        block = rng.normal(loc=center, scale=0.5, size=(n_per_blob, n_markers))
        rows.append(block)

    X = np.vstack(rows)
    n = X.shape[0]

    # Assign sample groups with a per-sample additive batch offset
    sample_assignment = np.tile(np.arange(n_samples), int(np.ceil(n / n_samples)))[:n]
    rng.shuffle(sample_assignment)
    for s in range(n_samples):
        offset = s * 3.0  # deliberate batch shift
        X[sample_assignment == s] += offset

    df = pd.DataFrame(X, columns=markers)
    df["cell_id"] = [f"cell_{i}" for i in range(n)]
    df["sample_id"] = [f"sample_{s}" for s in sample_assignment]
    return df, markers


@pytest.fixture
def markers():
    return list(MARKERS)


@pytest.fixture
def small_df():
    """~180 cells, 3 separable blobs, single sample group."""
    df, _ = _make_blob_df(n_per_blob=60, n_blobs=3, seed=0, n_samples=1)
    return df


@pytest.fixture
def multi_sample_df():
    """~180 cells, 3 blobs, split across 2 sample groups with a batch offset."""
    df, _ = _make_blob_df(n_per_blob=60, n_blobs=3, seed=1, n_samples=2)
    return df


@pytest.fixture
def tiny_df():
    """A handful of cells, for edge-case / small-n behavior."""
    df, _ = _make_blob_df(n_per_blob=3, n_blobs=2, seed=2, n_samples=1)
    return df
