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


def test_iqr_zscore_output_is_finite_and_roughly_centered(small_df, markers):
    out, report = normalize_markers(small_df, markers, method="iqr-zscore")
    vals = out[markers].values
    assert np.isfinite(vals).all()
    # Winsorization + standardizing on the same (winsorized) data means the
    # mean should land close to 0, though not exactly (fences remove tails
    # asymmetrically in general)
    assert abs(vals.mean()) < 0.5
    assert report["method"] == "iqr-zscore"


def test_iqr_minmax_output_in_unit_range(small_df, markers):
    out, _ = normalize_markers(small_df, markers, method="iqr-minmax")
    assert out[markers].min().min() >= -1e-9
    assert out[markers].max().max() <= 1 + 1e-9


def test_iqr_methods_accept_underscore_and_dash_spelling(small_df, markers):
    out_dash, _ = normalize_markers(small_df, markers, method="iqr-zscore")
    out_underscore, _ = normalize_markers(small_df, markers, method="iqr_zscore")
    assert np.allclose(out_dash[markers].values, out_underscore[markers].values)


def test_iqr_zscore_winsorizes_outliers_before_standardizing(markers):
    """A single extreme outlier shouldn't dominate the scale the way plain
    z-score would -- the Tukey-fence Winsorization should cap its influence
    before standardizing."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(200, len(markers))), columns=markers)
    df.iloc[0] = 1000.0  # extreme outlier row

    out_plain, _ = normalize_markers(df, markers, method="z-score", clip=None)
    out_iqr, _ = normalize_markers(df, markers, method="iqr-zscore")

    # Without Winsorization, the plain z-score of the other 199 (normal)
    # points gets compressed toward 0 because std is inflated by the outlier
    non_outlier_std_plain = out_plain[markers].values[1:].std()
    non_outlier_std_iqr = out_iqr[markers].values[1:].std()
    assert non_outlier_std_iqr > non_outlier_std_plain


def test_iqr_minmax_constant_marker_after_winsorization_is_flagged(small_df, markers):
    df = small_df.copy()
    df["Ki67"] = 7.0  # constant column
    out, report = normalize_markers(df, markers, method="iqr-minmax")
    assert np.allclose(out["Ki67"].values, 0.0)
    assert len(report["normalization_issues"]["samples_with_constant_markers"]) == 1


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
