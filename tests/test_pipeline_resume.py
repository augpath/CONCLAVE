"""Regression test for a real bug found via user testing: resuming a Phase 1
run (after an earlier crash mid-clustering) with dr_method=None used to fail
with "No clustering features after removing cell_id" -- see test_dr.py's
test_dr_none_method_survives_csv_roundtrip_as_nan for the root-cause
mechanism (None -> NaN on CSV round-trip). This test exercises the actual
pipeline end-to-end rather than just the isolated mechanism.
"""
import pytest

from conclave.phase1 import run_annotation_pipeline_with_resume


def test_resume_after_crash_with_dr_method_none(small_df, markers, tmp_path):
    outdir = tmp_path / "phase1_output"

    # First call: request a clustering method that's guaranteed to fail (no
    # R script given), so the run crashes AFTER normalization/sampling/DR
    # have already succeeded and been checkpointed.
    with pytest.raises(ValueError, match="depeche_rscript"):
        run_annotation_pipeline_with_resume(
            df=small_df, markers=markers, outdir=str(outdir),
            sample_size=len(small_df), dr_method=None,
            cluster_methods=("phenograph", "depeche"),
            phenograph_k=5,
            resume=True, force_restart=False,
        )

    assert (outdir / "02_dr" / "dr_matrix.csv").exists()

    # Second call: resume from the checkpoints written above, this time with
    # a cluster_methods list that doesn't need an R script. This is exactly
    # where the bug fired: the resumed DR checkpoint's dr_method (None)
    # round-tripped through CSV as NaN, and the pre-fix code treated that as
    # "a real DR method was used", ending up with zero feature columns.
    df_labeled, meta = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph",),
        phenograph_k=5,
        resume=True, force_restart=False,
    )

    assert len(df_labeled) == len(small_df)
    assert "phenograph" in meta["results"]["cluster_counts"]


def test_resume_regenerates_visualizations_for_newly_added_method(small_df, markers, tmp_path):
    """Regression test for a real bug found via user testing: after a
    successful run with methods A+B, adding method C to cluster_methods and
    resuming correctly re-ran clustering for C (Step 5 already checked
    per-method), but Step 6 (heatmaps/annotation templates) only checked
    whether *a* visualization checkpoint existed at all, not whether it
    covered every currently-requested method -- so C's heatmap/annotation
    files silently never got created despite clustering succeeding for it."""
    import os

    outdir = tmp_path / "phase1_output"

    # Run 1: two methods
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=True, force_restart=False,
    )
    heatmap_dir = outdir / "04_cluster_heatmaps"
    files_after_run1 = set(os.listdir(heatmap_dir))
    assert any("kmeans" in f for f in files_after_run1)
    assert not any("minibatchkmeans" in f for f in files_after_run1)

    # Run 2: add a third method, resume
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans", "minibatchkmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=True, force_restart=False,
    )
    files_after_run2 = set(os.listdir(heatmap_dir))
    mbk_files = [f for f in files_after_run2 if "minibatchkmeans" in f]
    assert len(mbk_files) >= 4, (
        f"Expected heatmap/annotation/topN files for minibatchkmeans after "
        f"resuming with it newly added, got: {mbk_files}"
    )
