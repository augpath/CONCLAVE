import { useState } from "react";
import { startPhase2, type Phase2Request } from "../api";
import type { Phase2FormValues } from "../formTypes";

interface Props {
  phase1JobId: string;
  annotatedMethods: string[];
  sampleColsUsedInPhase1: string[];
  values: Phase2FormValues;
  onChange: (values: Phase2FormValues) => void;
  onStarted: (jobId: string) => void;
  onBack: () => void;
}

export default function Phase2ConfigStep({
  phase1JobId,
  annotatedMethods,
  sampleColsUsedInPhase1,
  values: v,
  onChange,
  onStarted,
  onBack,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [manualMethodsText, setManualMethodsText] = useState(v.methods.join(", "));

  function update(patch: Partial<Phase2FormValues>) {
    onChange({ ...v, ...patch });
  }

  function toggleMethod(item: string) {
    const next = v.methods.includes(item)
      ? v.methods.filter((x) => x !== item)
      : [...v.methods, item];
    update({ methods: next });
  }

  const usingOverride = v.phase1OutdirOverride.trim().length > 0;

  async function handleSubmit() {
    setError(null);
    const methods = usingOverride
      ? manualMethodsText.split(",").map((s) => s.trim()).filter(Boolean)
      : v.methods;
    if (methods.length < 2) {
      setError("Select (or list) at least 2 methods for majority-vote consensus.");
      return;
    }
    setBusy(true);
    try {
      const req: Phase2Request = {
        phase1_job_id: usingOverride ? null : phase1JobId,
        phase1_outdir: usingOverride ? v.phase1OutdirOverride.trim() : null,
        methods,
        knn_k: v.knnK,
        min_votes: v.minVotes,
        sample_cols: sampleColsUsedInPhase1,
        template_max_per_label: v.templateMaxPerLabel,
        outdir: v.outdir.trim() || null,
      };
      const { job_id } = await startPhase2(req);
      onStarted(job_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const selectedCount = usingOverride
    ? manualMethodsText.split(",").map((s) => s.trim()).filter(Boolean).length
    : v.methods.length;

  return (
    <div className="card">
      <h2>4. Configure Phase 2</h2>
      <p className="muted">
        Consensus voting across your annotated methods, then projection onto your full dataset
        with confidence/disagreement flagging. This runs on your <em>full</em> uploaded file, so
        it can take several minutes.
      </p>

      <fieldset>
        <legend>Phase 1 source</legend>
        <label className="full-width">
          Use a different Phase 1 output directory instead (optional)
          <input
            type="text"
            value={v.phase1OutdirOverride}
            onChange={(e) => update({ phase1OutdirOverride: e.target.value })}
            placeholder="leave blank to use the run from the previous step"
          />
        </label>
        <p className="muted">
          Points at any Phase 1 output — from the CLI, a notebook, or an earlier GUI session —
          not just the one you just ran.
        </p>
      </fieldset>

      <fieldset>
        <legend>Methods to include in consensus ({selectedCount} selected)</legend>
        {usingOverride ? (
          <label className="full-width">
            Method names (comma-separated) — must match annotated methods in that directory
            <input
              type="text"
              value={manualMethodsText}
              onChange={(e) => setManualMethodsText(e.target.value)}
              placeholder="phenograph, kmeans, leiden"
            />
          </label>
        ) : (
          <div className="chip-grid">
            {annotatedMethods.map((m) => (
              <label key={m} className={`chip ${v.methods.includes(m) ? "chip-on" : ""}`}>
                <input type="checkbox" checked={v.methods.includes(m)} onChange={() => toggleMethod(m)} />
                {m}
              </label>
            ))}
          </div>
        )}
        {selectedCount !== 3 && (
          <p className="warn">
            The consensus methodology (majority vote, disagreement scoring) was validated around
            exactly 3 methods. It'll still run correctly with a different count, but consider
            picking exactly 3 for results closest to the validated design.
          </p>
        )}
      </fieldset>

      <fieldset>
        <legend>Parameters</legend>
        <div className="form-grid">
          <label>
            KNN k
            <input type="number" value={v.knnK} min={1} onChange={(e) => update({ knnK: Number(e.target.value) })} />
          </label>
          <label>
            Min votes for consensus
            <input
              type="number"
              value={v.minVotes}
              min={1}
              max={selectedCount || 1}
              onChange={(e) => update({ minVotes: Number(e.target.value) })}
            />
          </label>
          <label>
            Max cells per label in template
            <input
              type="number"
              value={v.templateMaxPerLabel}
              min={10}
              onChange={(e) => update({ templateMaxPerLabel: Number(e.target.value) })}
            />
          </label>
          <label className="full-width">
            Output directory (optional)
            <input
              type="text"
              value={v.outdir}
              onChange={(e) => update({ outdir: e.target.value })}
              placeholder="leave blank to use an auto-generated location"
            />
          </label>
        </div>
      </fieldset>

      {error && <p className="error">Error: {error}</p>}
      <div className="button-row">
        <button className="secondary" disabled={busy} onClick={onBack}>
          ← Back
        </button>
        <button disabled={busy} onClick={handleSubmit}>
          {busy ? "Starting…" : "Run Phase 2"}
        </button>
      </div>
    </div>
  );
}
