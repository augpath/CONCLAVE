// Typed API client for the CONCLAVE GUI backend.
// Kept as plain fetch wrappers (no axios) to minimize dependencies for a fast v1.

export interface UploadResponse {
  upload_id: string;
  columns: string[];
  n_rows: number;
  preview: Record<string, unknown>[];
}

export interface JobStatus {
  id: string;
  kind: string;
  status: "queued" | "running" | "completed" | "failed";
  logs: string[];
  error: string | null;
  result: Record<string, unknown>;
}

export interface Phase1Request {
  upload_id: string;
  markers: string[];
  sample_cols: string[];
  normalization: string | null;
  sampling: string;
  sample_size: number;
  n_tiles_per_axis: number;
  dr_method: string | null;
  dr_n_components: number;
  cluster_methods: string[];
  phenograph_k: number;
  derive_kmeans_from: string | null;
  flowsom_rscript: string | null;
  depeche_rscript: string | null;
  seed: number;
}

export interface ClusterRow {
  cluster_id: number;
  n_cells: number;
  annotation: string;
}

export interface ClustersResponse {
  methods: string[];
  clusters: Record<string, ClusterRow[]>;
  annotated_methods: string[];
}

export interface Phase2Request {
  phase1_job_id: string;
  methods: string[];
  knn_k: number;
  min_votes: number;
  sample_cols: string[];
  template_max_per_label: number;
}

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function uploadCsv(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  return asJson(res);
}

export async function startPhase1(req: Phase1Request): Promise<{ job_id: string }> {
  const res = await fetch("/api/phase1/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return asJson(res);
}

export async function getJob(jobId: string): Promise<JobStatus> {
  const res = await fetch(`/api/jobs/${jobId}`);
  return asJson(res);
}

export async function getPhase1Clusters(jobId: string): Promise<ClustersResponse> {
  const res = await fetch(`/api/phase1/jobs/${jobId}/clusters`);
  return asJson(res);
}

export function heatmapUrl(jobId: string, method: string): string {
  return `/api/phase1/jobs/${jobId}/heatmap/${method}`;
}

export async function saveAnnotations(
  jobId: string,
  method: string,
  annotations: Record<string, string>
): Promise<{ status: string; n_clusters: number; n_annotated: number }> {
  const res = await fetch(`/api/phase1/jobs/${jobId}/annotations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ method, annotations }),
  });
  return asJson(res);
}

export async function startPhase2(req: Phase2Request): Promise<{ job_id: string }> {
  const res = await fetch("/api/phase2/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  return asJson(res);
}

export async function listPhase2Plots(jobId: string): Promise<{ plots: string[] }> {
  const res = await fetch(`/api/phase2/jobs/${jobId}/plots`);
  return asJson(res);
}

export function plotUrl(jobId: string, name: string): string {
  return `/api/phase2/jobs/${jobId}/plot/${name}`;
}

export function downloadUrl(jobId: string): string {
  return `/api/phase2/jobs/${jobId}/download`;
}
