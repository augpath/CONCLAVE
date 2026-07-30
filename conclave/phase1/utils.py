"""CONCLAVE Phase 1 - Utility Functions"""
import hashlib
import json
import time
import logging
import traceback
from pathlib import Path
import pandas as pd
import numpy as np


# Cell 2
# ============================================================
# CHECKPOINT/RESUME SYSTEM
# Add this before the main pipeline function
# ============================================================

import hashlib

def compute_data_hash(df, markers):
    """Compute hash of input data for checkpoint validation"""
    # Hash based on shape and marker list
    data_str = f"{df.shape}_{sorted(markers)}"
    return hashlib.md5(data_str.encode()).hexdigest()[:12]


def check_checkpoint_exists(outdir, step_name):
    """Check if a checkpoint exists for a given step"""
    outdir = Path(outdir)
    checkpoint_file = outdir / f".checkpoint_{step_name}.json"
    return checkpoint_file.exists()


def save_checkpoint(outdir, step_name, step_data, logger=None):
    """Save checkpoint after completing a step"""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    
    checkpoint_file = outdir / f".checkpoint_{step_name}.json"
    
    checkpoint = {
        'step': step_name,
        'timestamp': time.time(),
        'completed': True,
        'data': step_data
    }
    
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)
    
    if logger:
        logger.debug(f"Saved checkpoint: {step_name}")


def load_checkpoint(outdir, step_name, logger=None):
    """Load checkpoint for a given step"""
    outdir = Path(outdir)
    checkpoint_file = outdir / f".checkpoint_{step_name}.json"
    
    if not checkpoint_file.exists():
        return None
    
    try:
        with open(checkpoint_file, 'r') as f:
            checkpoint = json.load(f)
        
        if logger:
            logger.info(f"✓ Loaded checkpoint: {step_name}")
        
        return checkpoint['data']
    except Exception as e:
        if logger:
            logger.warning(f"Failed to load checkpoint {step_name}: {e}")
        return None


def clear_checkpoints(outdir, logger=None):
    """Clear all checkpoints in output directory"""
    outdir = Path(outdir)
    
    if not outdir.exists():
        return
    
    checkpoint_files = list(outdir.glob(".checkpoint_*.json"))
    
    for cf in checkpoint_files:
        try:
            cf.unlink()
        except Exception:
            pass
    
    if logger and checkpoint_files:
        logger.info(f"Cleared {len(checkpoint_files)} checkpoint(s)")


def validate_checkpoint_compatibility(outdir, df, markers, params, logger=None):
    """
    Validate that existing checkpoints are compatible with current run.
    
    Returns
    -------
    compatible : bool
        True if checkpoints can be reused
    reason : str
        Reason if incompatible
    """
    meta_file = outdir / ".checkpoint_metadata.json"
    
    if not meta_file.exists():
        # First run - save metadata
        metadata = {
            'data_hash': compute_data_hash(df, markers),
            'n_cells': len(df),
            'n_markers': len(markers),
            'markers': sorted(markers),
            'params': params
        }
        
        with open(meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return True, "First run"
    
    # Load existing metadata
    try:
        with open(meta_file, 'r') as f:
            old_meta = json.load(f)
    except Exception as e:
        return False, f"Cannot read metadata: {e}"
    
    # Check compatibility
    current_hash = compute_data_hash(df, markers)
    
    if old_meta.get('data_hash') != current_hash:
        return False, "Input data changed"
    
    if old_meta.get('n_cells') != len(df):
        return False, f"Cell count changed: {old_meta.get('n_cells')} → {len(df)}"
    
    if sorted(old_meta.get('markers', [])) != sorted(markers):
        return False, "Marker list changed"
    
    # Check critical parameters
    critical_params = ['normalization', 'sampling', 'sample_size', 'dr_method']
    for param in critical_params:
        if old_meta.get('params', {}).get(param) != params.get(param):
            return False, f"Parameter '{param}' changed"
    
    return True, "Compatible"


def detect_completed_steps(outdir, logger=None):
    """Detect which steps have been completed"""
    outdir = Path(outdir)
    
    steps = [
        'validation',
        'sanity_check', 
        'normalization',
        'sampling',
        'dr',
        'clustering',
        'visualization'
    ]
    
    completed = {}
    
    for step in steps:
        checkpoint_file = outdir / f".checkpoint_{step}.json"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                completed[step] = data.get('timestamp', 0)
            except Exception:
                completed[step] = None
    
    if logger and completed:
        logger.info(f"Found {len(completed)} completed step(s)")
        for step, ts in completed.items():
            if ts:
                logger.info(f"  ✓ {step}: {time.ctime(ts)}")
    
    return completed


# ============================================================
# RESUME-AWARE PIPELINE WRAPPER
# ============================================================

# Cell 3
# =========================
# 1) Logger Setup
# =========================
def setup_logger(outdir: Path, name: str = "conclave_phase1"):
    """Setup comprehensive logging to both file and console."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Reset handlers for notebook re-runs

    log_path = outdir / "pipeline_log.txt"
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # File handler
    fh = logging.FileHandler(log_path, mode='a')
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    # Console handler
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)

    logger.addHandler(fh)
    logger.addHandler(sh)

    logger.info("="*80)
    logger.info(f"Logger initialized -> {log_path}")
    logger.info("="*80)
    return logger, log_path
# Cell 4
# =========================
# 2) Stable cell_id utilities
# =========================
def ensure_cell_id(df: pd.DataFrame, cell_id_col: str = "cell_id") -> pd.DataFrame:
    """
    Ensure dataframe contains a stable string `cell_id` column.
    If missing, creates it from the dataframe index.
    """
    out = df.copy()
    if cell_id_col not in out.columns:
        out[cell_id_col] = [f"cell_{i}" for i in df.index]
    else:
        out[cell_id_col] = out[cell_id_col].astype(str)
    return out


def save_df_with_cell_id(df: pd.DataFrame, path, cell_id_col="cell_id"):
    """
    Save dataframe to CSV ensuring `cell_id` exists and is the first column.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    df2 = ensure_cell_id(df, cell_id_col=cell_id_col)
    cols = [cell_id_col] + [c for c in df2.columns if c != cell_id_col]
    df2[cols].to_csv(path, index=False)
    return path


def save_matrix_with_cell_id(cell_ids, X: np.ndarray, columns, path):
    """
    Save a feature matrix (numpy array) with a cell_id column.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    dfX = pd.DataFrame(X, columns=list(columns))
    dfX.insert(0, "cell_id", pd.Series(cell_ids, dtype=str).values)
    dfX.to_csv(path, index=False)
    return path
# Cell 5
# =========================
# 3) Run-step wrapper with error handling
# =========================
def run_step(step_name, func, step_outdir: Path, step_logger, *args, **kwargs):
    """
    Wrapper to run a pipeline step with timing, error handling, and logging.
    """
    step_outdir = Path(step_outdir)
    step_outdir.mkdir(parents=True, exist_ok=True)

    step_logger.info(f"▶ Starting: {step_name}")
    t0 = time.time()
    
    try:
        out = func(*args, **kwargs)
        dt = time.time() - t0
        step_logger.info(f"✅ Completed: {step_name} | runtime={dt:.2f}s")
        return out
        
    except Exception as e:
        dt = time.time() - t0
        step_logger.error(f"❌ Failed: {step_name} | {type(e).__name__}: {e}")
        
        # Save detailed traceback
        tb = traceback.format_exc()
        err_path = step_outdir / "error_log.txt"
        with open(err_path, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"Step: {step_name}\n")
            f.write(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
            f.write(tb + "\n")
        
        step_logger.error(f"Traceback saved -> {err_path}")
        raise
# Cell 6
# =========================
# 4) Input Validation & Sanity Checks
# =========================
def validate_input_dataframe(df: pd.DataFrame, markers: list, logger=None):
    """
    Validate that the input dataframe has required structure.
    """
    errors = []
    warnings_list = []
    
    # Check dataframe not empty
    if len(df) == 0:
        errors.append("Dataframe is empty (0 rows)")
    
    # Check markers not empty
    if len(markers) == 0:
        errors.append("Markers list is empty")
    
    # Check all markers exist
    missing_markers = [m for m in markers if m not in df.columns]
    if missing_markers:
        errors.append(f"Missing marker columns: {missing_markers}")
    
    # Check for duplicate markers
    if len(markers) != len(set(markers)):
        duplicates = [m for m in markers if markers.count(m) > 1]
        warnings_list.append(f"Duplicate markers detected: {set(duplicates)}")
    
    # Minimum data requirements
    if len(df) < 100:
        warnings_list.append(f"Very small dataset ({len(df)} cells) - results may be unreliable")
    
    if len(markers) < 3:
        warnings_list.append(f"Very few markers ({len(markers)}) - clustering may be poor")
    
    # Report findings
    if errors:
        error_msg = "\n".join([f"  ❌ {e}" for e in errors])
        if logger:
            logger.error(f"Input validation failed:\n{error_msg}")
        raise ValueError(f"Input validation failed:\n{error_msg}")
    
    if warnings_list:
        warning_msg = "\n".join([f"  ⚠️  {w}" for w in warnings_list])
        if logger:
            logger.warning(f"Input validation warnings:\n{warning_msg}")
        else:
            print(f"⚠️  Warnings:\n{warning_msg}")
    
    if logger:
        logger.info("✅ Input validation passed")
    
    return True


def sanity_check_dataframe(df: pd.DataFrame, markers: list, outdir: Path, logger=None):
    """
    Comprehensive data quality checks on marker columns.
    """
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    report = {
        "shape": list(df.shape),
        "n_markers": int(len(markers)),
        "nan_markers": {},
        "dtype_issues": [],
        "near_constant_markers": [],
        "negative_values": {},
        "infinite_values": {}
    }

    # 1. Check for NaNs
    nan_counts = df[markers].isna().sum()
    nan_markers = nan_counts[nan_counts > 0].to_dict()
    report["nan_markers"] = {k: int(v) for k, v in nan_markers.items()}

    # 2. Check dtype coercion issues
    coerced = df[markers].apply(pd.to_numeric, errors="coerce")
    new_nan = coerced.isna().sum() - df[markers].isna().sum()
    bad = new_nan[new_nan > 0]
    if len(bad) > 0:
        report["dtype_issues"] = [
            {"marker": k, "new_nans": int(v)} 
            for k, v in bad.to_dict().items()
        ]

    # 3. Near-constant markers (z-score risk)
    variances = coerced.var(axis=0, skipna=True)
    near_const = variances[variances <= 1e-12].index.tolist()
    report["near_constant_markers"] = near_const
    
    # 4. Check for negative values (problematic for log-norm)
    negative_counts = (coerced < 0).sum()
    neg_markers = negative_counts[negative_counts > 0].to_dict()
    report["negative_values"] = {k: int(v) for k, v in neg_markers.items()}
    
    # 5. Check for infinite values
    inf_counts = np.isinf(coerced).sum()
    inf_markers = inf_counts[inf_counts > 0].to_dict()
    report["infinite_values"] = {k: int(v) for k, v in inf_markers.items()}

    # Save JSON report
    with open(outdir / "sanity_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print("\n" + "="*80)
    print("SANITY CHECK SUMMARY")
    print("="*80)
    print(f"Dataset shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"Markers analyzed: {len(markers)}\n")

    print("[1] Missing values (NaNs):")
    if len(nan_markers) == 0:
        print("  ✅ No NaNs in marker columns")
    else:
        print(f"  ⚠️  NaNs found in {len(nan_markers)} markers:")
        for k, v in list(nan_markers.items())[:10]:
            print(f"     - {k}: {v:,} cells ({100*v/len(df):.1f}%)")
        if len(nan_markers) > 10:
            print(f"     ... and {len(nan_markers)-10} more")

    print("\n[2] Data type issues:")
    if len(report["dtype_issues"]) == 0:
        print("  ✅ All markers are numeric")
    else:
        print(f"  ⚠️  Coercion issues in {len(report['dtype_issues'])} markers:")
        for d in report["dtype_issues"][:10]:
            print(f"     - {d['marker']}: {d['new_nans']:,} new NaNs after coercion")

    print("\n[3] Near-zero variance (z-score risk):")
    if len(near_const) == 0:
        print("  ✅ No constant markers")
    else:
        print(f"  ⚠️  Near-constant markers ({len(near_const)}):")
        print(f"     {near_const[:10]}")
        if len(near_const) > 10:
            print(f"     ... and {len(near_const)-10} more")
    
    print("\n[4] Negative values:")
    if len(neg_markers) == 0:
        print("  ✅ No negative values")
    else:
        print(f"  ⚠️  Negative values in {len(neg_markers)} markers:")
        for k, v in list(neg_markers.items())[:5]:
            print(f"     - {k}: {v:,} cells")
    
    print("\n[5] Infinite values:")
    if len(inf_markers) == 0:
        print("  ✅ No infinite values")
    else:
        print(f"  ⚠️  Infinite values in {len(inf_markers)} markers:")
        for k, v in list(inf_markers.items())[:5]:
            print(f"     - {k}: {v:,} cells")

    print("\n" + "="*80)
    print(f"Full report saved to: {outdir / 'sanity_report.json'}")
    print("="*80 + "\n")

    if logger:
        logger.info(f"Sanity check complete -> {outdir}")

    return report