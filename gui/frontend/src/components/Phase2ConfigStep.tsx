import { useState } from "react";
import { startPhase2, type Phase2Request } from "../api";

interface Props {
  phase1JobId: string;
  annotatedMethods: string[];
  sampleColsUsedInPhase1: string[];
  onStarted: (jobId: string) => void;
}

export default function Phase2ConfigStep({
  phase1JobId,
  annotatedMethods,
  sampleColsUsedInPhase1,
  onStarted,
}: Props) {
  const [methods, setMethods] = useState<Set<string>>(new Set(annotatedMethods));
  const [knnK, setKnnK] = useState(25);
  const [minVotes, setMinVotes] = useState(2);
  const [templateMax, setTemplateMax] = useState(500);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(item: string) {
    const next = new Set(methods);
    if (next.has(item)) next.delete(item);
    else next.add(item);
    setMethods(next);
  }

  async function handleSubmit() {
    setError(null);
    if (methods.size < 2) {
      setError("Select at least 2 methods for majority-vote consensus.");
      return;
    }
    setBusy(true);
    try {
      const req: Phase2Request = {
        phase1_job_id: phase1JobId,
        methods: [...methods],
        knn_k: knnK,
        min_votes: minVotes,
        sample_cols: sampleColsUsedInPhase1,
        template_max_per_label: templateMax,
      };
      const { job_id } = await startPhase2(req);
      onStarted(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>4. Configure Phase 2</h2>
      <p className="muted">
        Consensus voting across your annotated methods, then projection onto your full dataset
        with confidence/disagreement flagging. This runs on your <em>full</em> uploaded file, so
        it can take several minutes.
      </p>

      <fieldset>
        <legend>Methods to include in consensus</legend>
        <div className="chip-grid">
          {annotatedMethods.map((m) => (
            <label key={m} className={`chip ${methods.has(m) ? "chip-on" : ""}`}>
              <input type="checkbox" checked={methods.has(m)} onChange={() => toggle(m)} />
              {m}
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset>
        <legend>Parameters</legend>
        <div className="form-grid">
          <label>
            KNN k
            <input type="number" value={knnK} min={1} onChange={(e) => setKnnK(Number(e.target.value))} />
          </label>
          <label>
            Min votes for consensus
            <input
              type="number"
              value={minVotes}
              min={1}
              max={methods.size || 1}
              onChange={(e) => setMinVotes(Number(e.target.value))}
            />
          </label>
          <label>
            Max cells per label in template
            <input
              type="number"
              value={templateMax}
              min={10}
              onChange={(e) => setTemplateMax(Number(e.target.value))}
            />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">Error: {error}</p>}
      <button disabled={busy} onClick={handleSubmit}>
        {busy ? "Starting…" : "Run Phase 2"}
      </button>
    </div>
  );
}
