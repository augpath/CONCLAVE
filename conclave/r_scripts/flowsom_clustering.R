library(FlowSOM)
library(magrittr)
library(dplyr)

# ---------------------------------------------------------------------------
# flowsom_clustering.R  –  FlowSOM runner for the CONCLAVE pipeline
#
# Parameters (see function default below), also cross-checked against the
# sensitivity analysis in the CONCLAVE manuscript's supplementary materials:
#   maxMeta = 50   (cap on number of metaclusters)
#   xdim    = 10   (SOM grid x dimension)
#   ydim    = 10   (SOM grid y dimension)
#
# Not currently overridable from the Python side -- conclave's R bridge
# (conclave.phase1.clustering._run_rscript) only passes the CSV path as a
# CLI argument. To use different values, edit the defaults below directly.
#
# Usage: Rscript flowsom_clustering.R <input_csv>
# ---------------------------------------------------------------------------

path <- commandArgs(trailingOnly = TRUE)

Fsom = function(path, maxMeta = 50L, xdim = 10L, ydim = 10L) {
  
  dataframe = read.csv(path, stringsAsFactors = FALSE)
  
  # Remove unnamed index columns added by Python/R
  dataframe = dataframe[, !grepl("^X$|^Unnamed", colnames(dataframe))]
  
  # Strip non-marker columns before passing to FlowSOM. Filtering to
  # numeric-only columns (rather than just excluding specific names) also
  # correctly drops identifier columns like "cell_id" -- conclave's Python
  # bridge (conclave.phase1.clustering.cluster_r_labels) always includes
  # one, and leaving it in would make as.matrix() coerce the WHOLE matrix
  # to character type (R matrices are homogeneous), which then breaks the
  # left_join below with a type-mismatch error against the numeric
  # original data.
  if ('flowsom' %in% colnames(dataframe) & 'cellType' %in% colnames(dataframe)) {
    df = dataframe %>% select(-flowsom, -cellType)
  } else if ('cellType' %in% colnames(dataframe)) {
    df = dataframe %>% select(-cellType)
  } else if ('flowsom' %in% colnames(dataframe)) {
    df = dataframe %>% select(-flowsom)
  } else {
    df = dataframe
  }
  df = df %>% select(where(is.numeric))
  
  df = df %>% as.matrix()
  df = df %>% unique()
  
  # Guard: FlowSOM needs at least 50 rows
  if (nrow(df) < 50) {
    df <- df[rep(1:nrow(df), length.out = 50), , drop = FALSE]
  }
  
  # Guard: maxMeta cannot exceed number of unique rows
  effective_maxMeta <- min(maxMeta, nrow(df))
  
  # Guard: xdim * ydim must be >= effective_maxMeta
  effective_xdim <- xdim
  effective_ydim <- ydim
  while (effective_xdim * effective_ydim < effective_maxMeta) {
    effective_xdim <- effective_xdim + 1L
    effective_ydim <- effective_ydim + 1L
  }
  
  tmp_fsom = FlowSOM(
    df,
    colsToUse = colnames(df),
    xdim      = effective_xdim,
    ydim      = effective_ydim,
    maxMeta   = effective_maxMeta
  )
  
  flowsom = tmp_fsom$metaclustering[GetClusters(tmp_fsom)]
  df      = df %>% cbind(flowsom)
  
  out = suppressMessages(dataframe %>% left_join(df %>% as.data.frame()))
  
  write.csv(out, path, row.names = FALSE)
  return(path)
}

suppressMessages(cat(Fsom(path)))