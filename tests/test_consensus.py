"""Tests for conclave.phase2.consensus"""
import numpy as np
import pandas as pd

from conclave.phase2.consensus import consensus_voting


def test_unanimous_agreement_gets_full_votes():
    df = pd.DataFrame({
        "phenograph": ["Tcell", "Bcell"],
        "kmeans": ["Tcell", "Bcell"],
        "flowsom": ["Tcell", "Bcell"],
    })
    out = consensus_voting(df, ["phenograph", "kmeans", "flowsom"], min_votes=2)
    assert list(out["consensus_label"]) == ["Tcell", "Bcell"]
    assert list(out["consensus_votes"]) == [3, 3]
    assert out["has_consensus"].all()


def test_two_of_three_meets_min_votes_default():
    df = pd.DataFrame({
        "phenograph": ["Tcell"],
        "kmeans": ["Tcell"],
        "flowsom": ["Macrophage"],
    })
    out = consensus_voting(df, ["phenograph", "kmeans", "flowsom"], min_votes=2)
    assert out["consensus_label"].iloc[0] == "Tcell"
    assert out["consensus_votes"].iloc[0] == 2
    assert out["has_consensus"].iloc[0]


def test_all_disagree_below_min_votes_has_no_consensus():
    df = pd.DataFrame({
        "phenograph": ["Tcell"],
        "kmeans": ["Bcell"],
        "flowsom": ["Macrophage"],
    })
    out = consensus_voting(df, ["phenograph", "kmeans", "flowsom"], min_votes=2)
    assert not out["has_consensus"].iloc[0]
    assert pd.isna(out["consensus_label"].iloc[0])


def test_missing_values_are_excluded_from_voting():
    df = pd.DataFrame({
        "phenograph": ["Tcell"],
        "kmeans": ["Tcell"],
        "flowsom": [np.nan],
    })
    out = consensus_voting(df, ["phenograph", "kmeans", "flowsom"], min_votes=2)
    assert out["consensus_label"].iloc[0] == "Tcell"
    assert out["consensus_votes"].iloc[0] == 2


def test_all_missing_returns_no_consensus():
    df = pd.DataFrame({
        "phenograph": [np.nan],
        "kmeans": [np.nan],
        "flowsom": [np.nan],
    })
    out = consensus_voting(df, ["phenograph", "kmeans", "flowsom"], min_votes=2)
    assert not out["has_consensus"].iloc[0]
    assert out["consensus_votes"].iloc[0] == 0
