#!/usr/bin/env Rscript
# CONCLAVE FlowSOM clustering script
#
# Contract expected by conclave.phase1.clustering.cluster_r_labels():
#   1. Read the CSV at the path given as the first CLI argument.
#   2. Add a "flowsom" column with integer cluster labels.
#   3. Write the result back to the SAME path.
#   4. Stay silent on stdout (only write to stderr on error).
#
# Requires the Bioconductor FlowSOM package:
#   BiocManager::install("FlowSOM")
#
# Defaults below match the CONCLAVE manuscript's resubmission
# (maxMeta=40, 10x10 SOM grid) -- see the parameter sensitivity sweep
# in the supplementary materials.

suppressPackageStartupMessages({
  library(FlowSOM)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript flowsom_clustering.R <csv_path> [maxMeta] [xdim] [ydim] [seed]")
}
csv_path <- args[1]
maxMeta  <- if (length(args) >= 2) as.integer(args[2]) else 40L
xdim     <- if (length(args) >= 3) as.integer(args[3]) else 10L
ydim     <- if (length(args) >= 4) as.integer(args[4]) else 10L
seed     <- if (length(args) >= 5) as.integer(args[5]) else 42L

set.seed(seed)

df <- read.csv(csv_path, check.names = FALSE)

# cluster_r_labels() passes a "cell_id" column plus one column per marker --
# everything except cell_id is treated as a clustering feature.
marker_cols <- setdiff(colnames(df), "cell_id")
X <- as.matrix(df[, marker_cols, drop = FALSE])

ff <- flowCore::flowFrame(X)

fsom <- FlowSOM(
  ff,
  colsToUse = marker_cols,
  xdim = xdim,
  ydim = ydim,
  nClus = maxMeta,
  seed = seed
)

# Metaclustering (consensus hierarchical clustering on the SOM grid) up to maxMeta
meta <- metaClustering_consensus(fsom$FlowSOM$map$codes, k = maxMeta, seed = seed)
cluster_labels <- meta[fsom$FlowSOM$map$mapping[, 1]]

df$flowsom <- as.integer(cluster_labels)
write.csv(df, csv_path, row.names = FALSE)
