import { useState } from "react";
import "./App.css";
import UploadStep from "./components/UploadStep";
import Phase1ConfigStep from "./components/Phase1ConfigStep";
import JobProgress from "./components/JobProgress";
import Phase1ReviewStep from "./components/Phase1ReviewStep";
import Phase2ConfigStep from "./components/Phase2ConfigStep";
import Phase2ResultsStep from "./components/Phase2ResultsStep";
import type { JobStatus, UploadResponse } from "./api";

type Step =
  | "upload"
  | "phase1_config"
  | "phase1_running"
  | "phase1_review"
  | "phase2_config"
  | "phase2_running"
  | "phase2_results";

const STEP_LABELS: Record<Step, string> = {
  upload: "Upload",
  phase1_config: "Configure Phase 1",
  phase1_running: "Running Phase 1",
  phase1_review: "Annotate",
  phase2_config: "Configure Phase 2",
  phase2_running: "Running Phase 2",
  phase2_results: "Results",
};
const STEP_ORDER: Step[] = [
  "upload",
  "phase1_config",
  "phase1_running",
  "phase1_review",
  "phase2_config",
  "phase2_running",
  "phase2_results",
];

export default function App() {
  const [step, setStep] = useState<Step>("upload");
  const [upload, setUpload] = useState<UploadResponse | null>(null);
  const [phase1JobId, setPhase1JobId] = useState<string | null>(null);
  const [phase1Job, setPhase1Job] = useState<JobStatus | null>(null);
  const [annotatedMethods, setAnnotatedMethods] = useState<string[]>([]);
  const [phase2JobId, setPhase2JobId] = useState<string | null>(null);
  const [phase2Job, setPhase2Job] = useState<JobStatus | null>(null);

  const sampleColsUsedInPhase1: string[] = []; // read back from phase1Job.result if needed later

  return (
    <div className="app">
      <header>
        <h1>CONCLAVE</h1>
        <p className="muted">Consensus clustering &amp; annotation, in the browser</p>
      </header>

      <ol className="stepper">
        {STEP_ORDER.map((s) => (
          <li key={s} className={s === step ? "step-active" : ""}>
            {STEP_LABELS[s]}
          </li>
        ))}
      </ol>

      <main>
        {step === "upload" && (
          <UploadStep
            onUploaded={(res) => {
              setUpload(res);
              setStep("phase1_config");
            }}
          />
        )}

        {step === "phase1_config" && upload && (
          <Phase1ConfigStep
            upload={upload}
            onStarted={(jobId) => {
              setPhase1JobId(jobId);
              setStep("phase1_running");
            }}
          />
        )}

        {step === "phase1_running" && phase1JobId && (
          <JobProgress
            jobId={phase1JobId}
            title="Running Phase 1…"
            onDone={(job) => {
              setPhase1Job(job);
              if (job.status === "completed") setStep("phase1_review");
            }}
          />
        )}
        {step === "phase1_running" && phase1Job?.status === "failed" && (
          <div className="card">
            <p className="error">Phase 1 failed: {phase1Job.error}</p>
            <button onClick={() => setStep("phase1_config")}>← Back to config</button>
          </div>
        )}

        {step === "phase1_review" && phase1JobId && (
          <Phase1ReviewStep
            jobId={phase1JobId}
            onContinue={(methods) => {
              setAnnotatedMethods(methods);
              setStep("phase2_config");
            }}
          />
        )}

        {step === "phase2_config" && phase1JobId && (
          <Phase2ConfigStep
            phase1JobId={phase1JobId}
            annotatedMethods={annotatedMethods}
            sampleColsUsedInPhase1={sampleColsUsedInPhase1}
            onStarted={(jobId) => {
              setPhase2JobId(jobId);
              setStep("phase2_running");
            }}
          />
        )}

        {step === "phase2_running" && phase2JobId && (
          <JobProgress
            jobId={phase2JobId}
            title="Running Phase 2…"
            onDone={(job) => {
              setPhase2Job(job);
              if (job.status === "completed") setStep("phase2_results");
            }}
          />
        )}
        {step === "phase2_running" && phase2Job?.status === "failed" && (
          <div className="card">
            <p className="error">Phase 2 failed: {phase2Job.error}</p>
            <button onClick={() => setStep("phase2_config")}>← Back to config</button>
          </div>
        )}

        {step === "phase2_results" && phase2JobId && phase2Job && (
          <Phase2ResultsStep jobId={phase2JobId} job={phase2Job} />
        )}
      </main>
    </div>
  );
}
