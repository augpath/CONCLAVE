library(DepecheR)
library(magrittr)
library(dplyr)

# ---------------------------------------------------------------------------
# depeche_clustering.R  -  DepecheR runner for the CONCLAVE pipeline
#
# Usage: Rscript depeche_clustering.R <input_csv>
#
# Not currently overridable from the Python side -- conclave's R bridge
# (conclave.phase1.clustering._run_rscript) only passes the CSV path as a
# CLI argument.
# ---------------------------------------------------------------------------

path <- commandArgs(trailingOnly = TRUE)

Depech = function(path) {
  dataframe = read.csv(path, stringsAsFactors = FALSE)

  df = dataframe %>%
    select(where(is.numeric)) %>%
    select(-any_of(c("depeche", "cellType", "UMAP_1", "UMAP_2", "dr1", "dr2"))) %>%
    unique()

  result <- depeche(df %>% as.matrix())

  # Map cluster labels back onto every original row (including any rows
  # that were removed as duplicates above) by matching on shared marker
  # columns -- mirrors flowsom_clustering.R's join pattern. Directly
  # mutating dataframe with result$clusterVector (the previous approach)
  # silently assumed row-for-row alignment between the deduplicated
  # clustering input and the full original data, which breaks (errors, or
  # in older dplyr versions, silently misassigns labels) whenever any
  # duplicate marker rows exist.
  df = df %>% cbind(depeche = result$clusterVector)
  out = suppressMessages(dataframe %>% left_join(df %>% as.data.frame()))

  write.csv(out, path, row.names = FALSE)
  return(path)
}

cat(Depech(path))
