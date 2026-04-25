"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiFetch } from "../lib/api";

type UserResponse = {
  user_id: string;
  active_skill_revision_id: string | null;
};

type Candidate = {
  candidate_id: string;
  title: string;
  style_tags: string[];
  answer_text: string;
  rank: number;
  display_order: number;
};

type ChatGenerateResponse = {
  session_id: string;
  chat_message_id: string;
  generation_run_id: string;
  skills_enabled: boolean;
  active_skill_revision_id: string | null;
  retrievals: Array<{ chunk_id: string; document_id: string; filename: string; chunk_index: number; score: number; text: string }>;
  candidates: Candidate[];
};

type DocumentRow = {
  document_id: string;
  filename: string;
  source_type: string;
  ingest_status: string;
  created_at: string;
};

export function ChatWorkspace() {
  const [displayName, setDisplayName] = useState("研究参加者");
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [question, setQuestion] = useState("二次方程式の解き方を教えて");
  const [skillsEnabled, setSkillsEnabled] = useState(true);
  const [candidateCount, setCandidateCount] = useState(3);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [chatResult, setChatResult] = useState<ChatGenerateResponse | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [satisfactionScore, setSatisfactionScore] = useState(8);
  const [clarityScore, setClarityScore] = useState(8);
  const [comment, setComment] = useState("例題つきの説明がわかりやすい");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    async function refreshDocuments() {
      try {
        const response = await apiFetch<DocumentRow[]>("/api/documents");
        const completedDocuments = response.filter((document) => document.ingest_status === "completed");
        setDocuments(completedDocuments);
        setSelectedDocumentIds((current) => {
          const availableIds = new Set(completedDocuments.map((document) => document.document_id));
          const stillAvailable = current.filter((documentId) => availableIds.has(documentId));
          if (stillAvailable.length) return stillAvailable;
          const latestUploaded = completedDocuments.find((document) => document.source_type !== "seed");
          const initialDocument = latestUploaded ?? completedDocuments[0];
          return initialDocument ? [initialDocument.document_id] : [];
        });
      } catch (requestError) {
        setError(requestError instanceof Error ? requestError.message : "教材一覧の取得に失敗しました。");
      }
    }
    refreshDocuments();
  }, []);

  async function ensureUser() {
    if (userId) return userId;
    const created = await apiFetch<UserResponse>("/api/users", {
      method: "POST",
      body: JSON.stringify({ display_name: displayName }),
    });
    setUserId(created.user_id);
    return created.user_id;
  }

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("回答候補を生成しています...");
    try {
      const resolvedUserId = await ensureUser();
      const response = await apiFetch<ChatGenerateResponse>("/api/chat/generate", {
        method: "POST",
        body: JSON.stringify({
          user_id: resolvedUserId,
          question,
          candidate_count: candidateCount,
          skills_enabled: skillsEnabled,
          document_ids: selectedDocumentIds.length ? selectedDocumentIds : null,
          session_id: sessionId || null,
          experiment_condition: skillsEnabled ? "skills_on" : "skills_off",
        }),
      });
      setChatResult(response);
      setSessionId(response.session_id);
      setSelectedCandidateId(response.candidates[0]?.candidate_id ?? "");
      setStatus("回答候補を生成しました。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "回答候補の生成に失敗しました。");
      setStatus("");
    }
  }

  function toggleDocument(documentId: string) {
    setSelectedDocumentIds((current) =>
      current.includes(documentId)
        ? current.filter((selectedDocumentId) => selectedDocumentId !== documentId)
        : [...current, documentId],
    );
  }

  async function handleSelection(candidateId: string) {
    if (!chatResult) return;
    setError("");
    setStatus("選択結果を保存しています...");
    try {
      await apiFetch("/api/chat/select", {
        method: "POST",
        body: JSON.stringify({
          chat_message_id: chatResult.chat_message_id,
          selected_candidate_id: candidateId,
          satisfaction_score: satisfactionScore,
          clarity_score: clarityScore,
          comment,
        }),
      });
      setSelectedCandidateId(candidateId);
      setStatus("選択結果を保存しました。ワーカーがスキル履歴を更新します。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "選択結果の保存に失敗しました。");
      setStatus("");
    }
  }

  return (
    <div className="stack">
      <section className="hero">
        <div className="card stack">
          <div>
            <p className="muted">研究用プロトタイプ</p>
            <h1>回答選択で個人化する学習支援チャット</h1>
            <p className="muted">
              質問に対して複数の回答候補を生成し、学習者の選択を次回以降の説明方針に反映します。
            </p>
          </div>
          <form className="stack" onSubmit={handleGenerate}>
            <div className="grid-2">
              <label className="field">
                <span>表示名</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </label>
              <label className="field">
                <span>ユーザーID</span>
                <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="空欄なら自動作成" />
              </label>
            </div>
            <div className="grid-2">
              <label className="field">
                <span>セッションID</span>
                <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="既存セッションを続ける場合に入力" />
              </label>
              <label className="field">
                <span>回答候補数</span>
                <select value={candidateCount} onChange={(event) => setCandidateCount(Number(event.target.value))}>
                  <option value={3}>3</option>
                  <option value={2}>2</option>
                  <option value={4}>4</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>質問</span>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            </label>
            <label className="field">
              <span>実験条件</span>
              <select value={skillsEnabled ? "on" : "off"} onChange={(event) => setSkillsEnabled(event.target.value === "on")}>
                <option value="on">スキル有効</option>
                <option value="off">スキル無効</option>
              </select>
            </label>
            <div className="field">
              <span>検索対象教材</span>
              <div className="stack" style={{ gap: 8 }}>
                {documents.map((document) => (
                  <label className="inline" key={document.document_id}>
                    <input
                      checked={selectedDocumentIds.includes(document.document_id)}
                      onChange={() => toggleDocument(document.document_id)}
                      type="checkbox"
                    />
                    <span>
                      {document.filename}
                      {document.source_type === "seed" ? " (seed)" : ""}
                    </span>
                  </label>
                ))}
                {documents.length === 0 ? <p className="muted">completed の教材がありません。管理画面から教材を投入してください。</p> : null}
                {selectedDocumentIds.length === 0 ? (
                  <p className="muted">未選択の場合、seed 教材を除いた completed 教材全体から検索します。</p>
                ) : null}
              </div>
            </div>
            <button className="button" type="submit">
              回答候補を生成
            </button>
          </form>
        </div>

        <div className="card stack">
          <div>
            <h2>選択時フィードバック</h2>
            <p className="muted">候補を選ぶときに、主観評価として一緒に保存します。</p>
          </div>
          <label className="field">
            <span>満足度 (1-10)</span>
            <input type="number" min={1} max={10} value={satisfactionScore} onChange={(event) => setSatisfactionScore(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>わかりやすさ (1-10)</span>
            <input type="number" min={1} max={10} value={clarityScore} onChange={(event) => setClarityScore(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>コメント</span>
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          <div className="card" style={{ padding: 14 }}>
            <strong>現在の状態</strong>
            <p className="muted">{status || "待機中"}</p>
            {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
          </div>
        </div>
      </section>

      {chatResult ? (
        <section className="stack">
          <div className="card stack">
            <div className="grid-2">
              <div>
                <h2>生成メタデータ</h2>
                <p className="muted">セッション: {chatResult.session_id}</p>
                <p className="muted">質問ターン: {chatResult.chat_message_id}</p>
              </div>
              <div>
                <h2>検索結果</h2>
                <p className="muted">{chatResult.retrievals.length} 件のチャンクを参照しました。</p>
              </div>
            </div>
            <div className="stack">
              {chatResult.retrievals.map((retrieval) => (
                <div className="card" key={retrieval.chunk_id} style={{ padding: 14 }}>
                  <strong>{retrieval.filename}</strong>
                  <p className="muted">
                    chunk {retrieval.chunk_index} / {retrieval.chunk_id} / スコア: {retrieval.score.toFixed(4)}
                  </p>
                  <p>{retrieval.text}</p>
                </div>
              ))}
              {chatResult.retrievals.length === 0 ? <p className="muted">まだ検索対象のチャンクがありません。管理画面から教材を投入してください。</p> : null}
            </div>
          </div>

          <div className="grid-3">
            {chatResult.candidates.map((candidate) => (
              <article className="candidate" key={candidate.candidate_id}>
                <div>
                  <p className="muted">候補 {candidate.rank}</p>
                  <h3>{candidate.title}</h3>
                </div>
                <div className="tag-row">
                  {candidate.style_tags.map((tag) => (
                    <span className="tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
                <p>{candidate.answer_text}</p>
                <button className={selectedCandidateId === candidate.candidate_id ? "button secondary" : "button"} onClick={() => handleSelection(candidate.candidate_id)} type="button">
                  {selectedCandidateId === candidate.candidate_id ? "選択中" : "この回答を選ぶ"}
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
