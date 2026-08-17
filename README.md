# CONCLAVE: CONsensus CLustering with Annotation-Validation Extrapolation for spatial proteomics data

[![PyPI version](https://badge.fury.io/py/conclave.svg)](https://badge.fury.io/py/conclave)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python package for single-cell data analysis featuring multi-method clustering, consensus labeling, and automated quality assessment.
![Logo](CONCLAVE_logo.png)
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

**Resuming and starting fresh.** `run_annotation_pipeline_with_resume()` defaults to
`resume=True` — re-running with the same `outdir` skips whatever's already completed and only
runs what's new or missing (e.g. you add a clustering method, only that method runs). Pass
`force_restart=True` to ignore all existing checkpoints in `outdir` and start completely from
scratch instead.

**If one clustering method fails, the others aren't lost.** A single method failing (e.g. R
isn't installed for `flowsom`/`depeche`) doesn't abort the whole clustering step; it's
logged clearly, skipped, and the remaining methods still run and get saved. Check
`metadata["results"]["failed_methods"]` (or the final log summary, which shows
`⚠️ PIPELINE COMPLETE -- WITH FAILURES` instead of a clean `✅` when this happens) for what
failed and why. Fix the issue and re-run with `resume=True` (the default) to retry just the
failed method(s) — no need to redo anything that already succeeded.

For a guided, runnable walkthrough (including how to pick markers by inspecting your own CSV, and every normalization/sampling/DR/clustering option with its hyperparameters), see [`notebooks/CONCLAVE_Phase1.ipynb`](notebooks/CONCLAVE_Phase1.ipynb) and [`notebooks/CONCLAVE_Phase1_Reference.ipynb`](notebooks/CONCLAVE_Phase1_Reference.ipynb) in this repo. For Phase 2, see [`notebooks/CONCLAVE_Phase2.ipynb`](notebooks/CONCLAVE_Phase2.ipynb), which includes pre-flight validation of your annotation files.

Prefer plain scripts over notebooks? See [`examples/`](examples/): `run_phase1.py`, `run_phase2.py`
(auto-generates placeholder annotations if you haven't annotated yet, so it's runnable
end-to-end out of the box and clearly not real biology, just for seeing the pipeline run), and
`run_full_pipeline.py` (chains both). Includes a real 71MB sample dataset
(`Melanoma_example.csv`) to try them against immediately.

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
│   ├── annotation_template_<method>.csv
│   ├── cluster_topN_wide_<method>.csv
│   ├── cluster_topN_long_<method>.csv
│   └── cluster_sizes_<method>.csv
├── annotations/
│   └── annotation_template_<method>.csv  ← Annotate these! Auto-copied from
│                                            04_cluster_heatmaps/ above, ready to
│                                            edit -- re-running Phase 1 (e.g. via
│                                            resume) never overwrites a file
│                                            already here, so in-progress edits
│                                            are safe
├── pipeline_run_config.json         (full record of parameters used)
└── pipeline_log.txt
```

### Phase 2: Consensus & Projection

After manually annotating clusters (fill in the `annotation` column of each file in
`output_phase1/annotations/` and save):

```python
from conclave.phase2.pipeline_complete import run_phase2_complete

df_labeled, template, single_templates, report = run_phase2_complete(
    phase1_output="./output_phase1",
    phase2_output="./output_phase2",
    knn_k=25,
    # annotations_dir not passed -- defaults to output_phase1/annotations
    # consensus_methods not passed -- auto-detected from whichever files in
    #   there are actually filled in (non-blank 'annotation' column); if
    #   you clustered with 5 methods but only annotated 3, those 3 are used
    # markers not passed -- auto-loaded from output_phase1/pipeline_run_config.json,
    #   so Phase 2 automatically uses the same markers Phase 1 was run with
)

print(f"✅ Labeled {len(df_labeled):,} cells")
print(f"Consensus confidence: {df_labeled['confidence_score'].mean():.3f}")
```

Everything above is optional and independently overridable. Pass `annotations_dir=...` to point
elsewhere, or `consensus_methods=[...]` to pick a specific subset regardless of what's been
annotated (e.g. you've annotated all 5 methods but only want 3 in the consensus vote) — an
explicit `consensus_methods` always wins over auto-detection. Same for `markers=[...]` overriding
the auto-loaded marker list.

<details>
<summary>Older module-attribute pattern (still supported, for existing code)</summary>

```python
import conclave.phase2.pipeline_complete as p2

p2.PHASE1_OUTPUT = "./output_phase1"
p2.PHASE2_OUTPUT = "./output_phase2"
p2.KNN_K = 25

df_labeled, template, single_templates, report = p2.run_phase2_complete()
```


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
</details>
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


```
[Citation information to be added upon publication]
```

## License

MIT License - see [LICENSE](https://github.com/augpath/CONCLAVE/blob/main/LICENSE) file

See [CONTRIBUTING.md](https://github.com/augpath/CONCLAVE/blob/main/CONTRIBUTING.md) for details.

## Support

- **Issues**: https://github.com/augpath/CONCLAVE/issues
- **Discussions**: https://github.com/augpath/CONCLAVE/discussions
- **Email**: pouya.nazari@student.kuleuven.be

## Changelog

See [CHANGELOG.md](https://github.com/augpath/CONCLAVE/blob/main/CHANGELOG.md) for version history.

## Acknowledgments

Special thanks to:
- RAPIDS AI team for cuML
- All contributors
