# CONCLAVE: Consensus-based Labeling with Automated Evaluation

[![PyPI version](https://badge.fury.io/py/conclave.svg)](https://badge.fury.io/py/conclave)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python package for single-cell data analysis featuring multi-method clustering, consensus labeling, and automated quality assessment.

## Features

### Phase 1: Multi-Method Clustering
- ✅ **8 clustering algorithms**: PhenoGraph, FlowSOM, K-means, Leiden, Agglomerative, Birch, Affinity, MiniBatch
- ✅ **GPU acceleration**: 10-100x faster with NVIDIA RAPIDS (optional)
- ✅ **Multi-sample support**: Batch-aware normalization
- ✅ **Quality checks**: Automated validation and visualization

### Phase 2: Consensus Analysis
- ✅ **Consensus voting**: Combine multiple clustering methods
- ✅ **3D UMAP projection**: Interactive visualization with GPU support
- ✅ **Disagreement analysis**: Cell-level and sample-level flagging
- ✅ **Quality metrics**: JSD, confidence scores, spatial analysis
- ✅ **17+ visualizations**: Publication-ready plots

## Installation

### Quick Install (Most Users)

```bash
pip install conclave
```

That's it! All dependencies are installed automatically.

### Verify Installation

```bash
python -c "import conclave; print(conclave.__version__)"
# Output: 1.0.0
```

### GPU Support (Optional)

For 10-100x speedup on large datasets:

```bash
# Step 1: Install GPU packages via conda
conda install -c rapidsai -c conda-forge -c nvidia cuml=26.02 cuda-version=12.2 -y

# Step 2: Install CONCLAVE
pip install conclave

# Step 3: Verify GPU support
python -c "import cuml; print('GPU support available')"
```

**Requirements for GPU:**
- NVIDIA GPU (Compute Capability 7.0+: Volta, Turing, Ampere, or newer)
- CUDA 11.2+ or 12.x
- 8GB+ GPU memory recommended

### Alternative: Conda Environment

**For GPU users:**
```bash
# Download environment.yml from GitHub
conda env create -f environment.yml
conda activate conclave
pip install conclave
```

**For CPU-only users:**
```bash
# Download environment-cpu.yml from GitHub
conda env create -f environment-cpu.yml
conda activate conclave-cpu
pip install conclave
```

## Quick Start

### Phase 1: Clustering

```python
import pandas as pd
from conclave import run_annotation_pipeline

# Load your single-cell data
df = pd.read_csv("your_data.csv")

# Define markers
markers = ["CD3", "CD4", "CD8", "CD20", "CD45", ...]

# Run Phase 1 clustering
df_clustered, metadata = run_annotation_pipeline(
    df=df,
    markers=markers,
    outdir="./output_phase1",
    use_gpu=True,  # Set False if no GPU
    cluster_methods=("phenograph", "flowsom", "kmeans"),
    sample_size=20000,
)

print(f"✅ Clustered {len(df_clustered):,} cells")
```

**Phase 1 Outputs:**
```
output_phase1/
├── 01_normalized_full.csv
├── 02_sampled_full.csv
├── 03_clustering_annotation/
│   └── clustered_subset_with_labels_on_sampled.csv
└── 04_cluster_heatmaps/
    ├── heatmap_topN_ranked_phenograph.png
    ├── annotation_template_phenograph.csv  ← Annotate these!
    └── ...
```

### Phase 2: Consensus & Projection

After manually annotating clusters using the templates from Phase 1:

```python
from conclave import run_phase2_complete

# Run Phase 2 (annotate all 643k+ cells)
df_labeled, template, single_templates, report = run_phase2_complete()

print(f"✅ Labeled {len(df_labeled):,} cells")
print(f"Consensus confidence: {df_labeled['confidence_score'].mean():.3f}")
print(f"Disagreement: {report['full_dataset']['disagreement_pct']:.1f}%")
```

**Phase 2 Outputs:**
```
output_phase2/
├── full_dataset_labeled_complete.csv  ← All cells labeled!
├── metrics_summary.csv
├── phase2_complete_report.json
└── plots/ (17+ visualizations)
    ├── disagreement_by_sample_flagged.png
    ├── jsd_mean_per_sample_scatter.png
    ├── spatial_confidence_heatmap_tiles.png
    ├── umap_3d_consensus.png
    └── ...
```

## Documentation

- **GitHub**: https://github.com/augpath/CONCLAVE
- **Examples**: See `examples/` directory
- **Full API Docs**: https://conclave.readthedocs.io

## System Requirements

### Minimum Requirements (CPU mode)
- **OS**: Linux, macOS, or Windows (WSL2)
- **Python**: 3.8 or higher
- **RAM**: 16GB (32GB+ recommended for >100k cells)
- **Storage**: 1GB for package + data

### GPU Requirements (Optional)
- **GPU**: NVIDIA GPU with Compute Capability 7.0+
  - ✅ Volta (V100, Titan V)
  - ✅ Turing (RTX 2000 series, T4)
  - ✅ Ampere (RTX 3000 series, A100)
  - ✅ Ada Lovelace (RTX 4000 series)
- **CUDA**: 11.2+ or 12.x
- **GPU Memory**: 8GB+ recommended

## Dependencies

All dependencies are **automatically installed** with `pip install conclave`:

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

**GPU packages (optional, install separately via conda):**
- cuml (>=24.04) - GPU-accelerated ML
- cupy - GPU arrays

## Troubleshooting

### Issue: Import Error

**Problem:**
```python
ModuleNotFoundError: No module named 'pandas'
```

**Solution:**
This shouldn't happen if you installed via `pip install conclave`. If it does:
```bash
pip install --upgrade pip
pip uninstall conclave -y
pip install conclave
```

### Issue: GPU Not Working

**Problem:** GPU not detected or slow performance

**Solution:**
```bash
# Check if cuML is installed
python -c "import cuml; print('cuML OK')"

# If not installed:
conda install -c rapidsai cuml=26.02 cuda-version=12.2 -y
```

### Issue: Slow Performance

**Tips:**
- Use GPU acceleration (10-100x faster)
- Reduce `sample_size` parameter (default 20000)
- Use fewer clustering methods
- Increase RAM allocation

## Citation

If you use CONCLAVE in your research, please cite:

```
[Citation information to be added upon publication]
```

## License

MIT License - see [LICENSE](https://github.com/augpath/CONCLAVE/blob/main/LICENSE) file

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

See [CONTRIBUTING.md](https://github.com/augpath/CONCLAVE/blob/main/CONTRIBUTING.md) for details.

## Support

- **Issues**: https://github.com/augpath/CONCLAVE/issues
- **Discussions**: https://github.com/augpath/CONCLAVE/discussions
- **Email**: conclave@example.com

## Changelog

See [CHANGELOG.md](https://github.com/augpath/CONCLAVE/blob/main/CHANGELOG.md) for version history.

## Acknowledgments

Developed by the CONCLAVE Development Team.

Special thanks to:
- RAPIDS AI team for cuML
- UMAP developers
- PhenoGraph developers
- All contributors
