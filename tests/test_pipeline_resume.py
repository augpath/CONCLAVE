"""Regression test for a checkpoint-resume bug: resuming a Phase 1
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
    # R script given) alongside one that succeeds. This no longer crashes
    # the whole run (see test_clustering_failure_does_not_abort_other_methods)
    # -- phenograph succeeds and gets checkpointed, depeche is recorded as
    # failed. That's enough to exercise what this test is actually about:
    # a DR checkpoint (dr_method=None) gets written and then reloaded on a
    # second call.
    df_labeled_1, meta_1 = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "depeche"),
        phenograph_k=5,
        resume=True, force_restart=False,
    )
    assert "phenograph" in meta_1["results"]["cluster_counts"]
    assert "depeche" in meta_1["results"]["failed_methods"]

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
    """Regression test for a checkpoint-resume bug: after a
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


def test_clustering_failure_does_not_abort_other_methods():
    """Regression test for a real bug: a single clustering method's
    failure used to abort cluster_annotation_subset entirely via a bare
    `raise`, discarding already-successful methods' results too. Now it
    should log the failure, skip that method, and keep going -- only
    raising if every requested method fails."""
    import numpy as np
    import pandas as pd
    from conclave.phase1.clustering import cluster_annotation_subset

    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(100, 5)), columns=[f"m{i}" for i in range(5)])
    df.insert(0, "cell_id", [f"c{i}" for i in range(100)])

    # birch needs n_clusters derived from another method -- with
    # derive_kmeans_from=None it's guaranteed to fail, while phenograph
    # (which needs no such input) is guaranteed to succeed
    df_labeled, labels_dict, clust_meta = cluster_annotation_subset(
        df=df, feature_cols=[f"m{i}" for i in range(5)], markers_for_r=[f"m{i}" for i in range(5)],
        outdir="/tmp/test_fail_isolation", methods=("phenograph", "birch"),
        derive_kmeans_from=None,
    )

    assert "phenograph" in labels_dict
    assert "birch" not in labels_dict
    assert "birch" in clust_meta["failed_methods"]
    assert "phenograph" in clust_meta["cluster_counts"]
    assert "birch" not in clust_meta["cluster_counts"]  # no KeyError building the summary


def test_clustering_all_methods_failing_raises_clear_error():
    """If literally every requested method fails, there's genuinely
    nothing to save -- this should still raise, with a clear combined
    error message, not silently return empty results."""
    import numpy as np
    import pandas as pd
    import pytest as pt
    from conclave.phase1.clustering import cluster_annotation_subset

    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(50, 5)), columns=[f"m{i}" for i in range(5)])
    df.insert(0, "cell_id", [f"c{i}" for i in range(50)])

    with pt.raises(RuntimeError, match="All requested clustering methods failed"):
        cluster_annotation_subset(
            df=df, feature_cols=[f"m{i}" for i in range(5)], markers_for_r=[f"m{i}" for i in range(5)],
            outdir="/tmp/test_fail_all", methods=("birch", "spectral"),
            derive_kmeans_from=None,  # both need n_clusters, neither can get it
        )


def test_pipeline_survives_partial_clustering_failure_and_retries_only_that_method(tmp_path, small_df, markers):
    """Full pipeline-level regression test for the reported bug: run with
    a method that will fail alongside methods that will succeed -- the
    whole run must not crash, already-successful methods/annotations must
    be preserved, and a second run with the issue fixed must add only the
    previously-failed method (not silently do nothing, and not require a
    full restart)."""
    outdir = tmp_path / "phase1_out"

    # Run 1: phenograph succeeds, birch fails (no derive_kmeans_from)
    df_labeled, meta = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "birch"),
        phenograph_k=5, derive_kmeans_from=None,
        resume=True, force_restart=False,
    )

    assert "phenograph" in meta["results"]["cluster_counts"]
    assert "birch" not in meta["results"]["cluster_counts"]
    assert "birch" in meta["results"]["failed_methods"]

    ann_dir = outdir / "annotations"
    assert (ann_dir / "annotation_template_phenograph.csv").exists()
    assert not (ann_dir / "annotation_template_birch.csv").exists()

    # Run 2: same call, but now derive_kmeans_from is fixed -- birch should
    # succeed this time, without needing FORCE_RESTART, and phenograph's
    # already-successful result should still be there too
    df_labeled2, meta2 = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "birch"),
        phenograph_k=5, derive_kmeans_from="phenograph",  # fixed
        resume=True, force_restart=False,
    )

    assert "phenograph" in meta2["results"]["cluster_counts"]
    assert "birch" in meta2["results"]["cluster_counts"]
    assert not meta2["results"]["failed_methods"]
    assert (ann_dir / "annotation_template_birch.csv").exists()
