"""
CONCLAVE Phase 2 - Complete Pipeline
=====================================

Full implementation matching the working notebook exactly.

Includes:
1. Expert annotation loading
2. Consensus voting
3. Consensus 3D UMAP + projection
4. Single-method projections (phenograph, flowsom, kmeans)
5. Full disagreement scoring
6. Comprehensive JSD analysis
7. All visualizations
8. Complete reporting

Usage:
    python run_phase2_complete.py
"""

import sys
import time
import json
import pickle
from pathlib import Path
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon

import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.neighbors import NearestNeighbors

# Import Phase 2 modules
from conclave.phase2.utils_phase2 import ensure_cell_id, load_annotation_mapping, log_step
from conclave.phase2.consensus import consensus_voting
from conclave.phase2.template import sample_balanced_per_label
from conclave.phase2.umap_gpu import fit_umap_3d
from conclave.phase2.projection import knn_label_transfer
from conclave.phase2.flagging import compute_disagreement_scores, flag_problematic_cells
from conclave.phase2.visualization import (
    plot_disagreement_ranked,
    plot_confidence_distribution,
    plot_umap_3d
)

# Check GPU
try:
    import cuml
    import cupy as cp
    GPU_AVAILABLE = True
    print(f"✅ cuML (GPU): {cuml.__version__}")
except ImportError:
    GPU_AVAILABLE = False
    print("⚠️  cuML not available - CPU mode")


################################################################################
# CONFIGURATION
################################################################################

# Paths
PHASE1_OUTPUT = Path("./output_phase1")
PHASE2_OUTPUT = Path("./output_phase2")
ANNOTATIONS_DIR = Path("./annotations")

# Input files
CLUSTERED_FILE = PHASE1_OUTPUT / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"
FULL_DATA_FILE = PHASE1_OUTPUT / "01_normalized_full.csv"

# Annotation files
ANNOTATION_FILES = {
    'phenograph': ANNOTATIONS_DIR / "phenograph_annotated.csv",
    'flowsom': ANNOTATIONS_DIR / "flowsom_annotated.csv",
    'kmeans': ANNOTATIONS_DIR / "kmeans_annotated.csv",
}

# Markers
MARKERS = [
    'CD34','CD31','CD141','PNAd','CD25','CD14','CD1c','CK','CD21',
    'FoxP3','CD23','GRB7','CD1A','Podoplanin','CD138','CD248','CD64','CD163',
    'Pax5','IRF8','CD20','CD8','CD303','LYZ','CD16','CD2','HLADR','IRF4','CD5',
    'CD79a','CD68','CD3','CD4','CD27','PRDM1','MELANA','S100B'
]

# Methods
CONSENSUS_METHODS = ['phenograph', 'flowsom', 'kmeans']
MIN_VOTES = 2

# Parameters
TEMPLATE_MAX_PER_LABEL = 500
TEMPLATE_CLEAN = False
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_SEED = 42
KNN_K = 25
SAMPLE_COLS = ['ID']
USE_GPU = GPU_AVAILABLE

# Create directories
PHASE2_OUTPUT.mkdir(parents=True, exist_ok=True)
(PHASE2_OUTPUT / "templates").mkdir(exist_ok=True)
(PHASE2_OUTPUT / "plots").mkdir(exist_ok=True)

print("="*80)
print("CONFIGURATION")
print("="*80)
print(f"GPU: {'ENABLED' if USE_GPU else 'DISABLED'}")
print(f"Methods: {', '.join(CONSENSUS_METHODS)}")
print(f"Template: max {TEMPLATE_MAX_PER_LABEL} cells/label")
print(f"KNN: K={KNN_K}")
print("="*80)


################################################################################
# HELPER FUNCTIONS
################################################################################

def compute_full_disagreement(df, methods):
    """
    Compute disagreement on full dataset.
    Absolute no-consensus = all 3 methods assign DIFFERENT labels
    """
    print("\n" + "="*80)
    print("DISAGREEMENT SCORE (ABSOLUTE NO-CONSENSUS)")
    print("="*80)
    
    disagreement_per_cell = []
    disagreement_scores = []
    
    for idx, row in df.iterrows():
        labels_set = set()
        labels_list = []
        
        for method in methods:
            label = row.get(f'{method}_label_projected')
            if pd.notna(label):
                labels_list.append(label)
                labels_set.add(label)
        
        # Absolute no-consensus: all 3 are DIFFERENT (|L_i| = 3)
        if len(labels_list) == 3 and len(labels_set) == 3:
            disagreement_per_cell.append(1)  # Absolute no-consensus
            disagreement_scores.append(2)    # For compatibility
        else:
            disagreement_per_cell.append(0)  # Some agreement
            disagreement_scores.append(len(labels_set) - 1 if len(labels_set) > 0 else 0)
    
    df['absolute_no_consensus'] = disagreement_per_cell
    df['disagreement_score_full'] = disagreement_scores
    
    # Overall stats
    total_disagreement = sum(disagreement_per_cell)
    disagreement_pct = (total_disagreement / len(df)) * 100
    
    print(f"\nOverall Disagreement:")
    print(f"  Total cells:                 {len(df):,}")
    print(f"  Absolute no-consensus cells: {total_disagreement:,}")
    print(f"  Disagreement %:              {disagreement_pct:.2f}%")
    
    # Per-sample breakdown
    disagreement_per_sample = None
    if 'ID' in df.columns or 'sample' in df.columns:
        sample_col = 'sample' if 'sample' in df.columns else 'ID'
        print(f"\nPer-Sample Disagreement:")
        
        disagreement_per_sample = {}
        for sample in df[sample_col].unique():
            sample_data = df[df[sample_col] == sample]
            n_cells = len(sample_data)
            n_disagreement = sample_data['absolute_no_consensus'].sum()
            pct = (n_disagreement / n_cells) * 100 if n_cells > 0 else 0
            
            disagreement_per_sample[sample] = {
                'n_cells': n_cells,
                'n_disagreement': n_disagreement,
                'disagreement_pct': pct
            }
            
            print(f"  {sample:30s}: {n_disagreement:,}/{n_cells:,} ({pct:.2f}%)")
        
        # Add sample column if not present
        if 'sample' not in df.columns:
            df['sample'] = df[sample_col]
    
    print(f"\n✅ Disagreement score calculated")
    
    return df, disagreement_pct, disagreement_per_sample


def compute_jsd_comprehensive(df, methods):
    """
    Compute comprehensive JSD metrics matching notebook exactly.
    Includes per-sample JSD and per-cell-type contributions.
    """
    print("\n" + "="*80)
    print("JENSEN-SHANNON DIVERGENCE")
    print("="*80)
    
    def calculate_jsd_per_celltype(consensus_labels, method_labels, cell_types=None):
        """Calculate JSD and per-cell-type contribution"""
        # Get all unique cell types
        all_celltypes = sorted(set(consensus_labels) | set(method_labels))
        
        # Build distributions
        consensus_dist = np.array([np.sum(consensus_labels == ct) for ct in all_celltypes], dtype=float)
        method_dist = np.array([np.sum(method_labels == ct) for ct in all_celltypes], dtype=float)
        
        # Normalize
        consensus_dist = consensus_dist / consensus_dist.sum() if consensus_dist.sum() > 0 else consensus_dist
        method_dist = method_dist / method_dist.sum() if method_dist.sum() > 0 else method_dist
        
        # Overall JSD
        overall_jsd = jensenshannon(consensus_dist, method_dist)
        
        # Per cell type contribution
        contributions = {}
        for i, ct in enumerate(all_celltypes):
            p = consensus_dist[i]
            q = method_dist[i]
            m = (p + q) / 2
            
            # KL divergence components
            kl_pm = p * np.log(p / m) if p > 0 and m > 0 else 0
            kl_qm = q * np.log(q / m) if q > 0 and m > 0 else 0
            
            local_jsd = 0.5 * (kl_pm + kl_qm)
            contributions[ct] = local_jsd
        
        return overall_jsd, contributions, all_celltypes
    
    results = {}
    
    # Per-sample JSD
    if 'sample' in df.columns:
        print("\nPer-Sample JSD (Consensus vs Single Methods):")
        
        for sample in df['sample'].unique():
            sample_data = df[df['sample'] == sample]
            consensus_labels = sample_data['consensus_label'].values
            
            print(f"\n  Sample: {sample}")
            
            sample_jsds = {}
            sample_contributions = {}
            
            for method in methods:
                method_col = f'{method}_label_projected'
                if method_col not in sample_data.columns:
                    continue
                
                method_labels = sample_data[method_col].values
                jsd, contributions, celltypes = calculate_jsd_per_celltype(
                    consensus_labels, method_labels
                )
                
                sample_jsds[method] = float(jsd)
                sample_contributions[method] = contributions
                
                print(f"    {method:15s}: JSD = {jsd:.4f}")
            
            results[sample] = {
                'jsds': sample_jsds,
                'contributions': sample_contributions,
                'celltypes': celltypes
            }
    else:
        # Overall JSD (no samples)
        print("\nOverall JSD (Consensus vs Single Methods):")
        
        consensus_labels = df['consensus_label'].values
        
        results['overall'] = {'jsds': {}, 'contributions': {}}
        
        for method in methods:
            method_col = f'{method}_label_projected'
            if method_col not in df.columns:
                continue
            
            method_labels = df[method_col].values
            jsd, contributions, celltypes = calculate_jsd_per_celltype(
                consensus_labels, method_labels
            )
            
            results['overall']['jsds'][method] = float(jsd)
            results['overall']['contributions'][method] = contributions
            results['overall']['celltypes'] = celltypes
            
            print(f"  {method:15s}: JSD = {jsd:.4f}")
    
    # Pairwise JSD (consensus + all methods)
    print("\nPairwise JSD (All Method Combinations):")
    all_method_cols = ['consensus_label'] + [f'{m}_label_projected' for m in methods if f'{m}_label_projected' in df.columns]
    
    pairwise_jsd = {}
    for m1, m2 in combinations(all_method_cols, 2):
        dist1 = df[m1].value_counts(normalize=True).sort_index()
        dist2 = df[m2].value_counts(normalize=True).sort_index()
        
        all_labs = set(dist1.index) | set(dist2.index)
        p = np.array([dist1.get(lab, 0) for lab in sorted(all_labs)])
        q = np.array([dist2.get(lab, 0) for lab in sorted(all_labs)])
        
        jsd = jensenshannon(p, q)
        pairwise_jsd[f"{m1}_vs_{m2}"] = float(jsd)
        print(f"  {m1:25s} vs {m2:25s}: {jsd:.4f}")
    
    results['pairwise'] = pairwise_jsd
    
    print(f"\n✅ JSD calculated")
    
    return results


################################################################################
# MAIN PIPELINE
################################################################################

def run_phase2_complete():
    """Complete Phase 2 pipeline with all features"""
    
    print("\n" + "="*80)
    print("CONCLAVE PHASE 2 - COMPLETE PIPELINE")
    print("="*80)
    
    t_start = time.time()
    
    # Store results
    all_results = {}
    
    # =========================================================================
    # STEP 1: Load Annotations
    # =========================================================================
    log_step("1. Loading Expert Annotations")
    
    annotation_mappings = {}
    for method, filepath in ANNOTATION_FILES.items():
        if filepath.exists():
            try:
                annotation_mappings[method] = load_annotation_mapping(filepath)
                print(f"✅ {method}: {len(annotation_mappings[method])} clusters")
            except Exception as e:
                print(f"⚠️  {method}: Failed ({e})")
        else:
            print(f"⚠️  {method}: Not found - {filepath}")
    
    if len(annotation_mappings) == 0:
        raise ValueError("No annotations found!")
    
    # =========================================================================
    # STEP 2: Load Phase 1 Data & Apply Annotations
    # =========================================================================
    log_step("2. Loading Phase 1 Data")
    
    df_sampled = pd.read_csv(CLUSTERED_FILE)
    df_sampled = ensure_cell_id(df_sampled)
    print(f"✅ Loaded {len(df_sampled):,} cells")
    
    # Apply annotations
    print("\nApplying annotations...")
    for method in CONSENSUS_METHODS:
        label_col = f"label_{method}"
        ann_col = f"ann_{method}"
        
        if label_col in df_sampled.columns and method in annotation_mappings:
            df_sampled[ann_col] = df_sampled[label_col].map(annotation_mappings[method])
            n_ann = df_sampled[ann_col].notna().sum()
            print(f"  ✅ {method}: {n_ann:,} cells annotated")
    
    # =========================================================================
    # STEP 3: Consensus Voting
    # =========================================================================
    log_step("3. Computing Consensus")
    
    ann_cols = [f"ann_{m}" for m in CONSENSUS_METHODS if f"ann_{m}" in df_sampled.columns]
    df_sampled = consensus_voting(df_sampled, ann_cols, MIN_VOTES)
    
    # =========================================================================
    # STEP 4: Create Consensus Template
    # =========================================================================
    log_step("4. Creating Consensus Template")
    
    df_template = sample_balanced_per_label(
        df_sampled[df_sampled['has_consensus']].copy(),
        'consensus_label',
        per_label_n=TEMPLATE_MAX_PER_LABEL,
        seed=UMAP_SEED
    )
    
    print(f"Template: {len(df_template):,} cells, {df_template['consensus_label'].nunique()} labels")
    
    # =========================================================================
    # STEP 5: Fit Consensus 3D UMAP
    # =========================================================================
    log_step("5. Fitting Consensus 3D UMAP (GPU)")
    
    X_template = df_template[MARKERS].values
    umap_model_consensus, umap_embed = fit_umap_3d(
        X_template, USE_GPU, UMAP_N_NEIGHBORS, UMAP_MIN_DIST, UMAP_SEED
    )
    
    df_template['UMAP1'] = umap_embed[:, 0]
    df_template['UMAP2'] = umap_embed[:, 1]
    df_template['UMAP3'] = umap_embed[:, 2]
    
    # Save
    template_file = PHASE2_OUTPUT / "consensus_template.csv"
    df_template.to_csv(template_file, index=False)
    print(f"✅ Saved: {template_file}")
    
    # =========================================================================
    # STEP 6: Project Consensus to Full Dataset
    # =========================================================================
    log_step("6. Projecting Consensus to Full Dataset")
    
    df_full = pd.read_csv(FULL_DATA_FILE)
    df_full = ensure_cell_id(df_full)
    print(f"✅ Loaded {len(df_full):,} cells")
    
    # Transform
    X_full = df_full[MARKERS].values
    if USE_GPU and GPU_AVAILABLE:
        try:
            X_full_gpu = cp.asarray(X_full, dtype=cp.float32)
            umap_full = umap_model_consensus.transform(X_full_gpu)
            umap_full = cp.asnumpy(umap_full)
            print("  ✅ GPU projection")
        except:
            umap_full = umap_model_consensus.transform(X_full)
            print("  ✅ CPU projection")
    else:
        umap_full = umap_model_consensus.transform(X_full)
        print("  ✅ CPU projection")
    
    df_full['UMAP1'] = umap_full[:, 0]
    df_full['UMAP2'] = umap_full[:, 1]
    df_full['UMAP3'] = umap_full[:, 2]
    
    # KNN label transfer
    X_template_umap = df_template[['UMAP1', 'UMAP2', 'UMAP3']].values
    y_template = df_template['consensus_label'].values
    
    predicted_labels, confidence_scores = knn_label_transfer(
        X_template_umap, y_template, umap_full, k=KNN_K
    )
    
    df_full['consensus_label'] = predicted_labels
    df_full['confidence_score'] = confidence_scores
    
    # =========================================================================
    # STEP 7: PROJECT SINGLE METHODS (KEY MISSING PART!)
    # =========================================================================
    log_step("7. Projecting Single Methods")
    
    single_method_results = {}
    single_method_templates = {}
    single_method_models = {}
    
    for method in CONSENSUS_METHODS:
        print(f"\n{'='*80}")
        print(f"METHOD: {method.upper()}")
        print(f"{'='*80}")
        
        ann_col = f"ann_{method}"
        
        # Get cells with this method's annotation
        df_method = df_sampled[df_sampled[ann_col].notna()].copy()
        print(f"  Cells: {len(df_method):,}")
        
        # Create template
        df_template_method = sample_balanced_per_label(
            df_method, ann_col, per_label_n=TEMPLATE_MAX_PER_LABEL, seed=UMAP_SEED
        )
        print(f"  Template: {len(df_template_method):,}")
        
        # Fit UMAP
        X_temp_method = df_template_method[MARKERS].values
        umap_model_method, umap_emb_method = fit_umap_3d(
            X_temp_method, USE_GPU, UMAP_N_NEIGHBORS, UMAP_MIN_DIST, UMAP_SEED
        )
        
        df_template_method[f'UMAP1_{method}'] = umap_emb_method[:, 0]
        df_template_method[f'UMAP2_{method}'] = umap_emb_method[:, 1]
        df_template_method[f'UMAP3_{method}'] = umap_emb_method[:, 2]
        
        # Save template
        template_method_file = PHASE2_OUTPUT / "templates" / f"template_{method}.csv"
        df_template_method.to_csv(template_method_file, index=False)
        
        # Project full dataset
        print(f"  Projecting full dataset...")
        if USE_GPU and GPU_AVAILABLE:
            try:
                X_full_gpu = cp.asarray(X_full, dtype=cp.float32)
                umap_full_method = umap_model_method.transform(X_full_gpu)
                umap_full_method = cp.asnumpy(umap_full_method)
            except:
                umap_full_method = umap_model_method.transform(X_full)
        else:
            umap_full_method = umap_model_method.transform(X_full)
        
        # KNN transfer
        X_temp_umap_method = df_template_method[[f'UMAP1_{method}', f'UMAP2_{method}', f'UMAP3_{method}']].values
        y_temp_method = df_template_method[ann_col].values
        
        pred_labels_method, conf_scores_method = knn_label_transfer(
            X_temp_umap_method, y_temp_method, umap_full_method, k=KNN_K, logger=None
        )
        
        # Add to dataframe
        df_full[f'{method}_label_projected'] = pred_labels_method
        df_full[f'{method}_confidence'] = conf_scores_method
        df_full[f'{method}_UMAP1'] = umap_full_method[:, 0]
        df_full[f'{method}_UMAP2'] = umap_full_method[:, 1]
        df_full[f'{method}_UMAP3'] = umap_full_method[:, 2]
        
        # Store
        single_method_results[method] = {
            'labels': pred_labels_method,
            'confidence': conf_scores_method
        }
        single_method_templates[method] = df_template_method
        single_method_models[method] = umap_model_method
        
        print(f"  ✅ Complete")
    
    print(f"\n{'='*80}")
    print(f"✅ ALL SINGLE METHODS PROJECTED")
    print(f"{'='*80}")
    
    # =========================================================================
    # STEP 8: Compute Full Metrics
    # =========================================================================
    log_step("8. Computing Comprehensive Metrics")
    
    # Template disagreement
    df_template = compute_disagreement_scores(df_template, ann_cols)
    df_template = flag_problematic_cells(df_template)
    
    # Full dataset disagreement (ABSOLUTE NO-CONSENSUS)
    df_full, disagreement_pct, disagreement_per_sample = compute_full_disagreement(
        df_full, CONSENSUS_METHODS
    )
    
    # JSD (with per-sample and per-cell-type contributions)
    jsd_results = compute_jsd_comprehensive(df_full, CONSENSUS_METHODS)
    
    # Confidence stats
    print("\nConfidence scores:")
    print(f"  Consensus mean: {df_full['confidence_score'].mean():.3f}")
    for method in CONSENSUS_METHODS:
        conf_col = f'{method}_confidence'
        if conf_col in df_full.columns:
            print(f"  {method:12s} mean: {df_full[conf_col].mean():.3f}")
    
    # =========================================================================
    # STEP 9: Create Visualizations
    # =========================================================================
    log_step("9. Creating Visualizations")
    
    plots_dir = PHASE2_OUTPUT / "plots"
    
    # Disagreement plot (RED highlighting)
    print("  Creating disagreement plot...")
    plot_disagreement_ranked(df_template, plots_dir / "disagreement_ranked_RED.png")
    
    # Confidence distribution
    print("  Creating confidence distribution...")
    plot_confidence_distribution(df_full, plots_dir / "confidence_distribution.png")
    
    # 3D UMAP - Consensus
    print("  Creating consensus UMAP...")
    plot_umap_3d(
        df_template, ['UMAP1', 'UMAP2', 'UMAP3'], 'consensus_label',
        plots_dir / "umap_3d_consensus.png", 
        title='3D UMAP - Consensus Labels'
    )
    
    # 3D UMAP - Per method
    for method in CONSENSUS_METHODS:
        print(f"  Creating {method} UMAP...")
        df_temp_method = single_method_templates[method]
        plot_umap_3d(
            df_temp_method,
            [f'UMAP1_{method}', f'UMAP2_{method}', f'UMAP3_{method}'],
            f'ann_{method}',
            plots_dir / f"umap_3d_{method}.png",
            title=f'3D UMAP - {method.title()}'
        )
    
    # JSD comparison bar plot
    print("  Creating JSD comparison...")
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Extract JSD values based on structure
    methods_plot = []
    jsds_plot = []
    
    if 'overall' in jsd_results:
        # Single sample case
        for method in CONSENSUS_METHODS:
            if method in jsd_results['overall']['jsds']:
                methods_plot.append(method)
                jsds_plot.append(jsd_results['overall']['jsds'][method])
    else:
        # Multi-sample case - average across samples
        jsd_by_method = {m: [] for m in CONSENSUS_METHODS}
        for sample_key in jsd_results.keys():
            if sample_key != 'pairwise':
                for method in CONSENSUS_METHODS:
                    if method in jsd_results[sample_key]['jsds']:
                        jsd_by_method[method].append(jsd_results[sample_key]['jsds'][method])
        
        for method in CONSENSUS_METHODS:
            if jsd_by_method[method]:
                methods_plot.append(method)
                jsds_plot.append(np.mean(jsd_by_method[method]))
    
    if methods_plot and jsds_plot:
        colors = ['green' if j < 0.1 else 'orange' if j < 0.3 else 'red' for j in jsds_plot]
        
        ax.bar(methods_plot, jsds_plot, color=colors, edgecolor='black')
        ax.set_ylabel('Jensen-Shannon Divergence', fontsize=12)
        ax.set_title('Consensus vs Single Methods - JSD', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        for i, (m, j) in enumerate(zip(methods_plot, jsds_plot)):
            ax.text(i, j + 0.01, f'{j:.3f}', ha='center', fontsize=10)
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(plots_dir / "jsd_comparison.png", dpi=300, bbox_inches='tight')
        plt.close()
    else:
        print("  ⚠️  Skipping JSD comparison (no data)")
    
    # JSD per-cell-type contributions heatmap
    print("  Creating JSD cell-type contributions heatmap...")
    
    # First, compute pairwise JSD per sample with cell-type contributions (like notebook Cell 30)
    if 'sample' in df_full.columns:
        print("  Computing pairwise JSD per sample with cell-type contributions...")
        
        all_methods_jsd = ['consensus'] + CONSENSUS_METHODS
        jsd_all_pairs_data = []
        celltype_jsd_data = []
        
        for sample in df_full['sample'].unique():
            sample_data = df_full[df_full['sample'] == sample]
            
            # Get labels for all methods
            method_labels_dict = {
                'consensus': sample_data['consensus_label'].values
            }
            for method in CONSENSUS_METHODS:
                method_col = f'{method}_label_projected'
                if method_col in sample_data.columns:
                    method_labels_dict[method] = sample_data[method_col].values
            
            # Get all cell types in this sample
            all_celltypes_sample = set()
            for labels in method_labels_dict.values():
                all_celltypes_sample.update(labels)
            all_celltypes_sample = sorted(all_celltypes_sample)
            
            # Calculate all pairwise combinations
            sample_jsds = []
            
            for m1, m2 in combinations(all_methods_jsd, 2):
                if m1 not in method_labels_dict or m2 not in method_labels_dict:
                    continue
                
                labels1 = method_labels_dict[m1]
                labels2 = method_labels_dict[m2]
                
                # Build distributions
                dist1 = np.array([np.sum(labels1 == ct) for ct in all_celltypes_sample], dtype=float)
                dist2 = np.array([np.sum(labels2 == ct) for ct in all_celltypes_sample], dtype=float)
                
                # Normalize
                dist1 = dist1 / dist1.sum() if dist1.sum() > 0 else dist1
                dist2 = dist2 / dist2.sum() if dist2.sum() > 0 else dist2
                
                # Overall JSD
                jsd = jensenshannon(dist1, dist2)
                sample_jsds.append(jsd)
                
                jsd_all_pairs_data.append({
                    'sample': sample,
                    'method1': m1,
                    'method2': m2,
                    'jsd': jsd
                })
                
                # Per cell type contributions
                for i, ct in enumerate(all_celltypes_sample):
                    p = dist1[i]
                    q = dist2[i]
                    m = (p + q) / 2
                    
                    kl_pm = p * np.log(p / m) if p > 0 and m > 0 else 0
                    kl_qm = q * np.log(q / m) if q > 0 and m > 0 else 0
                    local_jsd = 0.5 * (kl_pm + kl_qm)
                    
                    celltype_jsd_data.append({
                        'sample': sample,
                        'method_pair': f"{m1}_vs_{m2}",
                        'celltype': ct,
                        'contribution': local_jsd
                    })
        
        # Convert to DataFrames
        df_jsd_pairs = pd.DataFrame(jsd_all_pairs_data)
        df_celltype_jsd = pd.DataFrame(celltype_jsd_data)
        
        # Calculate mean JSD per sample
        df_mean_jsd_per_sample = df_jsd_pairs.groupby('sample')['jsd'].mean().reset_index()
        df_mean_jsd_per_sample.columns = ['sample', 'mean_jsd']
        
        # Flag outliers (mean + sd threshold)
        mean_val = df_mean_jsd_per_sample['mean_jsd'].mean()
        sd_val = df_mean_jsd_per_sample['mean_jsd'].std()
        threshold = mean_val + sd_val
        
        df_mean_jsd_per_sample['is_outlier'] = df_mean_jsd_per_sample['mean_jsd'] > threshold
        df_mean_jsd_per_sample = df_mean_jsd_per_sample.sort_values('mean_jsd', ascending=False)
        
        # VISUALIZATION 1: Mean JSD scatter with flagged samples (RED)
        print("  Creating mean JSD per sample scatter plot...")
        fig, ax = plt.subplots(figsize=(14, 6))
        
        colors = ['red' if x else 'black' for x in df_mean_jsd_per_sample['is_outlier']]
        ax.scatter(
            range(len(df_mean_jsd_per_sample)),
            df_mean_jsd_per_sample['mean_jsd'],
            c=colors,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidth=1
        )
        
        ax.axhline(threshold, color='red', linestyle='--', linewidth=2, 
                  label=f'Threshold ({threshold:.4f})')
        
        ax.set_xticks(range(len(df_mean_jsd_per_sample)))
        ax.set_xticklabels(df_mean_jsd_per_sample['sample'], rotation=90, ha='right')
        ax.set_xlabel('Sample ID', fontsize=12)
        ax.set_ylabel('Mean JSD', fontsize=12)
        ax.set_title('Average Jensen-Shannon Divergence per Sample\n(Across All Method Pairs)', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(plots_dir / "jsd_mean_per_sample_scatter.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # VISUALIZATION 2: Heatmap - Samples × Cell Types
        print("  Creating JSD heatmap (Samples × Cell Types)...")
        
        # Average cell type contributions per sample
        df_heatmap = df_celltype_jsd.groupby(['sample', 'celltype'])['contribution'].mean().reset_index()
        heatmap_matrix = df_heatmap.pivot(index='sample', columns='celltype', values='contribution')
        
        # Sort by mean JSD (descending)
        sample_order = df_mean_jsd_per_sample.sort_values('mean_jsd', ascending=False)['sample'].tolist()
        heatmap_matrix = heatmap_matrix.reindex(sample_order)
        
        # Create labels with mean JSD
        sample_labels = [
            f"{sample}\n({df_mean_jsd_per_sample[df_mean_jsd_per_sample['sample']==sample]['mean_jsd'].values[0]:.4f})"
            for sample in sample_order
        ]
        
        # Plot
        fig, ax = plt.subplots(figsize=(max(12, len(heatmap_matrix.columns) * 0.6), 
                                       max(10, len(heatmap_matrix) * 0.4)))
        
        sns.heatmap(
            heatmap_matrix,
            cmap='RdBu_r',
            center=0.02,
            vmin=0,
            vmax=0.04,
            annot=False,
            cbar_kws={'label': 'Avg JSD Contribution'},
            yticklabels=sample_labels,
            ax=ax
        )
        
        ax.set_xlabel('Cell Type', fontsize=12)
        ax.set_ylabel('Sample (Mean JSD)', fontsize=12)
        ax.set_title('Heatmap of Average JSD Contributions per Sample and Cell Type\n(Averaged across all pairwise method comparisons)', 
                    fontsize=14, fontweight='bold')
        
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.savefig(plots_dir / "jsd_heatmap_samples_celltypes.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"  ✅ JSD sample analysis complete")
        print(f"     Flagged samples (high JSD): {df_mean_jsd_per_sample[df_mean_jsd_per_sample['is_outlier']]['sample'].tolist()}")
    
    elif 'overall' in jsd_results:

        # Multi-sample: create heatmaps per sample
        samples = [k for k in jsd_results.keys() if k != 'pairwise']
        
        for sample in samples[:6]:  # Limit to first 6
            sample_data = jsd_results[sample]
            methods_in_sample = list(sample_data['jsds'].keys())
            celltypes = sample_data['celltypes']
            
            fig, axes = plt.subplots(1, len(methods_in_sample), figsize=(5*len(methods_in_sample), 8))
            if len(methods_in_sample) == 1:
                axes = [axes]
            
            for i, method in enumerate(methods_in_sample):
                contributions = sample_data['contributions'][method]
                values = [contributions.get(ct, 0) for ct in celltypes]
                
                ax = axes[i]
                sns.heatmap(
                    np.array(values).reshape(-1, 1),
                    yticklabels=celltypes,
                    xticklabels=[method],
                    cmap='YlOrRd',
                    annot=True,
                    fmt='.4f',
                    cbar_kws={'label': 'JSD Contribution'},
                    ax=ax,
                    vmin=0
                )
                ax.set_title(f'{method}\nJSD={sample_data["jsds"][method]:.4f}')
            
            plt.suptitle(f'JSD Cell Type Contributions - Sample: {sample}', fontsize=14)
            plt.tight_layout()
            plt.savefig(plots_dir / f"jsd_celltype_contributions_{sample}.png", dpi=300, bbox_inches='tight')
            plt.close()
    
    elif 'overall' in jsd_results:
        # Single sample/overall
        celltypes = jsd_results['overall']['celltypes']
        methods_avail = list(jsd_results['overall']['jsds'].keys())
        
        fig, axes = plt.subplots(1, len(methods_avail), figsize=(5*len(methods_avail), 10))
        if len(methods_avail) == 1:
            axes = [axes]
        
        for i, method in enumerate(methods_avail):
            contributions = jsd_results['overall']['contributions'][method]
            values = [contributions.get(ct, 0) for ct in celltypes]
            
            ax = axes[i]
            sns.heatmap(
                np.array(values).reshape(-1, 1),
                yticklabels=celltypes,
                xticklabels=[method],
                cmap='YlOrRd',
                annot=True,
                fmt='.4f',
                cbar_kws={'label': 'JSD Contribution'},
                ax=ax,
                vmin=0
            )
            ax.set_title(f'{method}\nJSD={jsd_results["overall"]["jsds"][method]:.4f}')
        
        plt.suptitle('JSD Cell Type Contributions', fontsize=14)
        plt.tight_layout()
        plt.savefig(plots_dir / "jsd_celltype_contributions.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # Disagreement by sample (if applicable) - STYLED LIKE JSD PLOT
    if disagreement_per_sample:
        print("  Creating disagreement by sample plot (with flagging)...")
        
        # Create DataFrame
        df_disagr_samples = pd.DataFrame([
            {'sample': s, 'disagreement_pct': data['disagreement_pct']}
            for s, data in disagreement_per_sample.items()
        ])
        
        # Calculate threshold (mean + SD)
        mean_disagr = df_disagr_samples['disagreement_pct'].mean()
        sd_disagr = df_disagr_samples['disagreement_pct'].std()
        threshold_disagr = mean_disagr + sd_disagr
        
        # Flag outliers
        df_disagr_samples['is_outlier'] = df_disagr_samples['disagreement_pct'] > threshold_disagr
        
        # Sort by disagreement (descending)
        df_disagr_samples = df_disagr_samples.sort_values('disagreement_pct', ascending=False)
        
        # Create scatter plot (like JSD)
        fig, ax = plt.subplots(figsize=(14, 6))
        
        colors = ['red' if x else 'black' for x in df_disagr_samples['is_outlier']]
        ax.scatter(
            range(len(df_disagr_samples)),
            df_disagr_samples['disagreement_pct'],
            c=colors,
            s=100,
            alpha=0.7,
            edgecolors='black',
            linewidth=1
        )
        
        # Threshold line
        ax.axhline(threshold_disagr, color='red', linestyle='--', linewidth=2,
                  label=f'Threshold ({threshold_disagr:.2f}%)')
        
        # Labels
        ax.set_xticks(range(len(df_disagr_samples)))
        ax.set_xticklabels(df_disagr_samples['sample'], rotation=90, ha='right')
        ax.set_xlabel('Sample ID', fontsize=12)
        ax.set_ylabel('Disagreement (%)', fontsize=12)
        ax.set_title('Absolute No-Consensus per Sample\n(RED = Flagged High Disagreement)', 
                    fontsize=14, fontweight='bold')
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(plots_dir / "disagreement_by_sample_flagged.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        # Also create the bar chart version (original style)
        fig, ax = plt.subplots(figsize=(max(10, len(df_disagr_samples)*0.4), 6))
        
        bar_colors = ['coral' if not x else 'red' for x in df_disagr_samples['is_outlier']]
        ax.bar(range(len(df_disagr_samples)), df_disagr_samples['disagreement_pct'], 
               color=bar_colors, edgecolor='black')
        ax.set_xticks(range(len(df_disagr_samples)))
        ax.set_xticklabels(df_disagr_samples['sample'], rotation=45, ha='right')
        ax.set_ylabel('Disagreement (%)', fontsize=12)
        ax.set_title('Absolute No-Consensus by Sample', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # Add threshold line
        ax.axhline(threshold_disagr, color='red', linestyle='--', linewidth=2, alpha=0.5)
        
        plt.tight_layout()
        plt.savefig(plots_dir / "disagreement_by_sample.png", dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"  ✅ Disagreement plots saved")
        print(f"     Flagged samples (high disagreement): {df_disagr_samples[df_disagr_samples['is_outlier']]['sample'].tolist()}")
    
    # Confidence distributions (consensus + all single methods)
    print("  Creating comprehensive confidence distributions...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    # Consensus
    axes[0].hist(df_full['confidence_score'], bins=50, alpha=0.7, color='blue', edgecolor='black')
    axes[0].axvline(df_full['confidence_score'].mean(), color='red', linestyle='--', linewidth=2, label='Mean')
    axes[0].set_xlabel('Confidence', fontsize=11)
    axes[0].set_ylabel('Number of Cells', fontsize=11)
    axes[0].set_title('Consensus Confidence', fontsize=12, fontweight='bold')
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    
    # Single methods
    colors_methods = ['orange', 'green', 'purple']
    for i, method in enumerate(CONSENSUS_METHODS):
        conf_col = f'{method}_confidence'
        if conf_col in df_full.columns:
            axes[i+1].hist(df_full[conf_col], bins=50, alpha=0.7, 
                          color=colors_methods[i], edgecolor='black')
            axes[i+1].axvline(df_full[conf_col].mean(), color='red', 
                             linestyle='--', linewidth=2, label='Mean')
            axes[i+1].set_xlabel('Confidence', fontsize=11)
            axes[i+1].set_ylabel('Number of Cells', fontsize=11)
            axes[i+1].set_title(f'{method.title()} Confidence', fontsize=12, fontweight='bold')
            axes[i+1].legend()
            axes[i+1].grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(plots_dir / "confidence_all_methods.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    # Spatial confidence heatmaps (if X, Y coordinates exist)
    if 'X' in df_full.columns and 'Y' in df_full.columns:
        print("  Creating spatial confidence heatmaps...")
        
        sample_col = 'sample' if 'sample' in df_full.columns else ('ID' if 'ID' in df_full.columns else None)
        
        if sample_col:
            samples = df_full[sample_col].unique()
            n_samples = min(len(samples), 12)  # Limit to 12
            samples = samples[:n_samples]
            
            # Grid layout
            if n_samples <= 4:
                ncols = min(2, n_samples)
                nrows = int(np.ceil(n_samples / ncols))
            elif n_samples <= 9:
                ncols = 3
                nrows = int(np.ceil(n_samples / ncols))
            else:
                ncols = 4
                nrows = 3
            
            # Scatter plot version
            fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4*nrows))
            if nrows * ncols == 1:
                axes = [axes]
            else:
                axes = axes.flatten() if isinstance(axes, np.ndarray) else [axes]
            
            for idx, sample in enumerate(samples):
                ax = axes[idx]
                sample_data = df_full[df_full[sample_col] == sample]
                
                x = sample_data['X'].values
                y = sample_data['Y'].values
                confidence = sample_data['confidence_score'].values
                
                scatter = ax.scatter(x, y, c=confidence, cmap='viridis', s=1, alpha=0.8, vmin=0, vmax=1)
                
                mean_conf = confidence.mean()
                low_conf_pct = (confidence < 0.5).sum() / len(confidence) * 100
                
                ax.set_title(f'{sample}\nMean: {mean_conf:.3f} | Low conf: {low_conf_pct:.1f}%', fontsize=10)
                ax.set_xlabel('X')
                ax.set_ylabel('Y')
                ax.set_aspect('equal')
                plt.colorbar(scatter, ax=ax, label='Confidence')
            
            # Hide unused subplots
            for idx in range(len(samples), len(axes)):
                axes[idx].axis('off')
            
            plt.suptitle('Spatial Confidence Scores per Sample', fontsize=16, y=1.00)
            plt.tight_layout()
            plt.savefig(plots_dir / "spatial_confidence_per_sample.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            # Binned heatmap (50x50 tiles)
            print("  Creating binned spatial heatmaps...")
            fig, axes = plt.subplots(nrows, ncols, figsize=(5*ncols, 4*nrows))
            if nrows * ncols == 1:
                axes = [axes]
            else:
                axes = axes.flatten() if isinstance(axes, np.ndarray) else [axes]
            
            for idx, sample in enumerate(samples):
                ax = axes[idx]
                sample_data = df_full[df_full[sample_col] == sample]
                
                x = sample_data['X'].values
                y = sample_data['Y'].values
                confidence = sample_data['confidence_score'].values
                
                # 50x50 bins
                x_bins = np.linspace(x.min(), x.max(), 51)
                y_bins = np.linspace(y.min(), y.max(), 51)
                
                H, xedges, yedges = np.histogram2d(x, y, bins=[x_bins, y_bins], weights=confidence)
                counts, _, _ = np.histogram2d(x, y, bins=[x_bins, y_bins])
                
                with np.errstate(divide='ignore', invalid='ignore'):
                    H_avg = H / counts
                    H_avg[~np.isfinite(H_avg)] = np.nan
                
                im = ax.imshow(H_avg.T, origin='lower', 
                              extent=[x.min(), x.max(), y.min(), y.max()],
                              cmap='viridis', aspect='auto', vmin=0, vmax=1, interpolation='nearest')
                
                ax.set_title(f'{sample}\nMean: {confidence.mean():.3f}', fontsize=10)
                ax.set_xlabel('X')
                ax.set_ylabel('Y')
                plt.colorbar(im, ax=ax, label='Confidence')
            
            for idx in range(len(samples), len(axes)):
                axes[idx].axis('off')
            
            plt.suptitle('Spatial Confidence Heatmaps (50×50 Tiles)', fontsize=16, y=1.00)
            plt.tight_layout()
            plt.savefig(plots_dir / "spatial_confidence_heatmap_tiles.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            print("  ✅ Spatial confidence heatmaps saved")
        else:
            # Single sample
            print("  Creating single spatial confidence heatmap...")
            fig, axes = plt.subplots(1, 2, figsize=(20, 8))
            
            x = df_full['X'].values
            y = df_full['Y'].values
            confidence = df_full['confidence_score'].values
            
            # Scatter
            scatter = axes[0].scatter(x, y, c=confidence, cmap='viridis', s=1, alpha=0.8, vmin=0, vmax=1)
            axes[0].set_title(f'Spatial Confidence (Scatter)\nMean: {confidence.mean():.3f}', fontsize=14)
            axes[0].set_xlabel('X')
            axes[0].set_ylabel('Y')
            axes[0].set_aspect('equal')
            plt.colorbar(scatter, ax=axes[0], label='Confidence')
            
            # Binned
            x_bins = np.linspace(x.min(), x.max(), 51)
            y_bins = np.linspace(y.min(), y.max(), 51)
            H, _, _ = np.histogram2d(x, y, bins=[x_bins, y_bins], weights=confidence)
            counts, _, _ = np.histogram2d(x, y, bins=[x_bins, y_bins])
            
            with np.errstate(divide='ignore', invalid='ignore'):
                H_avg = H / counts
                H_avg[~np.isfinite(H_avg)] = np.nan
            
            im = axes[1].imshow(H_avg.T, origin='lower', 
                              extent=[x.min(), x.max(), y.min(), y.max()],
                              cmap='viridis', aspect='auto', vmin=0, vmax=1)
            axes[1].set_title('Spatial Confidence (50×50 Tiles)', fontsize=14)
            axes[1].set_xlabel('X')
            axes[1].set_ylabel('Y')
            plt.colorbar(im, ax=axes[1], label='Confidence')
            
            plt.tight_layout()
            plt.savefig(plots_dir / "spatial_confidence_overall.png", dpi=300, bbox_inches='tight')
            plt.close()
            
            print("  ✅ Spatial confidence saved")
    else:
        print("  ⚠️  X, Y coordinates not found - skipping spatial plots")
    
    # Pairwise JSD heatmap
    print("  Creating pairwise JSD heatmap...")
    if 'pairwise' in jsd_results:
        pairwise = jsd_results['pairwise']
        
        # Create matrix
        all_methods = ['consensus'] + CONSENSUS_METHODS
        n = len(all_methods)
        jsd_matrix = np.zeros((n, n))
        
        for i, m1 in enumerate(all_methods):
            for j, m2 in enumerate(all_methods):
                if i == j:
                    jsd_matrix[i, j] = 0
                else:
                    m1_col = 'consensus_label' if m1 == 'consensus' else f'{m1}_label_projected'
                    m2_col = 'consensus_label' if m2 == 'consensus' else f'{m2}_label_projected'
                    key = f"{m1_col}_vs_{m2_col}"
                    key_rev = f"{m2_col}_vs_{m1_col}"
                    
                    if key in pairwise:
                        jsd_matrix[i, j] = pairwise[key]
                    elif key_rev in pairwise:
                        jsd_matrix[i, j] = pairwise[key_rev]
        
        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(jsd_matrix, cmap='RdYlGn_r', vmin=0, vmax=0.5)
        
        ax.set_xticks(np.arange(n))
        ax.set_yticks(np.arange(n))
        ax.set_xticklabels(all_methods)
        ax.set_yticklabels(all_methods)
        
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        
        for i in range(n):
            for j in range(n):
                text = ax.text(j, i, f'{jsd_matrix[i, j]:.3f}',
                             ha="center", va="center", color="black", fontsize=9)
        
        ax.set_title("Pairwise JSD Between All Methods", fontsize=14, fontweight='bold')
        fig.colorbar(im, ax=ax, label='Jensen-Shannon Divergence')
        
        plt.tight_layout()
        plt.savefig(plots_dir / "jsd_pairwise_heatmap.png", dpi=300, bbox_inches='tight')
        plt.close()
    
    # Disagreement on full dataset
    print("  Creating full disagreement plot...")
    df_full_sorted = df_full.sort_values('disagreement_score_full', ascending=False).reset_index(drop=True)
    colors_disagr = ['red' if s >= 2 else 'orange' if s == 1 else 'steelblue' 
                     for s in df_full_sorted['disagreement_score_full']]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(range(len(df_full_sorted)), df_full_sorted['disagreement_score_full'],
           color=colors_disagr, width=1.0, edgecolor='none')
    ax.set_xlabel('Cell (ranked)', fontsize=12)
    ax.set_ylabel('Disagreement Score', fontsize=12)
    ax.set_title('Full Dataset Disagreement (RED = High)', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(plots_dir / "disagreement_full_dataset_RED.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"✅ All visualizations saved to: {plots_dir}")
    
    # =========================================================================
    # STEP 10: Save Outputs
    # =========================================================================
    log_step("10. Saving Outputs")
    
    # Full labeled dataset
    full_output = PHASE2_OUTPUT / "full_dataset_labeled_complete.csv"
    df_full.to_csv(full_output, index=False)
    print(f"✅ Saved: {full_output} ({len(df_full):,} cells)")
    
    # Template with flags
    template_flagged = PHASE2_OUTPUT / "template_with_flags.csv"
    df_template.to_csv(template_flagged, index=False)
    print(f"✅ Saved: {template_flagged}")
    
    # Save UMAP models
    model_consensus_file = PHASE2_OUTPUT / "umap_model_consensus.pkl"
    with open(model_consensus_file, 'wb') as f:
        pickle.dump(umap_model_consensus, f)
    print(f"✅ Saved consensus UMAP model")
    
    for method, model in single_method_models.items():
        model_file = PHASE2_OUTPUT / "templates" / f"umap_model_{method}.pkl"
        with open(model_file, 'wb') as f:
            pickle.dump(model, f)
    print(f"✅ Saved {len(single_method_models)} method UMAP models")
    
    # Summary report
    report = {
        "runtime_seconds": time.time() - t_start,
        "gpu_used": USE_GPU,
        "full_dataset": {
            "total_cells": len(df_full),
            "unique_labels": int(df_full['consensus_label'].nunique()),
            "mean_confidence": float(df_full['confidence_score'].mean()),
            "high_confidence_pct": float((df_full['confidence_score'] > 0.8).mean() * 100),
            "low_confidence_pct": float((df_full['confidence_score'] < 0.5).mean() * 100),
            "disagreement_pct": float(disagreement_pct)
        },
        "template": {
            "total_cells": len(df_template),
            "unique_labels": int(df_template['consensus_label'].nunique()),
            "high_disagreement": int(df_template.get('flag_high_disagreement', pd.Series([False])).sum())
        },
        "methods": {
            method: {
                "mean_confidence": float(df_full[f'{method}_confidence'].mean()),
                "unique_labels": int(df_full[f'{method}_label_projected'].nunique())
            } for method in CONSENSUS_METHODS if f'{method}_confidence' in df_full.columns
        },
        "jsd_results": {}
    }
    
    # Add JSD to report based on structure
    if 'overall' in jsd_results:
        report["jsd_results"] = jsd_results['overall']['jsds']
    elif jsd_results:
        # Multi-sample: average JSD per method
        jsd_avg = {}
        for sample_key in jsd_results.keys():
            if sample_key != 'pairwise':
                for method, jsd_val in jsd_results[sample_key]['jsds'].items():
                    if method not in jsd_avg:
                        jsd_avg[method] = []
                    jsd_avg[method].append(jsd_val)
        report["jsd_results"] = {m: float(np.mean(vals)) for m, vals in jsd_avg.items()}
    
    if 'pairwise' in jsd_results:
        report["jsd_pairwise"] = jsd_results['pairwise']
    
    report_file = PHASE2_OUTPUT / "phase2_complete_report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"✅ Saved: {report_file}")
    
    # Detailed metrics CSV
    metrics_summary = []
    for method in ['consensus'] + CONSENSUS_METHODS:
        if method == 'consensus':
            conf_col = 'confidence_score'
            label_col = 'consensus_label'
        else:
            conf_col = f'{method}_confidence'
            label_col = f'{method}_label_projected'
        
        if conf_col in df_full.columns:
            metrics_summary.append({
                'method': method,
                'mean_confidence': df_full[conf_col].mean(),
                'median_confidence': df_full[conf_col].median(),
                'high_conf_pct': (df_full[conf_col] > 0.8).mean() * 100,
                'low_conf_pct': (df_full[conf_col] < 0.5).mean() * 100,
                'unique_labels': df_full[label_col].nunique()
            })
    
    df_metrics = pd.DataFrame(metrics_summary)
    metrics_file = PHASE2_OUTPUT / "metrics_summary.csv"
    df_metrics.to_csv(metrics_file, index=False)
    print(f"✅ Saved: {metrics_file}")
    
    # =========================================================================
    # COMPLETE
    # =========================================================================
    runtime = time.time() - t_start
    
    print("\n" + "="*80)
    print("✅ PHASE 2 COMPLETE")
    print("="*80)
    print(f"Runtime: {runtime:.1f}s ({runtime/60:.1f} min)")
    print(f"\nFull dataset: {len(df_full):,} cells labeled")
    print(f"  Consensus confidence: {df_full['confidence_score'].mean():.3f}")
    print(f"  High confidence: {(df_full['confidence_score'] > 0.8).mean()*100:.1f}%")
    print(f"  Full disagreement: {disagreement_pct:.1f}%")
    print(f"\nSingle methods projected: {', '.join(CONSENSUS_METHODS)}")
    print(f"  JSD (consensus vs methods):")
    
    # Print JSD based on structure
    if 'overall' in jsd_results:
        for method in CONSENSUS_METHODS:
            if method in jsd_results['overall']['jsds']:
                print(f"    {method:12s}: {jsd_results['overall']['jsds'][method]:.4f}")
    elif jsd_results:
        # Multi-sample: show average
        jsd_avg = {}
        for sample_key in jsd_results.keys():
            if sample_key != 'pairwise':
                for method, jsd_val in jsd_results[sample_key]['jsds'].items():
                    if method not in jsd_avg:
                        jsd_avg[method] = []
                    jsd_avg[method].append(jsd_val)
        for method, vals in jsd_avg.items():
            print(f"    {method:12s}: {np.mean(vals):.4f} (avg across {len(vals)} samples)")
    
    print(f"\nOutputs: {PHASE2_OUTPUT}")
    print("  ⭐ full_dataset_labeled_complete.csv - Main output")
    print("  ⭐ template_with_flags.csv - Flagged cells")
    print("  ⭐ plots/ - All visualizations")
    print("  ⭐ phase2_complete_report.json - Summary")
    print("="*80)
    
    return df_full, df_template, single_method_templates, report


################################################################################
# MAIN EXECUTION
################################################################################

if __name__ == "__main__":
    try:
        df_full, df_template, single_templates, report = run_phase2_complete()
        
        print("\n✅ Phase 2 complete pipeline finished successfully!")
        print(f"\nKey outputs:")
        print(f"  - Full dataset:  {PHASE2_OUTPUT / 'full_dataset_labeled_complete.csv'}")
        print(f"  - Template:      {PHASE2_OUTPUT / 'template_with_flags.csv'}")
        print(f"  - Metrics:       {PHASE2_OUTPUT / 'metrics_summary.csv'}")
        print(f"  - Report:        {PHASE2_OUTPUT / 'phase2_complete_report.json'}")
        print(f"  - Plots:         {PHASE2_OUTPUT / 'plots'} ({len(list((PHASE2_OUTPUT / 'plots').glob('*.png')))} files)")
        
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    
