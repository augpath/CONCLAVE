"""CONCLAVE Phase 2 - Utility Functions"""

from pathlib import Path
import numpy as np
import pandas as pd


def ensure_cell_id(df):
    """Ensure cell_id column exists"""
    if 'cell_id' not in df.columns:
        df['cell_id'] = [f"cell_{i}" for i in range(len(df))]
    return df


def load_annotation_mapping(filepath):
    """
    Load cluster ID to cell type annotation mapping.
    
    Expected CSV format:
        cluster_id,annotation
        0,CD8 T cells
        1,B cells
        ...
    """
    df = pd.read_csv(filepath)
    return dict(zip(df['cluster_id'], df['annotation']))


def log_step(step_name, msg=""):
    """Print formatted step message"""
    print(f"\n{'='*80}")
    print(f"STEP: {step_name}")
    if msg:
        print(f"  {msg}")
    print(f"{'='*80}")


