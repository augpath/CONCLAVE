#!/usr/bin/env Rscript
# CONCLAVE DepecheR clustering script
#
# Contract expected by conclave.phase1.clustering.cluster_r_labels():
#   1. Read the CSV at the path given as the first CLI argument.
#   2. Add a "depeche" column with integer cluster labels.
#   3. Write the result back to the SAME path.
#   4. Stay silent on stdout (only write to stderr on error).
#
# Requires the Bioconductor DepecheR package:
#   BiocManager::install("DepecheR")

suppressPackageStartupMessages({
  library(DepecheR)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 1) {
  stop("Usage: Rscript depeche_clustering.R <csv_path> [seed]")
}
csv_path <- args[1]
seed     <- if (length(args) >= 2) as.integer(args[2]) else 42L

set.seed(seed)

df <- read.csv(csv_path, check.names = FALSE)
marker_cols <- setdiff(colnames(df), "cell_id")
X <- as.matrix(df[, marker_cols, drop = FALSE])

result <- depeche(X, maxIter = 100)

df$depeche <- as.integer(result$clusterVector)
write.csv(df, csv_path, row.names = FALSE)
