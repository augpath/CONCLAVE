"""CONCLAVE Phase 2 - Template Creation"""

import numpy as np
import pandas as pd


def sample_balanced_per_label(df, label_col, per_label_n=500, seed=42):
    """
    Sample up to N cells per label to create balanced template.
    
    Args:
        df: DataFrame with labeled cells
        label_col: Column name containing labels
        per_label_n: Maximum cells per label (default 500)
        seed: Random seed
    
    Returns:
        DataFrame with balanced sample
    """
    rng = np.random.default_rng(seed)
    sampled_dfs = []
    
    for label in df[label_col].unique():
        if pd.isna(label):
            continue
        
        df_label = df[df[label_col] == label]
        n_cells = len(df_label)
        n_sample = min(per_label_n, n_cells)
        
        if n_sample > 0:
            indices = rng.choice(df_label.index, size=n_sample, replace=False)
            sampled_dfs.append(df_label.loc[indices])
    
    df_sampled = pd.concat(sampled_dfs, ignore_index=True)
    
    print(f"Balanced template created:")
    print(f"  Total cells: {len(df_sampled):,}")
    print(f"  Labels: {df_sampled[label_col].nunique()}")
    print(f"  Cells per label: max {per_label_n}")
    
    return df_sampled


