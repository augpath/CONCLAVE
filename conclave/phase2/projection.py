"""CONCLAVE Phase 2 - Label Projection via KNN"""

from collections import Counter
import numpy as np
from sklearn.neighbors import NearestNeighbors


def knn_label_transfer(X_template, y_template, X_full, k=25, logger=None):
    """
    Transfer labels from template to full dataset using KNN.
    
    Args:
        X_template: UMAP coordinates of template (N_template × 3)
        y_template: Labels of template cells
        X_full: UMAP coordinates of full dataset (N_full × 3)
        k: Number of neighbors
        logger: Optional logger
    
    Returns:
        predicted_labels: List of predicted labels
        confidence_scores: List of confidence scores (proportion of K neighbors agreeing)
    """
    if logger:
        logger.info(f"KNN label transfer (K={k})...")
    else:
        print(f"KNN label transfer (K={k})...")
    
    knn = NearestNeighbors(n_neighbors=k, metric='euclidean')
    knn.fit(X_template)
    
    distances, indices = knn.kneighbors(X_full)
    
    predicted_labels = []
    confidence_scores = []
    
    for i in range(len(X_full)):
        neighbor_labels = y_template[indices[i]]
        counter = Counter(neighbor_labels)
        winner, votes = counter.most_common(1)[0]
        
        predicted_labels.append(winner)
        confidence_scores.append(votes / k)
    
    mean_conf = np.mean(confidence_scores)
    high_conf = (np.array(confidence_scores) > 0.8).sum()
    
    if logger:
        logger.info(f"  Mean confidence: {mean_conf:.3f}")
        logger.info(f"  High conf (>0.8): {high_conf:,}/{len(X_full):,}")
    else:
        print(f"  Mean confidence: {mean_conf:.3f}")
        print(f"  High conf (>0.8): {high_conf:,}/{len(X_full):,}")
    
    return predicted_labels, confidence_scores


