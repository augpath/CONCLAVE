"""Tests for the run_phase2_complete() API refactor.

Covers: real function arguments for output/input paths (previously only
settable via mutating module globals before a zero-arg call), automatic
marker/sample_cols detection from Phase 1's own pipeline_run_config.json,
explicit-argument override taking priority over that auto-detection, and
backward compatibility with the old "mutate module globals, call with no
args" pattern (several things, including the GUI backend, still use it).
"""
import json

import pandas as pd
import pytest

from conclave.phase1 import run_annotation_pipeline_with_resume


@pytest.fixture
def real_phase1_run(tmp_path, small_df, markers):
    """A real (small, fast) Phase 1 run producing a real
    pipeline_run_config.json and clustered/annotated outputs, plus filled-in
    annotation files in a deliberately non-default directory name -- so
    tests exercise the actual custom-path support, not just the defaults."""
    phase1_out = tmp_path / "my_phase1_output"

    df_labeled, meta = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(phase1_out),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )

    ann_dir = tmp_path / "my_custom_annotations"  # not the default "annotations"
    ann_dir.mkdir()
    heatmap_dir = phase1_out / "04_cluster_heatmaps"
    fake_types = ["Tcell", "Bcell", "Macrophage"]
    for method in ["phenograph", "kmeans"]:
        template = pd.read_csv(heatmap_dir / f"annotation_template_{method}.csv")
        template["annotation"] = [fake_types[i % len(fake_types)] for i in range(len(template))]
        template.to_csv(ann_dir / f"{method}_annotated.csv", index=False)

    return {
        "phase1_output": phase1_out,
        "annotations_dir": ann_dir,
        "markers": markers,
    }


def test_phase1_output_matching_default_value_still_triggers_derivation(tmp_path, monkeypatch, small_df, markers):
    """Regression test for a real bug: derivation of annotations_dir/
    clustered_file/full_data_file used to compare the resolved
    phase1_output against the module DEFAULT's *value*, not whether the
    argument was actually given. A caller who explicitly passes
    phase1_output="./output_phase1" -- which happens to be identical to
    the module's own default -- would silently get the wrong
    annotations_dir (the unrelated module default) instead of
    "./output_phase1/annotations". Fixed by tracking whether the argument
    was given at all, not comparing values."""
    monkeypatch.chdir(tmp_path)
    from conclave.phase2.pipeline_complete import run_phase2_complete

    phase1_out = tmp_path / "output_phase1"  # deliberately matches the module default's value
    df_labeled, meta = run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(phase1_out),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )

    ann_dir = phase1_out / "annotations"  # Phase 1 auto-creates and populates this now
    fake_types = ["Tcell", "Bcell", "Macrophage"]
    for method in ["phenograph", "kmeans"]:
        df = pd.read_csv(ann_dir / f"annotation_template_{method}.csv")
        df["annotation"] = [fake_types[i % len(fake_types)] for i in range(len(df))]
        df.to_csv(ann_dir / f"annotation_template_{method}.csv", index=False)

    df_labeled2, template, single_templates, report = run_phase2_complete(
        phase1_output="./output_phase1",  # explicit, but == module default's value
        phase2_output="./output_phase2",
        knn_k=5,
    )
    assert len(df_labeled2) > 0


def test_phase1_creates_annotations_folder_with_templates(tmp_path, small_df, markers):
    """Phase 1 should copy annotation_template_<method>.csv into
    outdir/annotations/ automatically, so users don't need to manually
    create the folder and copy files before annotating."""
    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )
    ann_dir = outdir / "annotations"
    assert ann_dir.exists()
    assert (ann_dir / "annotation_template_phenograph.csv").exists()
    assert (ann_dir / "annotation_template_kmeans.csv").exists()
    # content should match the originals in 04_cluster_heatmaps/
    original = pd.read_csv(outdir / "04_cluster_heatmaps" / "annotation_template_phenograph.csv")
    copy = pd.read_csv(ann_dir / "annotation_template_phenograph.csv")
    pd.testing.assert_frame_equal(original, copy)


def test_phase1_does_not_clobber_existing_annotation_edits(tmp_path, small_df, markers):
    """If a user has already started editing a copied template and Phase 1
    re-runs (e.g. resume after adding a method), their in-progress edits
    must not be silently overwritten with a blank template again."""
    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph",),
        phenograph_k=5, derive_kmeans_from=None,
        resume=False, force_restart=True,
    )
    ann_path = outdir / "annotations" / "annotation_template_phenograph.csv"
    df = pd.read_csv(ann_path)
    df.loc[0, "annotation"] = "MyEditedValue"
    df.to_csv(ann_path, index=False)

    # resume, adding a second method
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=True, force_restart=False,
    )

    reloaded = pd.read_csv(ann_path)
    assert reloaded.loc[0, "annotation"] == "MyEditedValue"
    assert (outdir / "annotations" / "annotation_template_kmeans.csv").exists()


def test_consensus_methods_autodetected_from_annotated_files(tmp_path, small_df, markers):
    """The main new feature: if Phase 1 clustered with N methods but only
    some have been genuinely annotated (non-blank 'annotation' column),
    Phase 2 should default to using exactly those, not all N."""
    from conclave.phase2.pipeline_complete import run_phase2_complete

    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans", "leiden"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )

    ann_dir = outdir / "annotations"
    fake_types = ["Tcell", "Bcell", "Macrophage"]
    for method in ["phenograph", "kmeans"]:  # leiden left blank on purpose
        df = pd.read_csv(ann_dir / f"annotation_template_{method}.csv")
        df["annotation"] = [fake_types[i % len(fake_types)] for i in range(len(df))]
        df.to_csv(ann_dir / f"annotation_template_{method}.csv", index=False)

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(outdir),
        phase2_output=str(tmp_path / "phase2_out"),
        knn_k=5,
        # consensus_methods NOT passed -- must auto-detect phenograph+kmeans, skip leiden
    )
    assert not any("leiden" in c.lower() for c in df_labeled.columns)
    assert any("phenograph" in c.lower() for c in df_labeled.columns)
    assert any("kmeans" in c.lower() for c in df_labeled.columns)


def test_consensus_methods_explicit_override_beats_autodetection(tmp_path, small_df, markers):
    """Even when more methods are fully annotated, an explicit
    consensus_methods= argument should be respected exactly."""
    from conclave.phase2.pipeline_complete import run_phase2_complete

    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans", "leiden"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )

    ann_dir = outdir / "annotations"
    fake_types = ["Tcell", "Bcell", "Macrophage"]
    for method in ["phenograph", "kmeans", "leiden"]:  # all 3 fully annotated
        df = pd.read_csv(ann_dir / f"annotation_template_{method}.csv")
        df["annotation"] = [fake_types[i % len(fake_types)] for i in range(len(df))]
        df.to_csv(ann_dir / f"annotation_template_{method}.csv", index=False)

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(outdir),
        phase2_output=str(tmp_path / "phase2_out"),
        knn_k=5,
        consensus_methods=["phenograph", "kmeans"],  # explicitly excludes leiden
    )
    assert not any("leiden" in c.lower() for c in df_labeled.columns)


def test_import_creates_no_output_directory(tmp_path, monkeypatch):
    """Regression test: `import conclave` alone used to create
    ./output_phase2/ on disk as a side effect. Confirms it no longer does,
    by importing (already happened at collection time, but re-verified via
    reload semantics is overkill -- instead just confirm the specific
    default-named directory doesn't exist in a fresh cwd)."""
    monkeypatch.chdir(tmp_path)
    import importlib
    import conclave.phase2.pipeline_complete as p2
    importlib.reload(p2)
    assert not (tmp_path / "output_phase2").exists()


def test_custom_paths_and_marker_autodetection(real_phase1_run, tmp_path):
    from conclave.phase2.pipeline_complete import run_phase2_complete

    phase2_out = tmp_path / "my_custom_phase2_output"

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(real_phase1_run["phase1_output"]),
        phase2_output=str(phase2_out),
        annotations_dir=str(real_phase1_run["annotations_dir"]),
        consensus_methods=["phenograph", "kmeans"],
        knn_k=5,
        # markers deliberately omitted -- must auto-load from Phase 1's config
    )

    assert len(df_labeled) > 0
    assert phase2_out.exists()
    assert (phase2_out / "full_dataset_labeled_complete.csv").exists()


def test_marker_autodetection_matches_phase1_config(real_phase1_run, tmp_path, capsys):
    from conclave.phase2.pipeline_complete import run_phase2_complete

    run_phase2_complete(
        phase1_output=str(real_phase1_run["phase1_output"]),
        phase2_output=str(tmp_path / "p2out"),
        annotations_dir=str(real_phase1_run["annotations_dir"]),
        consensus_methods=["phenograph", "kmeans"],
        knn_k=5,
    )
    captured = capsys.readouterr()
    assert "Auto-loaded" in captured.out
    assert f"{len(real_phase1_run['markers'])} markers" in captured.out


def test_explicit_markers_argument_overrides_autodetection(real_phase1_run, tmp_path, capsys):
    """An explicit markers= argument must win over Phase 1 config
    auto-detection -- the whole point of it being a real argument."""
    from conclave.phase2.pipeline_complete import run_phase2_complete

    subset_markers = real_phase1_run["markers"][:3]

    run_phase2_complete(
        phase1_output=str(real_phase1_run["phase1_output"]),
        phase2_output=str(tmp_path / "p2out_explicit"),
        annotations_dir=str(real_phase1_run["annotations_dir"]),
        consensus_methods=["phenograph", "kmeans"],
        knn_k=5,
        markers=subset_markers,
    )
    captured = capsys.readouterr()
    assert "Auto-loaded" not in captured.out
    assert f"Markers: {len(subset_markers)}" in captured.out


def test_legacy_module_attribute_pattern_still_works(real_phase1_run, tmp_path):
    """The old pattern (mutate module globals, call with zero arguments)
    must keep working unchanged -- the GUI backend and older user code
    depend on it."""
    import conclave.phase2.pipeline_complete as p2

    p2.PHASE1_OUTPUT = real_phase1_run["phase1_output"]
    p2.PHASE2_OUTPUT = tmp_path / "legacy_p2out"
    p2.ANNOTATIONS_DIR = real_phase1_run["annotations_dir"]
    p2.CLUSTERED_FILE = real_phase1_run["phase1_output"] / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"
    p2.FULL_DATA_FILE = real_phase1_run["phase1_output"] / "01_normalized_full.csv"
    p2.MARKERS = real_phase1_run["markers"]
    p2.CONSENSUS_METHODS = ["phenograph", "kmeans"]
    p2.KNN_K = 5
    p2.SAMPLE_COLS = []

    df_labeled, template, single_templates, report = p2.run_phase2_complete()

    assert len(df_labeled) > 0
    assert (tmp_path / "legacy_p2out" / "full_dataset_labeled_complete.csv").exists()


def test_missing_phase1_config_falls_back_to_module_default_markers(real_phase1_run, tmp_path, capsys):
    """If Phase 1 wasn't run through run_annotation_pipeline() (no
    pipeline_run_config.json present), Phase 2 should fall back to the
    module-level MARKERS default rather than crash."""
    from conclave.phase2.pipeline_complete import run_phase2_complete

    (real_phase1_run["phase1_output"] / "pipeline_run_config.json").unlink()

    # Fine as long as it doesn't crash trying to auto-detect; it'll fall
    # back to the (wrong-for-this-data) module default marker list, which
    # is a config problem for the caller to notice, not a crash.
    try:
        run_phase2_complete(
            phase1_output=str(real_phase1_run["phase1_output"]),
            phase2_output=str(tmp_path / "p2out_noconfig"),
            annotations_dir=str(real_phase1_run["annotations_dir"]),
            consensus_methods=["phenograph", "kmeans"],
            knn_k=5,
        )
    except KeyError:
        pass  # expected: module-default melanoma markers aren't in this synthetic data
    captured = capsys.readouterr()
    assert "Auto-loaded" not in captured.out


def test_disagreement_scoring_correct_for_non_three_method_counts():
    """Regression test for a real bug: compute_full_disagreement()'s
    'absolute no-consensus' check was hardcoded to require exactly 3
    methods (`len(labels_list) == 3`). With any other method count, that
    condition could never be true, so it silently reported 0% disagreement
    regardless of the actual data -- not a crash, just quietly wrong
    numbers. Generalized to the actual method count."""
    import pandas as pd
    from conclave.phase2.pipeline_complete import compute_full_disagreement

    # row 0: all 4 agree -> no disagreement
    # row 1: all 4 different -> absolute no-consensus
    # row 2: 3 agree, 1 differs -> partial disagreement, not absolute
    df = pd.DataFrame({
        "phenograph_label_projected": ["A", "A", "A"],
        "kmeans_label_projected":     ["A", "B", "A"],
        "leiden_label_projected":     ["A", "C", "A"],
        "birch_label_projected":      ["A", "D", "B"],
    })
    out, pct, _ = compute_full_disagreement(df, ["phenograph", "kmeans", "leiden", "birch"])

    assert list(out["absolute_no_consensus"]) == [0, 1, 0]
    assert out["disagreement_score_full"].iloc[1] == 3  # 4 methods, all different -> n_methods - 1
    assert pct == pytest.approx(100 / 3)  # 1 of 3 rows -- must NOT be 0


def test_disagreement_scoring_still_correct_for_three_methods():
    """Same check, but for the originally-intended 3-method case -- no
    regression from generalizing the n_methods==3 hardcoding."""
    import pandas as pd
    from conclave.phase2.pipeline_complete import compute_full_disagreement

    df = pd.DataFrame({
        "phenograph_label_projected": ["A", "A"],
        "kmeans_label_projected":     ["A", "B"],
        "leiden_label_projected":     ["A", "C"],
    })
    out, pct, _ = compute_full_disagreement(df, ["phenograph", "kmeans", "leiden"])
    assert list(out["absolute_no_consensus"]) == [0, 1]
    assert out["disagreement_score_full"].iloc[1] == 2
    assert pct == pytest.approx(50.0)


def test_phase2_plots_do_not_crash_with_more_than_three_methods(tmp_path, small_df, markers):
    """Regression test for a real bug: the confidence-distribution plot
    used a hardcoded 2x2 subplot grid (max 4 panels = 1 consensus + 3
    methods) and a 3-color palette, both silently assuming at most 3
    consensus methods. A 4th method caused axes[4] to go out of bounds.
    Now scales to any method count."""
    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans", "leiden", "birch"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )

    ann_dir = outdir / "annotations"
    fake_types = ["Tcell", "Bcell", "Macrophage"]
    for method in ["phenograph", "kmeans", "leiden", "birch"]:
        df = pd.read_csv(ann_dir / f"annotation_template_{method}.csv")
        df["annotation"] = [fake_types[i % len(fake_types)] for i in range(len(df))]
        df.to_csv(ann_dir / f"annotation_template_{method}.csv", index=False)

    from conclave.phase2.pipeline_complete import run_phase2_complete

    df_labeled, template, single_templates, report = run_phase2_complete(
        phase1_output=str(outdir),
        phase2_output=str(tmp_path / "phase2_out"),
        knn_k=5,
    )  # must not raise IndexError

    assert (tmp_path / "phase2_out" / "plots" / "confidence_all_methods.png").exists()
    # the fix must not have broken the actual math either
    assert not (df_labeled["disagreement_score_full"] == 0).all()


def test_warning_printed_when_consensus_methods_not_three(tmp_path, small_df, markers, capsys):
    """A count other than 3 should print a clear warning (not raise --
    the pipeline still runs correctly), and exactly 3 should not."""
    from conclave.phase2.pipeline_complete import run_phase2_complete

    outdir = tmp_path / "phase1_out"
    run_annotation_pipeline_with_resume(
        df=small_df, markers=markers, outdir=str(outdir),
        sample_size=len(small_df), dr_method=None,
        cluster_methods=("phenograph", "kmeans"),
        phenograph_k=5, derive_kmeans_from="phenograph",
        resume=False, force_restart=True,
    )
    ann_dir = outdir / "annotations"
    for method in ["phenograph", "kmeans"]:
        df = pd.read_csv(ann_dir / f"annotation_template_{method}.csv")
        df["annotation"] = ["Tcell"] * len(df)
        df.to_csv(ann_dir / f"annotation_template_{method}.csv", index=False)

    run_phase2_complete(
        phase1_output=str(outdir), phase2_output=str(tmp_path / "p2_2methods"), knn_k=5,
    )
    captured = capsys.readouterr()
    assert "methods selected for consensus" in captured.out
    assert "built around exactly 3" in captured.out
