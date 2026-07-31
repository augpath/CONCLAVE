"""CONCLAVE Phase 1 - Normalization"""
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from conclave.phase1.utils import ensure_cell_id


# =========================
# 5) Normalization Methods (UPDATED - Sample-Aware)
# =========================

def normalize_markers(
    df: pd.DataFrame,
    markers: list,
    method="z-score",
    sample_cols=None,
    clip=5.0,
    q=0.99,
    scale=1e4,
    logger=None
):
    """
    Normalize marker expression values with support for multi-sample datasets.
    
    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe with cells as rows
    markers : list
        Marker column names to normalize
    method : str, default="z-score"
        Normalization method: "z-score", "lognorm", "minmax", or None
    sample_cols : list of str, optional
        Columns defining sample groups (e.g., ["slide_id", "scene_id"]).
        If None or empty, treats entire dataset as single sample.
        Normalization is performed WITHIN each group to handle batch effects.
    clip : float, default=5.0
        Z-score clipping threshold (±clip)
    q : float, default=0.99
        Quantile for min-max winsorization
    scale : float, default=1e4
        Scale factor for log-normalization
    logger : logging.Logger, optional
        Logger instance
    
    Returns
    -------
    df_normalized : pd.DataFrame
        Dataframe with normalized marker values
    report : dict
        Validation report including sample-level and dataset-level checks
    """
    
    df = ensure_cell_id(df)
    
    # Handle sample grouping
    if sample_cols is None or len(sample_cols) == 0:
        if logger:
            logger.info("Sample grouping: None (treating as single dataset)")
        df['_temp_sample_id'] = 'all'
        group_col = '_temp_sample_id'
        is_temp = True
    else:
        # Validate sample columns exist
        missing = [c for c in sample_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Sample columns not found in dataframe: {missing}")
        
        # Create combined sample identifier
        df['_temp_sample_id'] = df[sample_cols].astype(str).agg('_'.join, axis=1)
        group_col = '_temp_sample_id'
        is_temp = True
        
        n_samples = df[group_col].nunique()
        if logger:
            logger.info(f"Sample grouping: {sample_cols} → {n_samples} unique samples")
            sample_sizes = df.groupby(group_col).size()
            logger.info(f"  Sample sizes: min={sample_sizes.min()}, max={sample_sizes.max()}, "
                       f"median={sample_sizes.median():.0f}")
    
    # Skip normalization if requested
    if method is None or str(method).lower() in ("none", "null", "no"):
        if logger:
            logger.info("Normalization: None (raw values)")
        out = df.copy()
        X = out[markers].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
        out[markers] = X.fillna(0.0)
        if is_temp:
            out.drop(columns=[group_col], inplace=True)
        
        report = {
            'method': None,
            'total_samples': 1,
            'normalization_issues': {'samples_with_constant_markers': [], 'samples_with_high_nan_rate': []},
            'post_validation': {}
        }
        return out, report
    
    method_str = str(method).lower().replace("-", "").replace("_", "")
    
    if logger:
        logger.info(f"Normalization: {method} | within-sample grouping: {bool(sample_cols)}")
    
    # Convert markers to numeric
    X = df[markers].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    
    # Prepare output
    out = df.copy()
    normalized_values = pd.DataFrame(index=df.index, columns=markers, dtype=np.float64)
    
    # Track normalization issues per sample
    issues = {
        'samples_with_constant_markers': [],
        'samples_with_high_nan_rate': [],
        'total_samples': df[group_col].nunique()
    }
    
    # Normalize within each sample group
    for sample_id, sample_indices in df.groupby(group_col).groups.items():
        X_sample = X.loc[sample_indices]
        n_cells = len(sample_indices)
        
        # Z-score normalization
        if method_str in ("zscore", "z"):
            mu = X_sample.mean(axis=0, skipna=True)
            sd = X_sample.std(axis=0, skipna=True)
            
            # Identify constant markers in this sample
            constant_markers = sd[sd <= 1e-12].index.tolist()
            if constant_markers:
                issues['samples_with_constant_markers'].append({
                    'sample_id': str(sample_id),
                    'n_cells': int(n_cells),
                    'constant_markers': constant_markers
                })
            
            # Avoid division by zero
            sd = sd.replace(0, np.nan)
            Z = (X_sample - mu) / sd
            
            # Clip outliers
            if clip is not None and clip > 0:
                Z = Z.clip(lower=-float(clip), upper=float(clip))
            
            # Fill NaNs
            Z = Z.fillna(0.0)
            normalized_values.loc[sample_indices] = Z.values
        
        # Log normalization
        elif method_str in ("lognorm", "lognormalize", "log"):
            Xp = X_sample.clip(lower=0).fillna(0.0)
            totals = Xp.sum(axis=1).replace(0, np.nan)
            Xn = (Xp.div(totals, axis=0) * float(scale)).fillna(0.0)
            Z = np.log1p(Xn)
            normalized_values.loc[sample_indices] = Z.values
        
        # Min-max normalization
        elif method_str in ("minmax",):
            lo = X_sample.quantile(1 - float(q), axis=0)
            hi = X_sample.quantile(float(q), axis=0)
            Xw = X_sample.clip(lower=lo, upper=hi, axis=1)
            mn = Xw.min(axis=0)
            mx = Xw.max(axis=0)
            rng = (mx - mn).replace(0, np.nan)
            Z = ((Xw - mn) / rng).fillna(0.0)
            normalized_values.loc[sample_indices] = Z.values
        
        else:
            raise ValueError(
                f"Unknown normalization method: '{method}'. "
                f"Choose from: None, z-score, lognorm, minmax"
            )
        
        # Check for high NaN rate
        nan_rate = normalized_values.loc[sample_indices].isna().sum().sum() / (n_cells * len(markers))
        if nan_rate > 0.1:
            issues['samples_with_high_nan_rate'].append({
                'sample_id': str(sample_id),
                'n_cells': int(n_cells),
                'nan_rate': float(nan_rate)
            })
    
    # Assign normalized values
    out[markers] = normalized_values
    
    # Clean up temporary column
    if is_temp:
        out.drop(columns=[group_col], inplace=True)
    
    # Post-normalization validation
    if logger:
        logger.info("Running post-normalization validation...")
    
    post_norm_report = validate_normalized_data(
        out, markers, issues, method, logger
    )
    
    return out, post_norm_report


def validate_normalized_data(df, markers, issues, method, logger=None):
    """Validate normalized data quality."""
    
    report = {
        'method': method,
        'total_samples': issues['total_samples'],
        'normalization_issues': issues,
        'post_validation': {}
    }
    
    X = df[markers].apply(pd.to_numeric, errors='coerce')
    
    # Check for NaNs
    nan_counts = X.isna().sum()
    nan_markers = nan_counts[nan_counts > 0].to_dict()
    report['post_validation']['nan_markers'] = {k: int(v) for k, v in nan_markers.items()}
    
    # Check for infinite values
    inf_counts = X.apply(lambda col: np.isinf(col).sum())
    inf_markers = inf_counts[inf_counts > 0].to_dict()
    report['post_validation']['inf_markers'] = {k: int(v) for k, v in inf_markers.items()}
    
    # Check for constant columns
    variances = X.var(axis=0, skipna=True)
    constant_markers = variances[variances <= 1e-12].index.tolist()
    report['post_validation']['constant_markers_overall'] = constant_markers
    
    # Check value ranges
    value_ranges = {}
    for marker in markers:
        vals = X[marker].dropna()
        if len(vals) > 0:
            value_ranges[marker] = {
                'min': float(vals.min()),
                'max': float(vals.max()),
                'mean': float(vals.mean()),
                'std': float(vals.std())
            }
    report['post_validation']['value_ranges'] = value_ranges
    
    # Print summary
    if logger:
        logger.info("Post-normalization validation:")
        
        if issues['samples_with_constant_markers']:
            logger.warning(
                f"  ⚠️  {len(issues['samples_with_constant_markers'])} samples "
                f"had constant markers (set to 0)"
            )
            for issue in issues['samples_with_constant_markers'][:3]:
                logger.warning(
                    f"     Sample {issue['sample_id']}: "
                    f"{len(issue['constant_markers'])} constant markers"
                )
            if len(issues['samples_with_constant_markers']) > 3:
                logger.warning(f"     ... and {len(issues['samples_with_constant_markers'])-3} more")
        
        if issues['samples_with_high_nan_rate']:
            logger.warning(
                f"  ⚠️  {len(issues['samples_with_high_nan_rate'])} samples "
                f"had >10% NaN rate after normalization"
            )
        
        if nan_markers:
            logger.warning(f"  ⚠️  NaNs in {len(nan_markers)} markers (filled with 0)")
        
        if inf_markers:
            logger.error(f"  ❌ Infinite values in {len(inf_markers)} markers!")
            for marker, count in list(inf_markers.items())[:5]:
                logger.error(f"     {marker}: {count} cells")
        
        if constant_markers:
            logger.warning(
                f"  ⚠️  {len(constant_markers)} markers are constant across entire dataset"
            )
        
        if not (nan_markers or inf_markers or constant_markers or issues['samples_with_constant_markers']):
            logger.info("  ✅ No issues detected")
    
    return report
