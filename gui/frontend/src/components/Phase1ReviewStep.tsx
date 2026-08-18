import { useEffect, useRef, useState } from "react";
import {
  getPhase1Clusters,
  heatmapUrl,
  saveAnnotations,
  uploadAnnotations,
  type ClustersResponse,
} from "../api";

interface Props {
  jobId: string;
  onContinue: (annotatedMethods: string[]) => void;
  onBack: () => void;
}

type AnnotationMode = "browser" | "upload";

export default function Phase1ReviewStep({ jobId, onContinue, onBack }: Props) {
  const [data, setData] = useState<ClustersResponse | null>(null);
  const [activeMethod, setActiveMethod] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, Record<string, string>>>({});
  const [modes, setModes] = useState<Record<string, AnnotationMode>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getPhase1Clusters(jobId).then((d) => {
      setData(d);
      setActiveMethod(d.methods[0] ?? null);
      const initialEdits: Record<string, Record<string, string>> = {};
      const initialModes: Record<string, AnnotationMode> = {};
      for (const m of d.methods) {
        initialEdits[m] = {};
        for (const row of d.clusters[m]) {
          initialEdits[m][String(row.cluster_id)] = row.annotation;
        }
        initialModes[m] = "browser";
      }
      setEdits(initialEdits);
      setModes(initialModes);
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

  function markAnnotated(method: string) {
    setData((prev) =>
      prev ? { ...prev, annotated_methods: [...new Set([...prev.annotated_methods, method])] } : prev
    );
  }

  async function handleSave(method: string) {
    setSaving(true);
    setError(null);
    setSavedFlash(null);
    try {
      const res = await saveAnnotations(jobId, method, edits[method]);
      setSavedFlash(`Saved ${res.n_annotated}/${res.n_clusters} annotated clusters for ${method}`);
      markAnnotated(method);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleFileUpload(method: string, file: File) {
    setSaving(true);
    setError(null);
    setSavedFlash(null);
    try {
      const res = await uploadAnnotations(jobId, method, file);
      setSavedFlash(`Uploaded: ${res.n_annotated}/${res.n_clusters} annotated clusters for ${method}`);
      markAnnotated(method);
      // refresh the table from what was actually saved, so it reflects the upload
      const refreshed = await getPhase1Clusters(jobId);
      setData(refreshed);
      setEdits((prev) => {
        const next = { ...prev };
        next[method] = {};
        for (const row of refreshed.clusters[method]) {
          next[method][String(row.cluster_id)] = row.annotation;
        }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function csvEscape(value: string): string {
    if (/[",\n]/.test(value)) {
      return `"${value.replace(/"/g, '""')}"`;
    }
    return value;
  }

  function handleDownloadTemplate(method: string) {
    const methodRows = data!.clusters[method];
    const methodEdits = edits[method] ?? {};
    const header = "cluster_id,n_cells,annotation";
    const lines = methodRows.map((row) => {
      const annotation = methodEdits[String(row.cluster_id)] ?? row.annotation ?? "";
      return [row.cluster_id, row.n_cells, csvEscape(annotation)].join(",");
    });
    const csv = [header, ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `annotation_template_${method}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const rows = data.clusters[activeMethod];
  const mode = modes[activeMethod] ?? "browser";

  return (
    <div className="card">
      <h2>3. Review clusters &amp; annotate</h2>
      <p className="muted">
        For each method, either annotate clusters here using the heatmap, or upload a CSV you
        already annotated separately (offline, or by someone else). You need at least 2
        saved-and-annotated methods to run Phase 2 (for majority voting).
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

      <div className="mode-toggle">
        <button
          className={`tab ${mode === "browser" ? "tab-active" : ""}`}
          onClick={() => setModes((prev) => ({ ...prev, [activeMethod]: "browser" }))}
        >
          Annotate here
        </button>
        <button
          className={`tab ${mode === "upload" ? "tab-active" : ""}`}
          onClick={() => setModes((prev) => ({ ...prev, [activeMethod]: "upload" }))}
        >
          Upload annotated CSV
        </button>
        <button className="secondary" onClick={() => handleDownloadTemplate(activeMethod)}>
          ⬇ Download {activeMethod} template
        </button>
      </div>

      {mode === "browser" && (
        <>
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

          <button disabled={saving} onClick={() => handleSave(activeMethod)}>
            {saving ? "Saving…" : `Save ${activeMethod} annotations`}
          </button>
        </>
      )}

      {mode === "upload" && (
        <div className="upload-annotations">
          <p className="muted">
            CSV must have <code>cluster_id</code> and <code>annotation</code> columns, with
            cluster_ids matching this method's actual clusters (
            {rows.map((r) => r.cluster_id).join(", ")}). Use the "Download {activeMethod} template"
            button above to get a correctly-formatted starting point.
          </p>
          <img className="heatmap-img" src={heatmapUrl(jobId, activeMethod)} alt={`${activeMethod} heatmap`} />
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            disabled={saving}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleFileUpload(activeMethod, f);
            }}
          />
          {saving && <p>Uploading…</p>}
        </div>
      )}

      {error && <p className="error">Error: {error}</p>}
      {savedFlash && <p className="ok">{savedFlash}</p>}

      <hr />
      <p>Methods saved so far: {data.annotated_methods.join(", ") || "none yet"}</p>
      <div className="button-row">
        <button className="secondary" onClick={onBack}>
          ← Back
        </button>
        <button
          disabled={data.annotated_methods.length < 2}
          onClick={() => onContinue(data.annotated_methods)}
        >
          Continue to Phase 2 →
        </button>
      </div>
      {data.annotated_methods.length < 2 && (
        <p className="muted">Save at least 2 methods' annotations to continue.</p>
      )}
    </div>
  );
}
