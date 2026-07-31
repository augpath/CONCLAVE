"""Tests for conclave.phase2.projection (KNN label transfer)"""
import numpy as np

from conclave.phase2.projection import knn_label_transfer


def test_knn_transfer_recovers_labels_when_full_dataset_equals_template():
    rng = np.random.default_rng(0)
    X_template = np.vstack([
        rng.normal(loc=[-5, -5], scale=0.2, size=(20, 2)),
        rng.normal(loc=[5, 5], scale=0.2, size=(20, 2)),
    ])
    y_template = np.array(["cluster_A"] * 20 + ["cluster_B"] * 20)

    predicted, confidence = knn_label_transfer(X_template, y_template, X_template, k=5)

    assert len(predicted) == len(X_template)
    # every point should recover its own well-separated cluster's label
    assert list(predicted) == list(y_template)
    assert np.mean(confidence) > 0.9


def test_knn_transfer_confidence_is_vote_proportion():
    # 4 template points, all one label, k=4 -> every full-dataset point's
    # neighbors are unanimous, so confidence must be exactly 1.0
    X_template = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=float)
    y_template = np.array(["X", "X", "X", "X"])
    X_full = np.array([[0.5, 0.5]])

    predicted, confidence = knn_label_transfer(X_template, y_template, X_full, k=4)
    assert predicted[0] == "X"
    assert confidence[0] == 1.0
