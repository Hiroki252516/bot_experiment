"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import { apiFetch, getApiBaseUrl } from "../lib/api";

type DocumentRow = {
  document_id: string;
  filename: string;
  mime_type: string;
  source_type: string;
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

type RuntimeProvider = {
  generation_provider: string;
  embedding_provider: string;
  generation_model: string;
  embedding_model: string;
  embedding_dimensions: number;
  local_embed_device: string;
};

export function AdminWorkspace() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [userId, setUserId] = useState("");
  const [skillHistory, setSkillHistory] = useState<SkillHistory | null>(null);
  const [runs, setRuns] = useState<ExperimentRun[]>([]);
  const [runtime, setRuntime] = useState<RuntimeProvider | null>(null);
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

  async function refreshRuntime() {
    const response = await apiFetch<RuntimeProvider>("/api/admin/runtime");
    setRuntime(response);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedFile) return;
    setError("");
    setStatus("教材をアップロードしています...");
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
      setStatus("アップロードが完了しました。取り込みジョブを登録しました。");
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "アップロードに失敗しました。");
    }
  }

  async function handleDeleteDocument(document: DocumentRow) {
    const confirmed = window.confirm(
      `教材「${document.filename}」を削除します。取り込みジョブ、チャンク、埋め込み、検索ログ、保存ファイルも削除されます。よろしいですか？`,
    );
    if (!confirmed) return;
    setError("");
    setStatus("教材を削除しています...");
    try {
      await apiFetch(`/api/documents/${document.document_id}`, { method: "DELETE" });
      setStatus("教材を削除しました。");
      await refreshDocuments();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "教材の削除に失敗しました。");
    }
  }

  async function handleLoadHistory(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await apiFetch<SkillHistory>(`/api/admin/skills/history/${userId}`);
      setSkillHistory(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "スキル履歴の取得に失敗しました。");
      setSkillHistory(null);
    }
  }

  async function handleRecompute() {
    if (!userId) return;
    setError("");
    try {
      await apiFetch(`/api/admin/skills/recompute/${userId}`, { method: "POST" });
      setStatus("スキル再計算ジョブを登録しました。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "スキル再計算に失敗しました。");
    }
  }

  async function handleRefresh() {
    setError("");
    await Promise.all([refreshDocuments(), refreshRuns(), refreshRuntime()]);
  }

  return (
    <div className="stack">
      <section className="hero">
        <div className="card stack">
          <div>
            <p className="muted">管理 / 実験</p>
            <h1>研究用の操作</h1>
            <p className="muted">教材投入、スキル履歴の確認、実験ログの出力を行います。</p>
          </div>
          <div className="grid-2">
            <button className="button" onClick={handleRefresh} type="button">
              教材と実験ログを更新
            </button>
            <a className="button secondary" href={exportUrl}>
              logs.zip をダウンロード
            </a>
          </div>
          {status ? <p className="muted">{status}</p> : null}
          {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
          {runtime ? (
            <div className="card" style={{ padding: 16 }}>
              <p className="muted">実行設定</p>
              <p>
                生成: {runtime.generation_provider} / {runtime.generation_model}
              </p>
              <p>
                埋め込み: {runtime.embedding_provider} / {runtime.embedding_model} / {runtime.embedding_dimensions} 次元 / device={runtime.local_embed_device}
              </p>
            </div>
          ) : null}
        </div>

        <form className="card stack" onSubmit={handleUpload}>
          <div>
            <h2>教材の取り込み</h2>
            <p className="muted">`pdf`、`md`、`txt` をアップロードし、ワーカー処理用の取り込みジョブを登録します。</p>
          </div>
          <label className="field">
            <span>ファイル</span>
            <input accept=".pdf,.md,.txt,text/plain,application/pdf,text/markdown" onChange={handleFileChange} type="file" />
          </label>
          <button className="button" type="submit">
            アップロードして取り込みを登録
          </button>
        </form>
      </section>

      <section className="grid-2">
        <div className="card stack">
          <h2>投入済み教材</h2>
          <table className="table">
            <thead>
              <tr>
                <th>ファイル名</th>
                <th>状態</th>
                <th>種類</th>
                <th>由来</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((document) => (
                <tr key={document.document_id}>
                  <td>{document.filename}</td>
                  <td>{document.ingest_status}</td>
                  <td>{document.mime_type}</td>
                  <td>{document.source_type}</td>
                  <td>
                    <button className="button secondary" onClick={() => handleDeleteDocument(document)} type="button">
                      削除
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card stack">
          <h2>実験ログ</h2>
          <table className="table">
            <thead>
              <tr>
                <th>条件</th>
                <th>ユーザー</th>
                <th>スキル</th>
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
          <h2>スキル履歴</h2>
          <p className="muted">ユーザーごとのリビジョンを確認し、必要に応じて最新の選択結果から再計算します。</p>
        </div>
        <form className="grid-2" onSubmit={handleLoadHistory}>
          <label className="field">
            <span>ユーザーID</span>
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="学習者の user_id を入力" />
          </label>
          <div style={{ alignSelf: "end", display: "flex", gap: 12 }}>
            <button className="button secondary" onClick={handleRecompute} type="button">
              スキルを再計算
            </button>
            <button className="button" type="submit">
              履歴を読み込む
            </button>
          </div>
        </form>
        {skillHistory ? (
          <div className="stack">
            {skillHistory.revisions.map((revision) => (
              <article className="card" key={revision.revision_id} style={{ padding: 16 }}>
                <p className="muted">リビジョン {revision.revision_number}</p>
                <strong>{revision.summary_rule}</strong>
                <p>{revision.update_reason}</p>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(revision.profile_json, null, 2)}</pre>
              </article>
            ))}
          </div>
        ) : (
          <p className="muted">まだ履歴は読み込まれていません。</p>
        )}
      </section>
    </div>
  );
}
