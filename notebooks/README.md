# CONCLAVE Notebooks

- **`CONCLAVE_Phase1.ipynb`** — run Phase 1 (normalize → sample → cluster → export
  annotation templates) on your own data. Set `CSV_PATH`, pick markers from what's
  found in your file, configure the pipeline (recommended defaults shown inline),
  run, and review the output heatmaps.

- **`CONCLAVE_Phase1_Reference.ipynb`** — options catalog. Runs every normalization
  method (including the two IQR-based ones), every sampling mode, and every
  dimensionality-reduction method side-by-side against a slice of your data, with
  each hyperparameter explained. Use this to decide what to actually use in the
  notebook above, not as a run-and-forget pipeline.

Both require R + the FlowSOM/DepecheR R packages installed separately if you want
to use those two clustering methods — see `conclave/r_scripts/` for the bundled
scripts (path auto-detected in the notebooks, no copy-pasting needed).
