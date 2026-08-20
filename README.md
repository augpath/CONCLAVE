# CONCLAVE

**CON**sensus **CL**ustering with **A**nnotation-**V**alidation **E**xtrapolation for spatial proteomics data.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

![Logo](CONCLAVE_logo.png)

A Python package for single-cell spatial proteomics analysis: multi-method clustering, consensus
labeling across methods, and quality assessment with confidence and disagreement scoring.

## Features

### Phase 1: Multi-Method Clustering
- 10 native Python clustering algorithms: PhenoGraph, K-means, MiniBatchKMeans, Leiden, Agglomerative, BIRCH, Affinity Propagation, MeanShift, DBSCAN, Spectral
- 2 R-based algorithms: FlowSOM, DepecheR (see [R Support](#r-support-for-flowsomdepecher-optional))
- 5 dimensionality-reduction options: none (raw marker space), PCA, UMAP, PaCMAP, t-SNE
- 6 normalization methods: none, z-score, log-normalize, min-max, IQR-based z-score, IQR-based min-max, each computed per-sample or pooled
- Optional GPU acceleration via NVIDIA RAPIDS
- Batch-aware normalization across multiple samples
- Automated data-quality checks and visualization

### Phase 2: Consensus Analysis
- Consensus voting across multiple clustering methods
- 3D UMAP projection with optional GPU support
- Cell-level and sample-level disagreement flagging
- Quality metrics: Jensen-Shannon divergence, confidence scores, spatial analysis
- Diagnostic plots for consensus quality and method comparison

## Installation

### 1. Create a virtual environment

```bash
python3 -m venv conclave-env
source conclave-env/bin/activate      # Windows: conclave-env\Scripts\activate
```

### 2. Install CONCLAVE

```bash
pip install git+https://github.com/augpath/CONCLAVE.git
```

### 3. Verify

```bash
python -c "import conclave; print(conclave.__version__)"
```

This should print `1.0.0`.

### GPU support (optional)

For faster processing on large datasets, using conda:

```bash
conda install -c rapidsai -c conda-forge -c nvidia cuml=26.02 cuda-version=12.2 -y
pip install git+https://github.com/augpath/CONCLAVE.git
python -c "import cuml; print('GPU support available')"
```

Requirements: an NVIDIA GPU (Compute Capability 7.0+: Volta, Turing, Ampere, or newer), CUDA
11.2+ or 12.x, 8GB+ GPU memory recommended.

### R Support for FlowSOM/DepecheR (optional)

The `flowsom_clustering.R` and `depeche_clustering.R` scripts are bundled with the package and
installed automatically with `pip install`, therefore, no separate download needed. You do need R itself
and the FlowSOM/DepecheR R packages installed separately:

```bash
# 1. Install R (skip if already installed)
sudo apt-get install r-base          # Ubuntu/Debian
# or: brew install r                  # macOS

# 2. Install the FlowSOM and DepecheR packages
Rscript -e 'if (!require("BiocManager", quietly = TRUE)) install.packages("BiocManager"); BiocManager::install(c("FlowSOM", "DepecheR"))'

# 3. Verify
Rscript -e 'library(FlowSOM); library(DepecheR); cat("OK\n")'
```

To confirm the bundled scripts are present:

```bash
python -c "
import conclave.r_scripts, pathlib
d = pathlib.Path(conclave.r_scripts.__file__).parent
print(sorted(p.name for p in d.glob('*.R')))
"
```

### Alternative: conda environment

```bash
git clone https://github.com/augpath/CONCLAVE.git
cd CONCLAVE

# GPU:
conda env create -f environment.yml
conda activate conclave

# CPU-only:
conda env create -f environment-cpu.yml
conda activate conclave-cpu

pip install .
```

## Quick Start

### Phase 1: Clustering

```python
import pandas as pd
from conclave.phase1 import run_annotation_pipeline_with_resume

df = pd.read_csv("your_data.csv")
markers = ["CD3", "CD4", "CD8", "CD20", "CD45"]  # replace with your panel

df_clustered, metadata = run_annotation_pipeline_with_resume(
    df=df,
    markers=markers,
    outdir="./output_phase1",
    sample_cols=["sample_id"],   # column identifying slide/sample; None to pool all cells
    normalization="z-score",     # or "iqr-zscore" / "iqr-minmax" for outlier-robust alternatives
    sampling="stratified-notproportional",
    sample_size=20000,
    cluster_methods=("phenograph", "kmeans"),  # add "flowsom"/"depeche" if R is set up
    phenograph_k=25,
    derive_kmeans_from="phenograph",
)

print(f"Clustered {len(df_clustered):,} cells")
```

`flowsom_rscript`/`depeche_rscript` don't need to be passed manually while their path is
auto-detected from the installed package. Pass them only to point at your own copy of a script.

**Resuming.** By default, re-running with the same `outdir` skips whatever's already completed
and only runs what's new or missing; add a clustering method and only that method runs. Pass
`force_restart=True` to ignore existing checkpoints and start from scratch.

**Partial failures.** If one clustering method fails (for example, R isn't set up for
`flowsom`/`depeche`), the other methods still run and their results are saved. Check
`metadata["results"]["failed_methods"]` for what failed and why, fix the issue, and re-run with
`resume=True` (the default) to retry just the failed method.

For a guided walkthrough — picking markers from your own CSV, and every normalization/sampling/DR/clustering option with its hyperparameters — see [`notebooks/CONCLAVE_Phase1.ipynb`](notebooks/CONCLAVE_Phase1.ipynb) and [`notebooks/CONCLAVE_Phase1_Reference.ipynb`](notebooks/CONCLAVE_Phase1_Reference.ipynb). For Phase 2, see [`notebooks/CONCLAVE_Phase2.ipynb`](notebooks/CONCLAVE_Phase2.ipynb).

If you prefer pure scripts see [`examples/`](examples/): `run_phase1.py`, `run_phase2.py`, and
`run_full_pipeline.py` (chains both), with a sample dataset (`Melanoma_example.csv`) included.

**Phase 1 outputs:**
```
output_phase1/
├── .checkpoint_*.json                (resume support -- safe to delete)
├── 00_sanitycheck/
│   ├── sanity_report.json
│   └── normalization_report.json
├── 01_normalized_full.csv
├── 02_sampled_full.csv
├── 02_dr/
│   ├── dr_matrix.csv                 (if dr_method was set)
│   └── dr_info.csv
├── 03_clustering_annotation/
│   ├── clustered_subset_with_labels_on_sampled.csv
│   ├── meta_cluster_summary.csv
│   ├── meta_run.json
│   └── labels/labels_<method>.csv    (one file per clustering method)
├── 04_cluster_heatmaps/
│   ├── heatmap_topN_ranked_<method>.png
│   ├── annotation_template_<method>.csv
│   ├── cluster_topN_wide_<method>.csv
│   ├── cluster_topN_long_<method>.csv
│   └── cluster_sizes_<method>.csv
├── annotations/
│   └── annotation_template_<method>.csv   (copied here automatically, ready to edit)
├── pipeline_run_config.json          (full record of parameters used)
└── pipeline_log.txt
```

### Phase 2: Consensus & Projection

Fill in the `annotation` column of each file in `output_phase1/annotations/`, then:

```python
from conclave.phase2.pipeline_complete import run_phase2_complete

df_labeled, template, single_templates, report = run_phase2_complete(
    phase1_output="./output_phase1",
    phase2_output="./output_phase2",
    knn_k=25,
)

print(f"Labeled {len(df_labeled):,} cells")
print(f"Consensus confidence: {df_labeled['confidence_score'].mean():.3f}")
```

Markers and sample columns are auto-loaded from `output_phase1/pipeline_run_config.json`.
`consensus_methods` defaults to whichever methods have a filled-in annotation file; pass
`consensus_methods=[...]` to pick a specific subset instead. `annotations_dir` defaults to
`output_phase1/annotations`.

<details>
<summary>Older module-attribute pattern (still supported)</summary>

```python
import conclave.phase2.pipeline_complete as p2

p2.PHASE1_OUTPUT = "./output_phase1"
p2.PHASE2_OUTPUT = "./output_phase2"
p2.KNN_K = 25

df_labeled, template, single_templates, report = p2.run_phase2_complete()
```
</details>

**Phase 2 outputs:**
```
output_phase2/
├── full_dataset_labeled_complete.csv  (every cell, labeled)
├── template_with_flags.csv
├── consensus_template.csv
├── metrics_summary.csv
├── phase2_complete_report.json
└── plots/
    ├── disagreement_ranked_RED.png
    ├── confidence_distribution.png
    ├── umap_3d_consensus.png
    ├── umap_3d_<method>.png            (one per method)
    ├── jsd_mean_per_sample_scatter.png
    ├── spatial_confidence_heatmap_tiles.png
    └── ...
```

## Documentation

- **GitHub**: https://github.com/augpath/CONCLAVE
- **Examples**: [`examples/`](examples/)
- **Notebooks**: [`notebooks/`](notebooks/)

## System Requirements

### Minimum (CPU mode)
- OS: Linux, macOS, or Windows (WSL2)
- Python: 3.8 or higher
- RAM: 16GB (32GB+ recommended for over 100k cells)
- Storage: 1GB for package and dependencies

### GPU (optional)
- NVIDIA GPU with Compute Capability 7.0+ (Volta, Turing, Ampere, Ada Lovelace, or newer)
- CUDA 11.2+ or 12.x
- 8GB+ GPU memory recommended

## Dependencies

Installed automatically:

- numpy (>=1.22, <2.0)
- pandas (>=1.5, <3.0)
- scipy (>=1.9, <2.0)
- scikit-learn (>=1.0, <2.0)
- matplotlib (>=3.7, <4.0)
- seaborn (>=0.11, <1.0)
- umap-learn (>=0.5.3)
- phenograph (>=1.5.7)
- leidenalg (>=0.10.0)
- python-igraph (>=0.10)
- openpyxl (>=3.0)

GPU packages, installed separately via conda: `cuml` (>=24.04), `cupy`.

## Troubleshooting

### Import error after installation

```
ModuleNotFoundError: No module named 'pandas'
```

```bash
pip install --upgrade pip
pip uninstall conclave -y
pip install git+https://github.com/augpath/CONCLAVE.git --no-cache-dir
```

### GPU not detected

```bash
python -c "import cuml; print('cuML OK')"
# if that fails:
conda install -c rapidsai cuml=26.02 cuda-version=12.2 -y
```

### Slow performance

- Enable GPU acceleration
- Reduce `sample_size` (default 20000)
- Use fewer clustering methods
- Increase available RAM

## Citation

If you use CONCLAVE in your research, please cite:

```
[Citation information to be added upon publication]
```

## License

MIT License — see [LICENSE](https://github.com/augpath/CONCLAVE/blob/main/LICENSE).

## Support

- **Issues**: https://github.com/augpath/CONCLAVE/issues
- **Discussions**: https://github.com/augpath/CONCLAVE/discussions
- **Email**: pouya.nazari@student.kuleuven.be

## Acknowledgments

- RAPIDS AI team for cuML
- All contributors
