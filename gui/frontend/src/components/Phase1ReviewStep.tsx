import { useEffect, useState } from "react";
import {
  getPhase1Clusters,
  heatmapUrl,
  saveAnnotations,
  type ClustersResponse,
} from "../api";

interface Props {
  jobId: string;
  onContinue: (annotatedMethods: string[]) => void;
}

export default function Phase1ReviewStep({ jobId, onContinue }: Props) {
  const [data, setData] = useState<ClustersResponse | null>(null);
  const [activeMethod, setActiveMethod] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, Record<string, string>>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState<string | null>(null);

  useEffect(() => {
    getPhase1Clusters(jobId).then((d) => {
      setData(d);
      setActiveMethod(d.methods[0] ?? null);
      const initialEdits: Record<string, Record<string, string>> = {};
      for (const m of d.methods) {
        initialEdits[m] = {};
        for (const row of d.clusters[m]) {
          initialEdits[m][String(row.cluster_id)] = row.annotation;
        }
      }
      setEdits(initialEdits);
    });
  }, [jobId]);

  if (!data || !activeMethod) {
    return (
      <div className="card">
        <h2>3. Review clusters &amp; annotate</h2>
        <p>Loading…</p>
      </div>
    );
  }

  function setCell(method: string, clusterId: string, value: string) {
    setEdits((prev) => ({
      ...prev,
      [method]: { ...prev[method], [clusterId]: value },
    }));
  }

  async function handleSave(method: string) {
    setSaving(true);
    setError(null);
    setSavedFlash(null);
    try {
      const res = await saveAnnotations(jobId, method, edits[method]);
      setSavedFlash(`Saved ${res.n_annotated}/${res.n_clusters} annotated clusters for ${method}`);
      setData((prev) =>
        prev ? { ...prev, annotated_methods: [...new Set([...prev.annotated_methods, method])] } : prev
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  const rows = data.clusters[activeMethod];

  return (
    <div className="card">
      <h2>3. Review clusters &amp; annotate</h2>
      <p className="muted">
        For each method, look at the heatmap to identify cell types, type a label per cluster,
        then save. You need at least 2 saved-and-annotated methods to run Phase 2 (for majority
        voting).
      </p>

      <div className="tab-bar">
        {data.methods.map((m) => (
          <button
            key={m}
            className={`tab ${m === activeMethod ? "tab-active" : ""}`}
            onClick={() => setActiveMethod(m)}
          >
            {m} {data.annotated_methods.includes(m) ? "✓" : ""}
          </button>
        ))}
      </div>

      <img className="heatmap-img" src={heatmapUrl(jobId, activeMethod)} alt={`${activeMethod} heatmap`} />

      <table className="ann-table">
        <thead>
          <tr>
            <th>Cluster</th>
            <th>Cells</th>
            <th>Annotation</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.cluster_id}>
              <td>{row.cluster_id}</td>
              <td>{row.n_cells.toLocaleString()}</td>
              <td>
                <input
                  type="text"
                  value={edits[activeMethod]?.[String(row.cluster_id)] ?? ""}
                  onChange={(e) => setCell(activeMethod, String(row.cluster_id), e.target.value)}
                  placeholder="e.g. T cells"
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {error && <p className="error">Error: {error}</p>}
      {savedFlash && <p className="ok">{savedFlash}</p>}
      <button disabled={saving} onClick={() => handleSave(activeMethod)}>
        {saving ? "Saving…" : `Save ${activeMethod} annotations`}
      </button>

      <hr />
      <p>Methods saved so far: {data.annotated_methods.join(", ") || "none yet"}</p>
      <button
        disabled={data.annotated_methods.length < 2}
        onClick={() => onContinue(data.annotated_methods)}
      >
        Continue to Phase 2 →
      </button>
      {data.annotated_methods.length < 2 && (
        <p className="muted">Save at least 2 methods' annotations to continue.</p>
      )}
    </div>
  );
}
