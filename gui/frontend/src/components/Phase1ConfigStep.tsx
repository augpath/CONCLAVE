import { useState } from "react";
import { startPhase1, type Phase1Request, type UploadResponse } from "../api";
import type { Phase1FormValues } from "../formTypes";

interface Props {
  upload: UploadResponse;
  values: Phase1FormValues;
  onChange: (values: Phase1FormValues) => void;
  onStarted: (jobId: string) => void;
  onBack: () => void;
}

const NORMALIZATION_OPTIONS = ["z-score", "lognorm", "minmax", "iqr-zscore", "iqr-minmax", "none"];
const SAMPLING_OPTIONS = [
  "stratified-notproportional",
  "stratified-proportional",
  "random",
  "none",
];
const DR_OPTIONS = ["none", "pca", "umap", "pacmap", "tsne"];
const CLUSTER_METHOD_OPTIONS = [
  "phenograph",
  "kmeans",
  "minibatchkmeans",
  "leiden",
  "agglomerative",
  "birch",
  "affinity",
  "meanshift",
  "dbscan",
  "spectral",
  "flowsom",
  "depeche",
];
const NEEDS_DERIVED_N_CLUSTERS = new Set([
  "kmeans",
  "minibatchkmeans",
  "agglomerative",
  "spectral",
  "birch",
]);

export default function Phase1ConfigStep({ upload, values: v, onChange, onStarted, onBack }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(patch: Partial<Phase1FormValues>) {
    onChange({ ...v, ...patch });
  }

  function toggleInList(list: string[], item: string): string[] {
    return list.includes(item) ? list.filter((x) => x !== item) : [...list, item];
  }

  const usesDerivedNClusters = v.clusterMethods.some((m) => NEEDS_DERIVED_N_CLUSTERS.has(m));
  const needsPhenographForDerive = usesDerivedNClusters && !v.clusterMethods.includes("phenograph");

  async function handleSubmit() {
    setError(null);
    if (v.markers.length === 0) {
      setError("Select at least one marker.");
      return;
    }
    if (v.clusterMethods.length === 0) {
      setError("Select at least one clustering method.");
      return;
    }
    setBusy(true);
    try {
      const req: Phase1Request = {
        upload_id: upload.upload_id,
        markers: v.markers,
        sample_cols: v.sampleCols,
        normalization: v.normalization === "none" ? null : v.normalization,
        sampling: v.sampling,
        sample_size: v.sampleSize,
        n_tiles_per_axis: 4,
        dr_method: v.drMethod === "none" ? null : v.drMethod,
        dr_n_components: 15,
        cluster_methods: v.clusterMethods,
        phenograph_k: v.phenographK,
        derive_kmeans_from: usesDerivedNClusters ? "phenograph" : null,
        flowsom_rscript: v.clusterMethods.includes("flowsom") ? v.flowsomRscript || null : null,
        depeche_rscript: v.clusterMethods.includes("depeche") ? v.depecheRscript || null : null,
        seed: v.seed,
        outdir: v.outdir.trim() || null,
        force_restart: v.forceRestart,
      };
      const { job_id } = await startPhase1(req);
      onStarted(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>2. Configure Phase 1</h2>

      <fieldset>
        <legend>Markers ({v.markers.length} selected)</legend>
        <div className="chip-grid">
          {upload.columns.map((col) => (
            <label key={col} className={`chip ${v.markers.includes(col) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={v.markers.includes(col)}
                onChange={() => update({ markers: toggleInList(v.markers, col) })}
              />
              {col}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Sample / batch column(s) (optional)</legend>
        <p className="muted">
          For batch-aware normalization across multiple slides/samples. Leave unselected to
          normalize all cells as one group.
        </p>
        <div className="chip-grid">
          {upload.columns.map((col) => (
            <label key={col} className={`chip ${v.sampleCols.includes(col) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={v.sampleCols.includes(col)}
                onChange={() => update({ sampleCols: toggleInList(v.sampleCols, col) })}
              />
              {col}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Pipeline</legend>
        <div className="form-grid">
          <label>
            Normalization
            <select value={v.normalization} onChange={(e) => update({ normalization: e.target.value })}>
              {NORMALIZATION_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sampling mode
            <select value={v.sampling} onChange={(e) => update({ sampling: e.target.value })}>
              {SAMPLING_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sample size
            <input
              type="number"
              value={v.sampleSize}
              min={100}
              onChange={(e) => update({ sampleSize: Number(e.target.value) })}
            />
          </label>
          <label>
            Dimensionality reduction
            <select value={v.drMethod} onChange={(e) => update({ drMethod: e.target.value })}>
              {DR_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label>
            PhenoGraph k
            <input
              type="number"
              value={v.phenographK}
              min={2}
              onChange={(e) => update({ phenographK: Number(e.target.value) })}
            />
          </label>
          <label>
            Random seed
            <input type="number" value={v.seed} onChange={(e) => update({ seed: Number(e.target.value) })} />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Output &amp; resuming</legend>
        <div className="form-grid">
          <label className="full-width">
            Output directory (optional)
            <input
              type="text"
              value={v.outdir}
              onChange={(e) => update({ outdir: e.target.value })}
              placeholder="leave blank to use an auto-generated location"
            />
            <span className="field-hint">
              If running via Docker, this must be under /data (the mounted volume) to be visible
              on your host machine and survive container restarts -- e.g. /data/my_run. A path
              outside /data still writes successfully but is invisible outside the container.
            </span>
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={v.forceRestart}
              onChange={(e) => update({ forceRestart: e.target.checked })}
            />
            Force restart (ignore any existing checkpoints in the output directory above)
          </label>
        </div>
        {!v.forceRestart && (
          <p className="muted">
            Resuming: if the output directory already has a completed or partial Phase 1 run,
            already-finished steps/methods are skipped and only what's new or missing runs.
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend>Clustering methods ({v.clusterMethods.length} selected)</legend>
        <div className="chip-grid">
          {CLUSTER_METHOD_OPTIONS.map((m) => (
            <label key={m} className={`chip ${v.clusterMethods.includes(m) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={v.clusterMethods.includes(m)}
                onChange={() => update({ clusterMethods: toggleInList(v.clusterMethods, m) })}
              />
              {m}
            </label>
          ))}
        </div>
        {needsPhenographForDerive && (
          <p className="warn">
            kmeans/minibatchkmeans/agglomerative/spectral/birch derive their cluster count from
            PhenoGraph — add "phenograph" too, or they'll fail.
          </p>
        )}
        {v.clusterMethods.includes("flowsom") && (
          <label className="full-width">
            FlowSOM R script path (leave blank to use the bundled one)
            <input
              type="text"
              value={v.flowsomRscript}
              onChange={(e) => update({ flowsomRscript: e.target.value })}
              placeholder="/path/to/flowsom_clustering.R"
            />
          </label>
        )}
        {v.clusterMethods.includes("depeche") && (
          <label className="full-width">
            DepecheR R script path (leave blank to use the bundled one)
            <input
              type="text"
              value={v.depecheRscript}
              onChange={(e) => update({ depecheRscript: e.target.value })}
              placeholder="/path/to/depeche_clustering.R"
            />
          </label>
        )}
        {(v.clusterMethods.includes("flowsom") || v.clusterMethods.includes("depeche")) && (
          <p className="muted">
            Requires R and the FlowSOM/DepecheR R packages installed in the backend container —
            see the GUI README.
          </p>
        )}
      </fieldset>

      {error && <p className="error">Error: {error}</p>}
      <div className="button-row">
        <button className="secondary" disabled={busy} onClick={onBack}>
          ← Back
        </button>
        <button disabled={busy} onClick={handleSubmit}>
          {busy ? "Starting…" : "Run Phase 1"}
        </button>
      </div>
    </div>
  );
}
