import { useEffect, useState } from "react";
import { listPhase2Plots, plotUrl, downloadUrl, type JobStatus } from "../api";

interface Props {
  jobId: string;
  job: JobStatus;
}

export default function Phase2ResultsStep({ jobId, job }: Props) {
  const [plots, setPlots] = useState<string[]>([]);

  useEffect(() => {
    listPhase2Plots(jobId).then((d) => setPlots(d.plots));
  }, [jobId]);

  const r = job.result as {
    n_cells?: number;
    mean_confidence?: number;
    high_confidence_pct?: number;
    full_disagreement_pct?: number;
    consensus_label_counts?: Record<string, number>;
  };

  return (
    <div className="card">
      <h2>5. Phase 2 results</h2>

      <div className="stat-grid">
        <div className="stat">
          <span className="stat-value">{r.n_cells?.toLocaleString() ?? "—"}</span>
          <span className="stat-label">cells labeled</span>
        </div>
        <div className="stat">
          <span className="stat-value">{r.mean_confidence?.toFixed(3) ?? "—"}</span>
          <span className="stat-label">mean confidence</span>
        </div>
        <div className="stat">
          <span className="stat-value">{r.high_confidence_pct?.toFixed(1) ?? "—"}%</span>
          <span className="stat-label">high confidence (&gt;0.8)</span>
        </div>
        <div className="stat">
          <span className="stat-value">{r.full_disagreement_pct?.toFixed(1) ?? "—"}%</span>
          <span className="stat-label">full disagreement</span>
        </div>
      </div>

      {r.consensus_label_counts && (
        <>
          <h3>Consensus label distribution</h3>
          <table className="ann-table">
            <tbody>
              {Object.entries(r.consensus_label_counts)
                .sort((a, b) => b[1] - a[1])
                .map(([label, count]) => (
                  <tr key={label}>
                    <td>{label}</td>
                    <td>{count.toLocaleString()}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </>
      )}

      <a href={downloadUrl(jobId)} download>
        <button>Download full_dataset_labeled_complete.csv</button>
      </a>

      <h3>Plots</h3>
      <div className="plot-grid">
        {plots.map((p) => (
          <div key={p} className="plot-item">
            <img src={plotUrl(jobId, p)} alt={p} />
            <span>{p}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
