import { useState } from "react";
import { startPhase1, type Phase1Request, type UploadResponse } from "../api";

interface Props {
  upload: UploadResponse;
  onStarted: (jobId: string) => void;
}

const NON_MARKER_HINT = ["OID", "X", "Y", "ID", "AID", "cell_id"];
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

export default function Phase1ConfigStep({ upload, onStarted }: Props) {
  const [markers, setMarkers] = useState<Set<string>>(
    new Set(upload.columns.filter((c) => !NON_MARKER_HINT.includes(c)))
  );
  const [sampleCols, setSampleCols] = useState<Set<string>>(new Set());
  const [normalization, setNormalization] = useState("z-score");
  const [sampling, setSampling] = useState("stratified-notproportional");
  const [sampleSize, setSampleSize] = useState(20000);
  const [drMethod, setDrMethod] = useState("none");
  const [clusterMethods, setClusterMethods] = useState<Set<string>>(
    new Set(["phenograph", "kmeans"])
  );
  const [phenographK, setPhenographK] = useState(25);
  const [flowsomRscript, setFlowsomRscript] = useState("");
  const [depecheRscript, setDepecheRscript] = useState("");
  const [seed, setSeed] = useState(42);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(set: Set<string>, setSet: (s: Set<string>) => void, item: string) {
    const next = new Set(set);
    if (next.has(item)) next.delete(item);
    else next.add(item);
    setSet(next);
  }

  const usesDerivedNClusters = [...clusterMethods].some((m) => NEEDS_DERIVED_N_CLUSTERS.has(m));
  const needsPhenographForDerive = usesDerivedNClusters && !clusterMethods.has("phenograph");

  async function handleSubmit() {
    setError(null);
    if (markers.size === 0) {
      setError("Select at least one marker.");
      return;
    }
    if (clusterMethods.size === 0) {
      setError("Select at least one clustering method.");
      return;
    }
    setBusy(true);
    try {
      const req: Phase1Request = {
        upload_id: upload.upload_id,
        markers: [...markers],
        sample_cols: [...sampleCols],
        normalization: normalization === "none" ? null : normalization,
        sampling,
        sample_size: sampleSize,
        n_tiles_per_axis: 4,
        dr_method: drMethod === "none" ? null : drMethod,
        dr_n_components: 15,
        cluster_methods: [...clusterMethods],
        phenograph_k: phenographK,
        derive_kmeans_from: usesDerivedNClusters ? "phenograph" : null,
        flowsom_rscript: clusterMethods.has("flowsom") ? flowsomRscript || null : null,
        depeche_rscript: clusterMethods.has("depeche") ? depecheRscript || null : null,
        seed,
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
        <legend>Markers ({markers.size} selected)</legend>
        <div className="chip-grid">
          {upload.columns.map((col) => (
            <label key={col} className={`chip ${markers.has(col) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={markers.has(col)}
                onChange={() => toggle(markers, setMarkers, col)}
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
            <label key={col} className={`chip ${sampleCols.has(col) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={sampleCols.has(col)}
                onChange={() => toggle(sampleCols, setSampleCols, col)}
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
            <select value={normalization} onChange={(e) => setNormalization(e.target.value)}>
              {NORMALIZATION_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sampling mode
            <select value={sampling} onChange={(e) => setSampling(e.target.value)}>
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
              value={sampleSize}
              min={100}
              onChange={(e) => setSampleSize(Number(e.target.value))}
            />
          </label>
          <label>
            Dimensionality reduction
            <select value={drMethod} onChange={(e) => setDrMethod(e.target.value)}>
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
              value={phenographK}
              min={2}
              onChange={(e) => setPhenographK(Number(e.target.value))}
            />
          </label>
          <label>
            Random seed
            <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>Clustering methods ({clusterMethods.size} selected)</legend>
        <div className="chip-grid">
          {CLUSTER_METHOD_OPTIONS.map((m) => (
            <label key={m} className={`chip ${clusterMethods.has(m) ? "chip-on" : ""}`}>
              <input
                type="checkbox"
                checked={clusterMethods.has(m)}
                onChange={() => toggle(clusterMethods, setClusterMethods, m)}
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
        {clusterMethods.has("flowsom") && (
          <label className="full-width">
            FlowSOM R script path (leave blank to use the bundled one)
            <input
              type="text"
              value={flowsomRscript}
              onChange={(e) => setFlowsomRscript(e.target.value)}
              placeholder="/path/to/flowsom_clustering.R"
            />
          </label>
        )}
        {clusterMethods.has("depeche") && (
          <label className="full-width">
            DepecheR R script path (leave blank to use the bundled one)
            <input
              type="text"
              value={depecheRscript}
              onChange={(e) => setDepecheRscript(e.target.value)}
              placeholder="/path/to/depeche_clustering.R"
            />
          </label>
        )}
        {(clusterMethods.has("flowsom") || clusterMethods.has("depeche")) && (
          <p className="muted">
            Requires R and the FlowSOM/DepecheR R packages installed in the backend container —
            see the GUI README.
          </p>
        )}
      </fieldset>

      {error && <p className="error">Error: {error}</p>}
      <button disabled={busy} onClick={handleSubmit}>
        {busy ? "Starting…" : "Run Phase 1"}
      </button>
    </div>
  );
}
