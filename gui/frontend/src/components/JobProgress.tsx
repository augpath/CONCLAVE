import { useEffect, useRef, useState } from "react";
import { getJob, type JobStatus } from "../api";

interface Props {
  jobId: string;
  title: string;
  onDone: (job: JobStatus) => void;
}

export default function JobProgress({ jobId, title, onDone }: Props) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const doneRef = useRef(false);

  useEffect(() => {
    doneRef.current = false;
    let cancelled = false;

    async function poll() {
      if (cancelled || doneRef.current) return;
      try {
        const j = await getJob(jobId);
        if (cancelled) return;
        setJob(j);
        if (j.status === "completed" || j.status === "failed") {
          doneRef.current = true;
          onDone(j);
          return;
        }
      } catch {
        // transient network error while polling -- just retry
      }
      setTimeout(poll, 1500);
    }
    poll();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [job?.logs.length]);

  return (
    <div className="card">
      <h2>{title}</h2>
      <p>
        Status: <strong className={`status-${job?.status ?? "queued"}`}>{job?.status ?? "queued"}</strong>
      </p>
      <pre className="log-view" ref={logRef}>
        {(job?.logs ?? []).join("\n") || "Waiting for output…"}
      </pre>
      {job?.error && <p className="error">{job.error}</p>}
    </div>
  );
}
