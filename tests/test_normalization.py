"""Tests for conclave.phase1.normalization"""
import numpy as np
import pandas as pd
import pytest

from conclave.phase1.normalization import normalize_markers


def test_zscore_normalizes_mean_zero_std_one(small_df, markers):
    out, report = normalize_markers(small_df, markers, method="z-score", clip=None)
    means = out[markers].mean()
    stds = out[markers].std()
    assert np.allclose(means, 0, atol=1e-8)
    assert np.allclose(stds, 1, atol=1e-2)
    assert report["method"] == "z-score"


def test_zscore_clipping_bounds_respected(small_df, markers):
    out, _ = normalize_markers(small_df, markers, method="z-score", clip=2.0)
    assert out[markers].max().max() <= 2.0 + 1e-9
    assert out[markers].min().min() >= -2.0 - 1e-9


def test_lognorm_output_is_finite_and_nonneg(small_df, markers):
    out, _ = normalize_markers(small_df, markers, method="lognorm")
    assert np.isfinite(out[markers].values).all()
    assert (out[markers].values >= 0).all()


def test_minmax_output_in_unit_range(small_df, markers):
    out, _ = normalize_markers(small_df, markers, method="minmax")
    assert out[markers].min().min() >= -1e-9
    assert out[markers].max().max() <= 1 + 1e-9


def test_none_method_returns_raw_values(small_df, markers):
    out, report = normalize_markers(small_df, markers, method=None)
    assert np.allclose(out[markers].values, small_df[markers].values)
    assert report["method"] is None


def test_unknown_method_raises(small_df, markers):
    with pytest.raises(ValueError):
        normalize_markers(small_df, markers, method="not-a-real-method")


def test_sample_cols_missing_column_raises(small_df, markers):
    with pytest.raises(ValueError):
        normalize_markers(small_df, markers, method="z-score", sample_cols=["not_a_column"])


def test_sample_aware_zscore_normalizes_within_each_sample(multi_sample_df, markers):
    """The whole point of sample_cols: each sample group should independently
    end up mean~0/std~1, even though the raw data has a large between-sample
    batch offset baked in (see conftest._make_blob_df)."""
    out, report = normalize_markers(
        multi_sample_df, markers, method="z-score", clip=None, sample_cols=["sample_id"]
    )
    for sample_id, sub in out.groupby(multi_sample_df["sample_id"]):
        assert np.allclose(sub[markers].mean(), 0, atol=1e-8)
    assert report["total_samples"] == multi_sample_df["sample_id"].nunique()


def test_sample_aware_vs_pooled_normalization_differ(multi_sample_df, markers):
    """Sanity check that within-sample normalization actually behaves
    differently from pooling everything together (i.e. it's not a no-op) --
    this is the behavior distinguishing 'per sample' vs 'all cells together'
    normalization."""
    out_grouped, _ = normalize_markers(
        multi_sample_df, markers, method="z-score", clip=None, sample_cols=["sample_id"]
    )
    out_pooled, _ = normalize_markers(
        multi_sample_df, markers, method="z-score", clip=None, sample_cols=None
    )
    assert not np.allclose(out_grouped[markers].values, out_pooled[markers].values)


def test_constant_marker_column_flagged_and_zeroed(small_df, markers):
    df = small_df.copy()
    df["Ki67"] = 7.0  # constant column within the single sample group
    out, report = normalize_markers(df, markers, method="z-score")
    assert np.allclose(out["Ki67"].values, 0.0)
    assert len(report["normalization_issues"]["samples_with_constant_markers"]) == 1
