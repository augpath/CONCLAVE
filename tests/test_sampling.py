"""Tests for conclave.phase1.sampling"""
import numpy as np
import pytest

from conclave.phase1.sampling import sample_umap_tiles


def test_no_sampling_when_sample_size_none(small_df, markers):
    out = sample_umap_tiles(small_df, markers, sample_size=None)
    assert len(out) == len(small_df)


def test_no_sampling_when_mode_none(small_df, markers):
    out = sample_umap_tiles(small_df, markers, sample_size=50, mode="none")
    assert len(out) == len(small_df)


def test_sample_size_larger_than_df_returns_full(small_df, markers):
    out = sample_umap_tiles(small_df, markers, sample_size=10_000, mode="random")
    assert len(out) == len(small_df)


def test_random_sampling_returns_requested_size(small_df, markers):
    out = sample_umap_tiles(small_df, markers, sample_size=50, mode="random", random_state=1)
    assert len(out) == 50
    # sampled rows should be a subset of the original cell_ids
    assert set(out["cell_id"]).issubset(set(small_df["cell_id"]))


def test_random_sampling_is_reproducible_with_seed(small_df, markers):
    out1 = sample_umap_tiles(small_df, markers, sample_size=40, mode="random", random_state=7)
    out2 = sample_umap_tiles(small_df, markers, sample_size=40, mode="random", random_state=7)
    assert list(out1["cell_id"]) == list(out2["cell_id"])


@pytest.mark.parametrize("mode", ["stratified-proportional", "stratified-notproportional"])
def test_stratified_modes_return_approximately_requested_size(small_df, markers, mode):
    out = sample_umap_tiles(
        small_df, markers, sample_size=60, mode=mode, n_tiles_per_axis=3, random_state=0
    )
    # stratified sampling can land a handful under/over the target due to
    # per-tile rounding, so allow slack rather than requiring an exact count
    assert abs(len(out) - 60) <= 10
    assert "umap_x" in out.columns and "umap_y" in out.columns and "tile_id" in out.columns


def test_unknown_mode_raises(small_df, markers):
    with pytest.raises(ValueError):
        sample_umap_tiles(small_df, markers, sample_size=10, mode="not-a-real-mode")
