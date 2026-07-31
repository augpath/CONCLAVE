"""Tests for conclave.phase2.flagging

Note: per project decision, Cohen's Kappa is NOT part of this package's
flagging system -- only disagreement score, confidence score, and JSD are
used, so those are what's tested here.
"""
import numpy as np
import pandas as pd
import pytest

from conclave.phase2.flagging import (
    compute_disagreement_scores,
    flag_problematic_cells,
    compute_jsd_metrics,
)


def test_disagreement_score_zero_when_all_methods_agree():
    df = pd.DataFrame({"m1": ["Tcell"], "m2": ["Tcell"], "m3": ["Tcell"]})
    out = compute_disagreement_scores(df, ["m1", "m2", "m3"])
    assert out["disagreement_score"].iloc[0] == 0


def test_disagreement_score_one_when_one_method_differs():
    df = pd.DataFrame({"m1": ["Tcell"], "m2": ["Tcell"], "m3": ["Bcell"]})
    out = compute_disagreement_scores(df, ["m1", "m2", "m3"])
    assert out["disagreement_score"].iloc[0] == 1


def test_disagreement_score_two_when_all_differ():
    df = pd.DataFrame({"m1": ["Tcell"], "m2": ["Bcell"], "m3": ["Macrophage"]})
    out = compute_disagreement_scores(df, ["m1", "m2", "m3"])
    assert out["disagreement_score"].iloc[0] == 2


def test_flag_problematic_cells_thresholds():
    df = pd.DataFrame({
        "confidence_score": [0.9, 0.3, 0.9],
        "disagreement_score": [0, 0, 2],
    })
    out = flag_problematic_cells(df, confidence_threshold=0.5, disagreement_threshold=1)
    assert list(out["flag_low_confidence"]) == [False, True, False]
    assert list(out["flag_high_disagreement"]) == [False, False, True]
    assert list(out["flag_any"]) == [False, True, True]


def test_jsd_zero_when_method_matches_consensus_exactly():
    df = pd.DataFrame({
        "consensus": ["A", "A", "B", "B"],
        "method1": ["A", "A", "B", "B"],
    })
    results = compute_jsd_metrics(df, "consensus", ["method1"])
    assert results["method1"]["overall_jsd"] == pytest.approx(0.0, abs=1e-9)


def test_jsd_positive_when_distributions_differ():
    df = pd.DataFrame({
        "consensus": ["A", "A", "A", "B"],
        "method1": ["A", "B", "B", "B"],
    })
    results = compute_jsd_metrics(df, "consensus", ["method1"])
    assert results["method1"]["overall_jsd"] > 0


def test_jsd_per_sample_breakdown_when_sample_cols_given():
    df = pd.DataFrame({
        "consensus": ["A", "A", "B", "B"],
        "method1": ["A", "A", "B", "B"],
        "sample_id": ["s1", "s1", "s2", "s2"],
    })
    results = compute_jsd_metrics(df, "consensus", ["method1"], sample_cols=["sample_id"])
    assert "per_sample_jsd" in results["method1"]
    assert len(results["method1"]["per_sample_jsd"]) == 2
