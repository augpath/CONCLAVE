import { useState } from "react";
import { uploadCsv, type UploadResponse } from "../api";

interface Props {
  onUploaded: (res: UploadResponse) => void;
}

export default function UploadStep({ onUploaded }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      const res = await uploadCsv(file);
      onUploaded(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h2>1. Upload your data</h2>
      <p className="muted">A CSV with one row per cell and one column per marker.</p>
      <input
        type="file"
        accept=".csv"
        disabled={busy}
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) handleFile(f);
        }}
      />
      {busy && <p>Uploading and reading columns…</p>}
      {error && <p className="error">Error: {error}</p>}
    </div>
  );
}
