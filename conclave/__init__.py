"""
CONCLAVE: Consensus-based Labeling with Automated Evaluation
=============================================================

A comprehensive pipeline for single-cell data analysis with multi-method 
clustering and consensus labeling.

Modules:
--------
- phase1: Data normalization, sampling, and multi-method clustering
- phase2: Consensus labeling, projection, and quality assessment

Example Usage:
--------------
>>> from conclave.phase1.pipeline import run_annotation_pipeline
>>> from conclave.phase2.pipeline_complete import run_phase2_complete
>>> 
>>> # Phase 1: Clustering
>>> df_clustered, meta = run_annotation_pipeline(df, markers, outdir)
>>> 
>>> # Phase 2: Consensus & Projection  
>>> df_labeled, template, report = run_phase2_complete()

Version: 1.0.0
Author: CONCLAVE Development Team
License: MIT
"""

__version__ = "1.0.0"
__author__ = "CONCLAVE Development Team"

# Import main functions for easy access
from conclave.phase1.pipeline import run_annotation_pipeline, run_annotation_pipeline_with_resume
from conclave.phase2.pipeline_complete import run_phase2_complete

__all__ = [
    'run_annotation_pipeline',
    'run_annotation_pipeline_with_resume',
    'run_phase2_complete',
]
