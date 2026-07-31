"""Tests for conclave.phase1.visualization.run_dr"""
import numpy as np
import pytest

from conclave.phase1.visualization import run_dr


def test_dr_none_returns_raw_marker_matrix(small_df, markers):
    Xr, info = run_dr(small_df, markers, method=None)
    assert Xr.shape == (len(small_df), len(markers))
    assert info["dr_method"] is None


def test_dr_pca_reduces_dimensions(small_df, markers):
    Xr, info = run_dr(small_df, markers, method="pca", n_components=2)
    assert Xr.shape == (len(small_df), 2)
    assert info["dr_method"] == "pca"


def test_dr_umap_reduces_dimensions(small_df, markers):
    Xr, info = run_dr(small_df, markers, method="umap", n_components=3, random_state=0)
    assert Xr.shape == (len(small_df), 3)


def test_dr_tsne_default_components(small_df, markers):
    Xr, info = run_dr(small_df, markers, method="tsne", n_components=2, random_state=0)
    assert Xr.shape == (len(small_df), 2)
    assert info["dr_method"] == "tsne"
    assert info["n_components"] == 2


def test_dr_tsne_caps_at_three_components(small_df, markers):
    """The manuscript restricts t-SNE to 3D (and sklearn's fast solver can't
    go higher anyway) -- requesting more should silently clip to 3, not
    error, and should report the original request for traceability."""
    Xr, info = run_dr(small_df, markers, method="tsne", n_components=15, random_state=0)
    assert Xr.shape == (len(small_df), 3)
    assert info["n_components"] == 3
    assert info["requested_n_components"] == 15


def test_dr_unknown_method_raises(small_df, markers):
    with pytest.raises(ValueError):
        run_dr(small_df, markers, method="not-a-real-method")
