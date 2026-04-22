"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import { apiFetch, getApiBaseUrl } from "../lib/api";

type DocumentRow = {
  document_id: string;
  filename: string;
  mime_type: string;
  ingest_status: string;
  created_at: string;
};

type SkillHistory = {
  user_id: string;
  revisions: Array<{
    revision_id: string;
    revision_number: number;
    summary_rule: string;
    update_reason: string;
    profile_json: Record<string, unknown>;
    created_at: string;
  }>;
};

type ExperimentRun = {
  run_id: string;
  user_id: string;
  chat_message_id: string;
  condition_name: string;
  skills_enabled: boolean;
  candidate_count: number;
  notes: string | null;
  created_at: string;
};

export function AdminWorkspace() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [userId, setUserId] = useState("");
  const [skillHistory, setSkillHistory] = useState<SkillHistory | null>(null);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const exportUrl = useMemo(() => `${getApiBaseUrl()}/api/experiments/exports/logs.zip`, []);

  async function refreshDocuments() {
    const response = await apiFetch<DocumentRow[]>("/api/documents");
    setDocuments(response);
  }

  async function refreshRuns() {
    const response = await apiFetch<ExperimentRun[]>("/api/experiments/runs");
    setRuns(response);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) return;
    setError("");
    setStatus("Uploading document...");
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const uploadResponse = await fetch(`${getApiBaseUrl()}/api/documents/upload`, {
        method: "POST",
        body: formData,
      });
      if (!uploadResponse.ok) {
        throw new Error(await uploadResponse.text());
      }
      const document = (await uploadResponse.json()) as DocumentRow;
      await apiFetch(`/api/documents/${document.document_id}/ingest`, {
        method: "POST",
      });
      setStatus("Upload complete. Ingestion job queued.");
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Upload failed");
    }
  }

  async function handleLoadHistory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await apiFetch<SkillHistory>(`/api/admin/skills/history/${userId}`);
      setSkillHistory(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load skill history");
      setSkillHistory(null);
    }
  }

  async function handleRecompute() {
    if (!userId) return;
    setError("");
    try {
      await apiFetch(`/api/admin/skills/recompute/${userId}`, { method: "POST" });
      setStatus("Skill recompute job queued.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Recompute failed");
    }
  }

  async function handleRefresh() {
    setError("");
    await Promise.all([refreshDocuments(), refreshRuns()]);
  }

  return (
    <div className="stack">
      <section className="hero">
        <div className="card stack">
          <div>
            <p className="muted">Admin / Experiment</p>
            <h1>Research operations</h1>
            <p className="muted">Upload materials, inspect skill revision history, and export experiment logs.</p>
          </div>
          <div className="grid-2">
            <button className="button" onClick={handleRefresh} type="button">
              Refresh documents and runs
            </button>
            <a className="button secondary" href={exportUrl}>
              Download logs.zip
            </a>
          </div>
          {status ? <p className="muted">{status}</p> : null}
          {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
        </div>

        <form className="card stack" onSubmit={handleUpload}>
          <div>
            <h2>Document ingestion</h2>
            <p className="muted">Upload `pdf`, `md`, or `txt`, then queue ingestion for worker processing.</p>
          </div>
          <label className="field">
            <span>File</span>
            <input accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown" onChange={handleFileChange} type="file" />
          </label>
          <button className="button" type="submit">
            Upload and queue ingestion
          </button>
        </form>
      </section>

      <section className="grid-2">
        <div className="card stack">
          <h2>Indexed documents</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Status</th>
                <th>Type</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.document_id}>
                  <td>{document.filename}</td>
                  <td>{document.ingest_status}</td>
                  <td>{document.mime_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card stack">
          <h2>Experiment runs</h2>
          <table className="table">
            <thead>
              <tr>
                <th>Condition</th>
                <th>User</th>
                <th>Skills</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.run_id}>
                  <td>{run.condition_name}</td>
                  <td>{run.user_id}</td>
                  <td>{String(run.skills_enabled)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card stack">
        <div>
          <h2>Skill history</h2>
          <p className="muted">Load revisions for a user and optionally queue recomputation from the latest selection.</p>
        </div>
        <form className="grid-2" onSubmit={handleLoadHistory}>
          <label className="field">
            <span>User ID</span>
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Enter a learner user_id" />
          </label>
          <div style={{ alignSelf: "end", display: "flex", gap: 12 }}>
            <button className="button secondary" onClick={handleRecompute} type="button">
              Recompute skills
            </button>
            <button className="button" type="submit">
              Load history
            </button>
          </div>
        </form>
        {skillHistory ? (
          <div className="stack">
            {skillHistory.revisions.map((revision) => (
              <article className="card" key={revision.revision_id} style={{ padding: 16 }}>
                <p className="muted">Revision {revision.revision_number}</p>
                <strong>{revision.summary_rule}</strong>
                <p>{revision.update_reason}</p>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(revision.profile_json, null, 2)}</pre>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">No history loaded yet.</p>
        )}
      </section>
    </div>
  );
}

