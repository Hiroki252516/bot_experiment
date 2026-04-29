"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";

import { apiFetch } from "../lib/api";

type AuthUserResponse = {
  user_id: string;
  username: string;
  display_name: string | null;
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

function renderInlineMarkdown(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <span key={index}>{part}</span>;
  });
}

function cleanCandidateTitle(title: string) {
  return title.replace(/^#{1,6}\s+/, "").trim();
}

function MarkdownText({ text }: { text: string }) {
  const normalizedText = text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => !line.trim().startsWith("```"))
    .join("\n")
    .replace(/(\S)\s+\*\s+/g, "$1\n* ");
  const blocks = normalizedText
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return (
    <div className="markdown-body">
      {blocks.map((block, blockIndex) => {
        if (block.startsWith("### ")) {
          return <h4 key={blockIndex}>{renderInlineMarkdown(block.slice(4))}</h4>;
        }
        if (block.startsWith("## ")) {
          return <h3 key={blockIndex}>{renderInlineMarkdown(block.slice(3))}</h3>;
        }

        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        if (lines.every((line) => /^[-*]\s+/.test(line))) {
          return (
            <ul key={blockIndex}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>
              ))}
            </ul>
          );
        }
        if (lines.every((line) => /^\d+\.\s+/.test(line))) {
          return (
            <ol key={blockIndex}>
              {lines.map((line, lineIndex) => (
                <li key={lineIndex}>{renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>
              ))}
            </ol>
          );
        }
        return <p key={blockIndex}>{renderInlineMarkdown(lines.join(" "))}</p>;
      })}
    </div>
  );
}

export function ChatWorkspace() {
  const [authUser, setAuthUser] = useState<AuthUserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [sessionId, setSessionId] = useState("");
  const [question, setQuestion] = useState("二次方程式の解き方を教えて");
  const [skillsEnabled, setSkillsEnabled] = useState(true);
  const [candidateCount, setCandidateCount] = useState(3);
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<string[]>([]);
  const [chatResult, setChatResult] = useState<ChatGenerateResponse | null>(null);
  const [activeCandidateId, setActiveCandidateId] = useState("");
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [submittedCandidateId, setSubmittedCandidateId] = useState("");
  const [satisfactionScore, setSatisfactionScore] = useState(8);
  const [clarityScore, setClarityScore] = useState(8);
  const [comment, setComment] = useState("例題つきの説明がわかりやすい");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    async function loadInitialState() {
      try {
        const currentUser = await apiFetch<AuthUserResponse>("/api/auth/me");
        setAuthUser(currentUser);
      } catch {
        setAuthUser(null);
        setAuthLoading(false);
        return;
      }

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
      } finally {
        setAuthLoading(false);
      }
    }
    loadInitialState();
  }, []);

  async function handleGenerate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!authUser) {
      setError("チャットを使うにはログインが必要です。");
      return;
    }
    setError("");
    setStatus("回答候補を生成しています...");
    try {
      const response = await apiFetch<ChatGenerateResponse>("/api/chat/generate", {
        method: "POST",
        body: JSON.stringify({
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
      setActiveCandidateId(response.candidates[0]?.candidate_id ?? "");
      setSelectedCandidateId("");
      setSubmittedCandidateId("");
      setStatus("回答候補を生成しました。候補を1つ選んでから、選択結果を送信してください。");
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

  function handleCandidateChoice(candidateId: string) {
    if (submittedCandidateId) return;
    setSelectedCandidateId(candidateId);
    setStatus("候補を選択しました。評価を確認してから選択結果を送信してください。");
  }

  async function handleFeedbackSubmit() {
    if (!authUser) {
      setError("チャットを使うにはログインが必要です。");
      return;
    }
    if (!chatResult) return;
    if (!selectedCandidateId) {
      setError("回答候補を1つ選択してから送信してください。");
      return;
    }
    setError("");
    setStatus("選択結果をフィードバックとして送信しています...");
    try {
      await apiFetch("/api/chat/select", {
        method: "POST",
        body: JSON.stringify({
          chat_message_id: chatResult.chat_message_id,
          selected_candidate_id: selectedCandidateId,
          satisfaction_score: satisfactionScore,
          clarity_score: clarityScore,
          comment,
        }),
      });
      setSubmittedCandidateId(selectedCandidateId);
      setStatus("選択結果を送信しました。ワーカーがこのフィードバックを使ってスキル履歴を更新します。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "選択結果の送信に失敗しました。");
      setStatus("");
    }
  }

  const activeCandidate =
    chatResult?.candidates.find((candidate) => candidate.candidate_id === activeCandidateId) ?? chatResult?.candidates[0] ?? null;

  if (authLoading) {
    return (
      <section className="card stack">
        <p className="muted">ログイン状態を確認しています...</p>
      </section>
    );
  }

  if (!authUser) {
    return (
      <section className="card stack" style={{ maxWidth: 720, margin: "0 auto" }}>
        <div>
          <p className="muted">ログインが必要です</p>
          <h1>チャットを使うにはログインしてください</h1>
          <p className="muted">
            回答候補の選択をユーザーごとのフィードバックとして保存し、次回以降の回答傾向に反映するため、Chat 画面はログイン済みユーザーのみ利用できます。
          </p>
        </div>
        <div className="inline" style={{ gap: 12 }}>
          <Link className="button" href="/login">
            ログイン
          </Link>
          <Link className="button secondary" href="/register">
            新規登録
          </Link>
        </div>
      </section>
    );
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
            <div className="card" style={{ padding: 14 }}>
              <strong>ログイン中: {authUser.display_name || authUser.username}</strong>
              <p className="muted">ユーザーID: {authUser.user_id}</p>
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
            <p className="muted">回答候補を1つ選んだ後、この評価をフィードバックとして送信します。</p>
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
          <button
            className="button"
            disabled={!chatResult || !selectedCandidateId || Boolean(submittedCandidateId)}
            onClick={handleFeedbackSubmit}
            type="button"
          >
            {submittedCandidateId ? "選択結果を送信済み" : "選択結果をフィードバックとして送信"}
          </button>
          {chatResult && !selectedCandidateId ? <p className="muted">生成された回答候補から、最も良いものを1つ選択してください。</p> : null}
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

          <div className="candidate-tabs" role="tablist" aria-label="回答候補">
            {chatResult.candidates.map((candidate) => {
              const isActive = activeCandidate?.candidate_id === candidate.candidate_id;
              const isSelected = selectedCandidateId === candidate.candidate_id;
              const isSubmitted = submittedCandidateId === candidate.candidate_id;
              return (
                <button
                  aria-selected={isActive}
                  className={`candidate-tab${isActive ? " active" : ""}${isSelected ? " selected" : ""}`}
                  key={candidate.candidate_id}
                  onClick={() => setActiveCandidateId(candidate.candidate_id)}
                  role="tab"
                  type="button"
                >
                  <span className="candidate-tab-rank">候補 {candidate.rank}</span>
                  <span className="candidate-tab-title">{cleanCandidateTitle(candidate.title)}</span>
                  {isSubmitted ? <span className="candidate-tab-status">送信済み</span> : null}
                  {!isSubmitted && isSelected ? <span className="candidate-tab-status">選択中</span> : null}
                </button>
              );
            })}
          </div>

          {activeCandidate ? (
            <article className={`candidate-detail${selectedCandidateId === activeCandidate.candidate_id ? " selected" : ""}`}>
              <div className="candidate-detail-header">
                <div>
                  <p className="muted">候補 {activeCandidate.rank}</p>
                  <h2>{cleanCandidateTitle(activeCandidate.title)}</h2>
                </div>
                <div className="tag-row">
                  {activeCandidate.style_tags.map((tag) => (
                    <span className="tag" key={tag}>
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <MarkdownText text={activeCandidate.answer_text} />
              <div className="candidate-action-row">
                <button
                  className={selectedCandidateId === activeCandidate.candidate_id ? "button secondary" : "button"}
                  disabled={Boolean(submittedCandidateId)}
                  onClick={() => handleCandidateChoice(activeCandidate.candidate_id)}
                  type="button"
                >
                  {submittedCandidateId === activeCandidate.candidate_id
                    ? "送信済み"
                    : selectedCandidateId === activeCandidate.candidate_id
                      ? "この回答を選択中"
                      : "この回答を選択"}
                </button>
                {selectedCandidateId && selectedCandidateId !== activeCandidate.candidate_id ? (
                  <p className="muted">別の候補を選択中です。この候補に変える場合はボタンを押してください。</p>
                ) : null}
              </div>
            </article>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
