"""Tests for conclave.phase1.clustering.cluster_r_labels / _run_rscript

These test the Python<->R subprocess *bridge* (temp CSV round-trip, contract
validation, error surfacing) using a trivial base-R dummy script, NOT the
actual FlowSOM/DepecheR algorithms -- those require the Bioconductor
FlowSOM/DepecheR packages, which aren't a pip/CI-installable dependency.
See conclave/r_scripts/{flowsom,depeche}_clustering.R for the real scripts
(untested beyond syntax review -- verify against your own R + FlowSOM/
DepecheR installation before relying on them).

Skipped entirely if Rscript isn't on PATH.
"""
import shutil
import textwrap

import numpy as np
import pandas as pd
import pytest

from conclave.phase1.clustering import cluster_r_labels

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not on PATH")


@pytest.fixture
def marker_df():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(rng.normal(size=(30, 4)), columns=["m1", "m2", "m3", "m4"])
    df.insert(0, "cell_id", [f"c{i}" for i in range(30)])
    return df


@pytest.fixture
def dummy_r_script(tmp_path):
    script = tmp_path / "dummy.R"
    script.write_text(textwrap.dedent("""
        args <- commandArgs(trailingOnly = TRUE)
        df <- read.csv(args[1])
        df$dummy_method <- (seq_len(nrow(df)) %% 3) + 1
        write.csv(df, args[1], row.names = FALSE)
    """))
    return script


def test_r_bridge_round_trips_labels(marker_df, dummy_r_script, tmp_path):
    labels = cluster_r_labels(
        marker_df, rscript_path=str(dummy_r_script), out_col="dummy_method",
        tmp_dir=str(tmp_path / "tmp"),
    )
    assert len(labels) == len(marker_df)
    assert set(labels) == {1, 2, 3}


def test_r_bridge_missing_script_raises_filenotfound(marker_df, tmp_path):
    with pytest.raises(FileNotFoundError):
        cluster_r_labels(
            marker_df, rscript_path=str(tmp_path / "does_not_exist.R"),
            out_col="dummy_method", tmp_dir=str(tmp_path / "tmp"),
        )


def test_r_bridge_surfaces_r_error(marker_df, tmp_path):
    script = tmp_path / "broken.R"
    script.write_text('stop("intentional failure for testing")\n')
    with pytest.raises(RuntimeError, match="intentional failure"):
        cluster_r_labels(
            marker_df, rscript_path=str(script), out_col="dummy_method",
            tmp_dir=str(tmp_path / "tmp"),
        )


def test_r_bridge_missing_output_column_raises(marker_df, tmp_path):
    script = tmp_path / "wrongcol.R"
    script.write_text(textwrap.dedent("""
        args <- commandArgs(trailingOnly = TRUE)
        df <- read.csv(args[1])
        df$not_the_right_column <- 1
        write.csv(df, args[1], row.names = FALSE)
    """))
    with pytest.raises(ValueError, match="missing column"):
        cluster_r_labels(
            marker_df, rscript_path=str(script), out_col="dummy_method",
            tmp_dir=str(tmp_path / "tmp"),
        )
