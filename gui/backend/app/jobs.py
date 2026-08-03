"""Serialized background job execution with live log capture.

Design choices, deliberate for a "fast v1" local/single-user tool:
- Only ONE job runs at a time (single worker thread pulling from a queue).
  This keeps stdout/stderr redirection safe (Python's sys.stdout/stderr are
  process-global, not thread-local -- redirecting them while multiple jobs
  ran concurrently would cross-contaminate their logs) and avoids CPU/memory
  contention between heavy Phase 1/2 runs.
- Progress capture works for BOTH phases despite them logging differently:
  Phase 1 uses the `logging` module (writes to stderr by default), Phase 2
  uses plain print() (writes to stdout). Redirecting both stdout and stderr
  into the same line-buffered capture stream picks up either style without
  needing to know conclave's internals.
"""
import contextlib
import queue
import threading
import time
import traceback
import uuid
from typing import Any, Callable, Dict, List, Optional


class ListStream:
    """File-like object that appends complete lines to a shared list as
    they're written, so a poller can read live progress mid-run."""

    def __init__(self, sink: List[str]):
        self.sink = sink
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                self.sink.append(line)
        return len(s)

    def flush(self) -> None:
        pass


class Job:
    def __init__(self, job_id: str, kind: str):
        self.id = job_id
        self.kind = kind
        self.status = "queued"  # queued | running | completed | failed
        self.logs: List[str] = []
        self.error: Optional[str] = None
        self.result: Dict[str, Any] = {}
        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None


class JobManager:
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: "queue.Queue" = queue.Queue()
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    def create(self, kind: str) -> Job:
        job = Job(str(uuid.uuid4()), kind)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def start(self, job: Job, target: Callable, *args, **kwargs) -> None:
        self._queue.put((job, target, args, kwargs))

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def _worker_loop(self) -> None:
        while True:
            job, target, args, kwargs = self._queue.get()
            job.status = "running"
            job.started_at = time.time()
            stream = ListStream(job.logs)
            try:
                with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                    result = target(*args, **kwargs)
                job.result = result if result is not None else {}
                job.status = "completed"
            except Exception as e:  # noqa: BLE001 -- deliberately broad, this is a job runner
                job.status = "failed"
                job.error = f"{type(e).__name__}: {e}"
                job.logs.append(f"ERROR: {job.error}")
                job.logs.append(traceback.format_exc())
            finally:
                job.finished_at = time.time()
                self._queue.task_done()


job_manager = JobManager()
