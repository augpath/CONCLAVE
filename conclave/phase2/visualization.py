"""CONCLAVE Phase 2 - Visualization Functions"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d import Axes3D


def plot_disagreement_ranked(df, output_path):
    """
    Ranked bar plot of disagreement scores.
    RED = high disagreement, ORANGE = partial, BLUE = agreement
    """
    print(f"Creating ranked disagreement plot...")
    
    df_plot = df.sort_values('disagreement_score', ascending=False).reset_index(drop=True)
    
    # Color mapping
    colors = ['red' if s >= 2 else 'orange' if s == 1 else 'steelblue' 
              for s in df_plot['disagreement_score']]
    
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(range(len(df_plot)), df_plot['disagreement_score'], 
           color=colors, width=1.0, edgecolor='none')
    
    ax.set_xlabel('Cell (ranked by disagreement)', fontsize=13)
    ax.set_ylabel('Disagreement Score', fontsize=13)
    ax.set_title('Cell-Level Disagreement - RANKED (RED = High Disagreement)', 
                 fontsize=15, fontweight='bold')
    ax.set_ylim(-0.1, df_plot['disagreement_score'].max() + 0.3)
    
    # Legend
    legend_elements = [
        Patch(facecolor='steelblue', label='All methods agree (0)'),
        Patch(facecolor='orange', label='Partial disagreement (1)'),
        Patch(facecolor='red', label='Full disagreement (≥2)')
    ]
    ax.legend(handles=legend_elements, loc='upper right', fontsize=11)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved: {output_path}")


def plot_confidence_distribution(df, output_path):
    """Histogram of confidence scores"""
    print(f"Creating confidence distribution...")
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df['confidence_score'], bins=50, color='steelblue', 
            edgecolor='black', alpha=0.7)
    ax.axvline(0.5, color='red', linestyle='--', linewidth=2, 
               label='Low confidence threshold')
    ax.axvline(0.8, color='green', linestyle='--', linewidth=2, 
               label='High confidence threshold')
    
    ax.set_xlabel('Confidence Score', fontsize=12)
    ax.set_ylabel('Number of Cells', fontsize=12)
    ax.set_title('Distribution of Confidence Scores', fontsize=14, fontweight='bold')
    ax.legend()
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved: {output_path}")


def plot_umap_3d(df, umap_cols, color_by, output_path, title='3D UMAP'):
    """3D scatter plot of UMAP"""
    print(f"Creating 3D UMAP plot...")
    
    fig = plt.figure(figsize=(14, 12))
    ax = fig.add_subplot(111, projection='3d')
    
    # Color by label
    unique_labels = df[color_by].unique()
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_labels)))
    
    for label, color in zip(unique_labels, colors):
        mask = df[color_by] == label
        ax.scatter(df.loc[mask, umap_cols[0]], 
                   df.loc[mask, umap_cols[1]], 
                   df.loc[mask, umap_cols[2]],
                   c=[color], label=label, s=10, alpha=0.6)
    
    ax.set_xlabel(umap_cols[0])
    ax.set_ylabel(umap_cols[1])
    ax.set_zlabel(umap_cols[2])
    ax.set_title(title, fontsize=14, fontweight='bold')
    
    # Legend
    ax.legend(bbox_to_anchor=(1.15, 1), loc='upper left', markerscale=2, fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved: {output_path}")


def plot_jsd_comparison(jsd_results, output_path):
    """Bar plot of JSD values across methods"""
    print(f"Creating JSD comparison plot...")
    
    methods = list(jsd_results.keys())
    jsds = [jsd_results[m]['overall_jsd'] for m in methods]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(methods, jsds, color='steelblue', edgecolor='black')
    
    # Color bars by JSD value
    for bar, jsd in zip(bars, jsds):
        if jsd < 0.1:
            bar.set_color('green')
        elif jsd < 0.3:
            bar.set_color('orange')
        else:
            bar.set_color('red')
    
    ax.set_ylabel('Jensen-Shannon Divergence', fontsize=12)
    ax.set_title('Consensus vs Single Methods - Label Distribution Divergence', 
                 fontsize=14, fontweight='bold')
    ax.set_ylim(0, max(jsds) * 1.2)
    ax.grid(axis='y', alpha=0.3)
    
    # Add value labels
    for i, (method, jsd) in enumerate(zip(methods, jsds)):
        ax.text(i, jsd + 0.01, f'{jsd:.3f}', ha='center', va='bottom', fontsize=10)
    
    # Add interpretation guide
    ax.axhline(y=0.1, color='green', linestyle='--', linewidth=1, alpha=0.5)
    ax.axhline(y=0.3, color='orange', linestyle='--', linewidth=1, alpha=0.5)
    ax.text(len(methods)-0.5, 0.1, 'Low divergence', fontsize=9, color='green')
    ax.text(len(methods)-0.5, 0.3, 'High divergence', fontsize=9, color='red')
    
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"  ✅ Saved: {output_path}")


