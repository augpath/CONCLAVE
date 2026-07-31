"""Tests for conclave.phase1.clustering

Covers the clustering methods that run without external R dependencies
(FlowSOM and DepecheR require an external R script + Rscript on PATH and
are intentionally not unit-tested here; see BUILD_AND_PUBLISH_GUIDE.md).
"""
import inspect

import numpy as np
import pytest

from conclave.phase1.clustering import (
    cluster_kmeans_labels,
    cluster_minibatchkmeans_labels,
    cluster_birch_labels,
    cluster_dbscan_labels,
    cluster_agglomerative_labels,
    cluster_affinity_labels,
    cluster_phenograph_labels,
    cluster_leiden_labels,
)


def _n_found_clusters(labels):
    return len(set(labels)) - (1 if -1 in set(labels) else 0)  # exclude DBSCAN noise label


def test_phenograph_default_k_is_25():
    """Regression test: the manuscript's sensitivity sweep landed on k=25
    (was library default of 30) -- this pins the default so it can't
    silently drift back."""
    assert inspect.signature(cluster_phenograph_labels).parameters["k"].default == 25


def test_kmeans_recovers_three_blobs(small_df, markers):
    labels = cluster_kmeans_labels(small_df[markers], n_clusters=3, seed=0)
    assert len(labels) == len(small_df)
    assert _n_found_clusters(labels) == 3


def test_minibatchkmeans_recovers_three_blobs(small_df, markers):
    labels = cluster_minibatchkmeans_labels(small_df[markers], n_clusters=3, seed=0)
    assert _n_found_clusters(labels) == 3


def test_birch_runs_and_returns_labels_per_cell(small_df, markers):
    labels = cluster_birch_labels(small_df[markers], n_clusters=3)
    assert len(labels) == len(small_df)


def test_agglomerative_recovers_three_blobs(small_df, markers):
    labels = cluster_agglomerative_labels(small_df[markers], n_clusters=3)
    assert _n_found_clusters(labels) == 3


def test_dbscan_runs_and_returns_labels_per_cell(small_df, markers):
    labels = cluster_dbscan_labels(small_df[markers], eps=1.5, min_samples=5)
    assert len(labels) == len(small_df)


def test_affinity_propagation_runs_on_small_data(small_df, markers):
    labels = cluster_affinity_labels(small_df[markers], seed=0)
    assert len(labels) == len(small_df)


def test_affinity_propagation_known_limitation_above_5000_cells(markers):
    """Documents the known (not-yet-fixed) behavior: for >5000 cells,
    cluster_affinity_labels subsamples to 5000, clusters those, and leaves
    every cell beyond that at label 0 rather than assigning via
    nearest-center lookup. This test exists so that if/when this gets
    fixed, it fails loudly here instead of silently changing behavior."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(5100, len(markers)))
    import pandas as pd
    df = pd.DataFrame(X, columns=markers)

    labels = cluster_affinity_labels(df, seed=0)
    assert len(labels) == 5100
    # cells beyond the first 5000 are all left at the placeholder label 0
    assert np.all(labels[5000:] == 0)


def test_phenograph_runs_on_small_data(small_df, markers):
    labels = cluster_phenograph_labels(small_df[markers], k=10)
    assert len(labels) == len(small_df)


def test_leiden_runs_on_small_data(small_df, markers):
    labels = cluster_leiden_labels(small_df[markers], knn_k=10)
    assert len(labels) == len(small_df)


def test_leiden_tiny_dataset_does_not_crash(tiny_df, markers):
    """n<2 edge case should return zeros, not raise."""
    labels = cluster_leiden_labels(tiny_df[markers].iloc[:1], knn_k=10)
    assert len(labels) == 1
