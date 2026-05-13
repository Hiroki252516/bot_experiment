"use client";

import { ChangeEvent, FormEvent, useEffect, useState } from "react";

import { apiFetch, getApiBaseUrl } from "../lib/api";

type SourceDocument = {
  document_id: string;
  title: string;
  description: string | null;
  filename: string;
  mime_type: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type ExportJob = { export_job_id: string; status: string; file_path: string | null };

export function AdminWorkspace() {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [runId, setRunId] = useState("");
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function refreshDocuments() {
    const response = await apiFetch<SourceDocument[]>("/api/admin/documents");
    setDocuments(response);
  }

  useEffect(() => {
    void refreshDocuments();
  }, []);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    if (file && !title) setTitle(file.name);
  }

  async function handleUpload(event: FormEvent) {
    event.preventDefault();
    if (!selectedFile) return;
    setError("");
    setStatus("PDF教材をアップロードしています...");
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("title", title || selectedFile.name);
      const response = await fetch(`${getApiBaseUrl()}/api/admin/documents/upload`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!response.ok) throw new Error(await response.text());
      setStatus("アップロードしました。Document Agent Skill extraction を実行してください。");
      setSelectedFile(null);
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "アップロードに失敗しました。");
      setStatus("");
    }
  }

  async function extractSkill(documentId: string) {
    setError("");
    setStatus("Document Agent Skill を抽出しています...");
    try {
      await apiFetch(`/api/admin/documents/${documentId}/extract-skill`, { method: "POST" });
      setStatus("Document Agent Skill を抽出しました。被験者 run を開始できます。");
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Document Agent Skill extraction に失敗しました。");
      setStatus("");
    }
  }

  async function deleteDocument(document: SourceDocument) {
    const confirmed = window.confirm(
      `教材「${document.title} / ${document.filename}」を削除します。既存runで使われている場合はログ保護のため非表示状態にします。よろしいですか？`,
    );
    if (!confirmed) return;
    setError("");
    setStatus("教材を削除しています...");
    try {
      await apiFetch(`/api/admin/documents/${document.document_id}`, { method: "DELETE" });
      setStatus("教材を削除しました。");
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "教材の削除に失敗しました。");
      setStatus("");
    }
  }

  async function exportRun(event: FormEvent) {
    event.preventDefault();
    if (!runId) return;
    setError("");
    setStatus("CSV export を作成しています...");
    try {
      const job = await apiFetch<ExportJob>(`/api/admin/exports/runs/${runId}`, { method: "POST" });
      setExportJob(job);
      setStatus("CSV export を作成しました。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "CSV export に失敗しました。");
      setStatus("");
    }
  }

  return (
    <div className="stack">
      <section className="hero">
        <div className="card stack">
          <p className="muted">管理 / Agent Skills 実験</p>
          <h1>研究用管理画面</h1>
          <p className="muted">PDF 教材を Document Agent Skill に変換し、10サイクル実験のログを export します。新 runtime path では RAG / embedding retrieval を使いません。</p>
          <button className="button secondary" onClick={refreshDocuments} type="button">教材一覧を更新</button>
          {status ? <p className="muted">{status}</p> : null}
          {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
        </div>

        <form className="card stack" onSubmit={handleUpload}>
          <h2>PDF 教材アップロード</h2>
          <label className="field">
            <span>教材タイトル</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例: 仮定法教材" />
          </label>
          <label className="field">
            <span>PDF / md / txt</span>
            <input accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown" onChange={handleFileChange} type="file" />
          </label>
          <button className="button" disabled={!selectedFile} type="submit">アップロード</button>
        </form>
      </section>

      <section className="card stack">
        <h2>教材一覧</h2>
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>タイトル</th>
                <th>ファイル</th>
                <th>状態</th>
                <th>作成日時</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.document_id}>
                  <td>{document.title}</td>
                  <td className="break-anywhere">{document.filename}</td>
                  <td>{document.status}</td>
                  <td>{new Date(document.created_at).toLocaleString("ja-JP")}</td>
                  <td>
                    <div className="inline" style={{ gap: 8, flexWrap: "wrap" }}>
                      <button className="button secondary" onClick={() => extractSkill(document.document_id)} type="button">
                        Document Skill 抽出
                      </button>
                      <button className="button secondary" onClick={() => deleteDocument(document)} type="button">
                        削除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <form className="card stack" onSubmit={exportRun}>
        <h2>CSV export</h2>
        <p className="muted">run_id を指定して、runs / assessments / attempts / materials / skills / generation_logs / results を zip 用に生成します。</p>
        <label className="field">
          <span>run_id</span>
          <input value={runId} onChange={(event) => setRunId(event.target.value)} placeholder="被験者画面の run_id" />
        </label>
        <button className="button" disabled={!runId} type="submit">export 作成</button>
        {exportJob ? (
          <p className="muted">export_job_id: {exportJob.export_job_id} / status: {exportJob.status} / path: {exportJob.file_path}</p>
        ) : null}
      </form>
    </div>
  );
}
