"""CONCLAVE Phase 2 - Consensus Voting"""

from collections import Counter
import numpy as np
import pandas as pd


def consensus_voting(df, method_cols, min_votes=2):
    """
    Consensus via majority voting across methods.
    
    Args:
        df: DataFrame with annotation columns
        method_cols: List of column names to use for voting
        min_votes: Minimum number of methods that must agree
    
    Returns:
        df: DataFrame with added columns:
            - consensus_label: Winning label
            - consensus_votes: Number of votes for winner
            - has_consensus: Whether min_votes threshold was met
    """
    def _vote(row, cols, min_v):
        vals = [row[c] for c in cols if pd.notna(row[c])]
        if not vals:
            return (np.nan, 0, False)
        cnt = Counter(vals)
        winner, votes = cnt.most_common(1)[0]
        return (winner if votes >= min_v else np.nan, votes, votes >= min_v)
    
    result = df.apply(lambda r: _vote(r, method_cols, min_votes), axis=1, result_type="expand")
    df = df.copy()
    df["consensus_label"] = result[0]
    df["consensus_votes"] = result[1].astype(int)
    df["has_consensus"] = result[2]
    
    coverage = df['has_consensus'].mean() * 100
    print(f"✅ Consensus: {coverage:.1f}% coverage, {df['consensus_label'].nunique()} labels")
    
    # Show top labels
    if df['has_consensus'].sum() > 0:
        print(f"\nTop consensus labels:")
        for label, count in df[df['has_consensus']]['consensus_label'].value_counts().head(10).items():
            pct = count / len(df) * 100
            print(f"  {str(label):30s}: {count:6,} cells ({pct:5.1f}%)")
    
    return df


