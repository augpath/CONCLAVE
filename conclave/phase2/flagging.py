"""CONCLAVE Phase 2 - Flagging Metrics"""

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy


def compute_disagreement_scores(df, method_cols):
    """
    Compute per-cell disagreement score.
    
    Score = number of unique labels - 1
    (0 = all agree, 1 = one method differs, 2+ = all different)
    """
    print("Computing disagreement scores...")
    
    disagreement_scores = []
    
    for idx, row in df.iterrows():
        labels = [row[col] for col in method_cols if pd.notna(row[col])]
        unique_labels = len(set(labels))
        disagreement_scores.append(unique_labels - 1)
    
    df['disagreement_score'] = disagreement_scores
    
    n_agree = (np.array(disagreement_scores) == 0).sum()
    n_partial = (np.array(disagreement_scores) == 1).sum()
    n_full = (np.array(disagreement_scores) >= 2).sum()
    
    print(f"  All agree: {n_agree:,}")
    print(f"  Partial disagreement: {n_partial:,}")
    print(f"  Full disagreement: {n_full:,}")
    
    return df


def flag_problematic_cells(df, confidence_threshold=0.5, disagreement_threshold=1):
    """Flag cells with low confidence or high disagreement"""
    print(f"Flagging problematic cells...")
    
    df['flag_low_confidence'] = df.get('confidence_score', 1.0) < confidence_threshold
    df['flag_high_disagreement'] = df.get('disagreement_score', 0) >= disagreement_threshold
    df['flag_any'] = df['flag_low_confidence'] | df['flag_high_disagreement']
    
    n_low_conf = df['flag_low_confidence'].sum()
    n_high_dis = df['flag_high_disagreement'].sum()
    n_any = df['flag_any'].sum()
    
    print(f"  Low confidence: {n_low_conf:,} ({n_low_conf/len(df)*100:.1f}%)")
    print(f"  High disagreement: {n_high_dis:,} ({n_high_dis/len(df)*100:.1f}%)")
    print(f"  Any flag: {n_any:,} ({n_any/len(df)*100:.1f}%)")
    
    return df


def compute_jsd_metrics(df_template, consensus_col, method_cols, sample_cols=None):
    """
    Compute Jensen-Shannon Divergence between consensus and individual methods.
    
    Returns dictionary with overall and per-sample JSD values.
    """
    print("Computing Jensen-Shannon Divergence...")
    
    results = {}
    
    # Overall JSD
    consensus_dist = df_template[consensus_col].value_counts(normalize=True).sort_index()
    
    for method_col in method_cols:
        method_dist = df_template[method_col].value_counts(normalize=True).sort_index()
        
        # Align distributions
        all_labels = set(consensus_dist.index) | set(method_dist.index)
        p = np.array([consensus_dist.get(lab, 0) for lab in sorted(all_labels)])
        q = np.array([method_dist.get(lab, 0) for lab in sorted(all_labels)])
        
        jsd = jensenshannon(p, q, base=2)
        results[method_col] = {'overall_jsd': jsd}
        print(f"  {method_col}: JSD = {jsd:.4f}")
    
    # Per-sample JSD (if sample columns provided)
    if sample_cols:
        for method_col in method_cols:
            sample_jsds = []
            
            for sample in df_template[sample_cols[0]].unique():
                df_sample = df_template[df_template[sample_cols[0]] == sample]
                
                if len(df_sample) > 0:
                    cons_dist = df_sample[consensus_col].value_counts(normalize=True).sort_index()
                    meth_dist = df_sample[method_col].value_counts(normalize=True).sort_index()
                    
                    all_labs = set(cons_dist.index) | set(meth_dist.index)
                    p = np.array([cons_dist.get(lab, 0) for lab in sorted(all_labs)])
                    q = np.array([meth_dist.get(lab, 0) for lab in sorted(all_labs)])
                    
                    jsd = jensenshannon(p, q, base=2)
                    sample_jsds.append(jsd)
            
            results[method_col]['per_sample_jsd'] = sample_jsds
            results[method_col]['mean_sample_jsd'] = np.mean(sample_jsds) if sample_jsds else 0
    
    return results


