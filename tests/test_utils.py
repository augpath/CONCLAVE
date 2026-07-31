"""Tests for conclave.phase1.utils"""
import pandas as pd
import pytest

from conclave.phase1.utils import ensure_cell_id, validate_input_dataframe


def test_ensure_cell_id_creates_column_from_index_when_missing():
    df = pd.DataFrame({"CD3": [1, 2, 3]})
    out = ensure_cell_id(df)
    assert "cell_id" in out.columns
    assert list(out["cell_id"]) == ["cell_0", "cell_1", "cell_2"]


def test_ensure_cell_id_preserves_existing_column_as_string():
    df = pd.DataFrame({"CD3": [1, 2], "cell_id": [101, 102]})
    out = ensure_cell_id(df)
    assert list(out["cell_id"]) == ["101", "102"]
    assert out["cell_id"].dtype == object


def test_validate_input_dataframe_passes_on_good_input(small_df, markers):
    assert validate_input_dataframe(small_df, markers) is True


def test_validate_input_dataframe_raises_on_empty_df(markers):
    empty = pd.DataFrame(columns=markers)
    with pytest.raises(ValueError):
        validate_input_dataframe(empty, markers)


def test_validate_input_dataframe_raises_on_missing_markers(small_df):
    with pytest.raises(ValueError):
        validate_input_dataframe(small_df, ["CD3", "NOT_A_REAL_MARKER"])


def test_validate_input_dataframe_raises_on_empty_marker_list(small_df):
    with pytest.raises(ValueError):
        validate_input_dataframe(small_df, [])
