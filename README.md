# CONCLAVE: CONsensus CLustering with Annotation-Validation Extrapolation for spatial proteomics data

[![PyPI version](https://badge.fury.io/py/conclave.svg)](https://badge.fury.io/py/conclave)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python package for single-cell data analysis featuring multi-method clustering, consensus labeling, and automated quality assessment.

## Features

### Phase 1: Multi-Method Clustering
- ✅ **10 native Python clustering algorithms**: PhenoGraph, K-means, MiniBatchKMeans, Leiden, Agglomerative, BIRCH, Affinity Propagation, MeanShift, DBSCAN, Spectral
- ✅ **2 R-based algorithms**: FlowSOM, DepecheR (require R + those packages installed; scripts ship with the package, path auto-detected — see Quick Start)
- ✅ **5 dimensionality-reduction options**: None (raw marker space), PCA, UMAP, PaCMAP, t-SNE
- ✅ **6 normalization methods**: None, z-score, log-normalize, min-max, IQR-based z-score, IQR-based min-max (Tukey-fence outlier handling), each optionally computed per-sample or pooled
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

> **⚠️ Not yet on PyPI.** `conclave` is already taken by an unrelated project
> (a Bitcoin-network client), so this package will need a different
> distribution name before publishing — `pip install conclave` will NOT
> install this package. Until then, install from GitHub:

### Quick Install (from GitHub)

```bash
pip install git+https://github.com/augpath/CONCLAVE.git
```

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
pip install git+https://github.com/augpath/CONCLAVE.git

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
git clone https://github.com/augpath/CONCLAVE.git
cd CONCLAVE
conda env create -f environment.yml
conda activate conclave
pip install .
```

**For CPU-only users:**
```bash
git clone https://github.com/augpath/CONCLAVE.git
cd CONCLAVE
conda env create -f environment-cpu.yml
conda activate conclave-cpu
pip install .
```

## Quick Start

### Phase 1: Clustering

```python
import pandas as pd
from conclave.phase1 import run_annotation_pipeline_with_resume

# Load your single-cell data
df = pd.read_csv("your_data.csv")

# Define the markers to cluster on
markers = ["CD3", "CD4", "CD8", "CD20", "CD45"]  # replace with your panel

# Optional: use FlowSOM/DepecheR (need R + those R packages installed separately;
# path to the bundled scripts is auto-detected, no copy-pasting needed)
import conclave.r_scripts, pathlib
r_scripts_dir = pathlib.Path(conclave.r_scripts.__file__).parent

# Run Phase 1 clustering
df_clustered, metadata = run_annotation_pipeline_with_resume(
    df=df,
    markers=markers,
    outdir="./output_phase1",
    sample_cols=["sample_id"],   # column identifying slide/sample, for batch-aware normalization; None to pool all cells
    normalization="z-score",     # or "iqr-zscore" / "iqr-minmax" for outlier-robust alternatives
    sampling="stratified-notproportional",
    sample_size=20000,
    cluster_methods=("phenograph", "kmeans"),  # add "flowsom"/"depeche" if you have R + those packages installed
    phenograph_k=25,
    derive_kmeans_from="phenograph",
    flowsom_rscript=str(r_scripts_dir / "flowsom_clustering.R"),   # only used if "flowsom" is in cluster_methods
    depeche_rscript=str(r_scripts_dir / "depeche_clustering.R"),   # only used if "depeche" is in cluster_methods
)

print(f"✅ Clustered {len(df_clustered):,} cells")
```

For a guided, runnable walkthrough (including how to pick markers by inspecting your own CSV, and every normalization/sampling/DR/clustering option with its hyperparameters), see [`notebooks/CONCLAVE_Phase1.ipynb`](notebooks/CONCLAVE_Phase1.ipynb) and [`notebooks/CONCLAVE_Phase1_Reference.ipynb`](notebooks/CONCLAVE_Phase1_Reference.ipynb) in this repo. For Phase 2, see [`notebooks/CONCLAVE_Phase2.ipynb`](notebooks/CONCLAVE_Phase2.ipynb), which includes pre-flight validation of your annotation files.

**Phase 1 Outputs:**
```
output_phase1/
├── .checkpoint_*.json                (resume support -- safe to ignore/delete)
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
│   ├── annotation_template_<method>.csv  ← Annotate these!
│   ├── cluster_topN_wide_<method>.csv
│   ├── cluster_topN_long_<method>.csv
│   └── cluster_sizes_<method>.csv
├── pipeline_run_config.json         (full record of parameters used)
└── pipeline_log.txt
```

### Phase 2: Consensus & Projection

After manually annotating clusters using the templates from Phase 1 (fill in the
`annotation` column of each `annotation_template_<method>.csv` and save it):

> **⚠️ Current limitation:** `run_phase2_complete()` does not yet accept your
> data/markers/paths as function arguments — it reads them from module-level
> variables in `conclave.phase2.pipeline_complete`. This also means
> `import conclave` currently creates `./output_phase2/` on disk using
> default settings tuned for the CONCLAVE manuscript's melanoma panel. This
> is a known issue slated for a proper kwargs-based refactor; until then,
> **every** variable below needs setting — several (`CLUSTERED_FILE`,
> `FULL_DATA_FILE`, `ANNOTATION_FILES`) are derived once from the defaults
> at import time and won't update just by changing `PHASE1_OUTPUT` /
> `ANNOTATIONS_DIR` afterward:

```python
from pathlib import Path
import conclave.phase2.pipeline_complete as p2

phase1_out = Path("./output_phase1")
phase2_out = Path("./output_phase2")
annotations_dir = Path("./annotations")  # your filled-in annotation_template_<method>.csv files, renamed/copied here

p2.PHASE1_OUTPUT = phase1_out
p2.PHASE2_OUTPUT = phase2_out
p2.ANNOTATIONS_DIR = annotations_dir

# Derived paths -- must be set explicitly, they do NOT auto-update above
p2.CLUSTERED_FILE = phase1_out / "03_clustering_annotation" / "clustered_subset_with_labels_on_sampled.csv"
p2.FULL_DATA_FILE = phase1_out / "01_normalized_full.csv"
p2.ANNOTATION_FILES = {
    "phenograph": annotations_dir / "phenograph_annotated.csv",
    "kmeans": annotations_dir / "kmeans_annotated.csv",
    # one entry per method you ran in Phase 1
}

p2.MARKERS = markers  # same marker list used in Phase 1
p2.CONSENSUS_METHODS = ["phenograph", "kmeans"]  # match what you ran in Phase 1
p2.KNN_K = 25
p2.SAMPLE_COLS = ["sample_id"]  # match what you used in Phase 1

# Output dirs are created at import time using the OLD default path --
# recreate them at your actual PHASE2_OUTPUT location
p2.PHASE2_OUTPUT.mkdir(parents=True, exist_ok=True)
(p2.PHASE2_OUTPUT / "templates").mkdir(exist_ok=True)
(p2.PHASE2_OUTPUT / "plots").mkdir(exist_ok=True)

df_labeled, template, single_templates, report = p2.run_phase2_complete()

print(f"✅ Labeled {len(df_labeled):,} cells")
print(f"Consensus confidence: {df_labeled['confidence_score'].mean():.3f}")
```

This full sequence has been verified end-to-end against real data.

**Phase 2 Outputs:**
```
output_phase2/
├── full_dataset_labeled_complete.csv  ← All cells labeled!
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

All dependencies are **automatically installed** when you install from GitHub:

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
This shouldn't happen if you installed via the command above. If it does:
```bash
pip install --upgrade pip
pip uninstall conclave -y
pip install git+https://github.com/augpath/CONCLAVE.git --no-cache-dir
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
- **Email**: (contact info to be added)

## Changelog

See [CHANGELOG.md](https://github.com/augpath/CONCLAVE/blob/main/CHANGELOG.md) for version history.

## Acknowledgments

Developed by the CONCLAVE Development Team.

Special thanks to:
- RAPIDS AI team for cuML
- UMAP developers
- PhenoGraph developers
- All contributors
