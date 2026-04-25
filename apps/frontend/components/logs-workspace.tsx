"use client";

import { FormEvent, useState } from "react";

import { apiFetch } from "../lib/api";

type SessionLog = {
  session_id: string;
  user_id: string;
  messages: Array<{
    chat_message_id: string;
    question_text: string;
    skills_enabled: boolean;
    active_skill_revision_id: string | null;
    candidates: Array<{
      candidate_id: string;
      title: string;
      style_tags: string[];
      answer_text: string;
    }>;
    selection: {
      selected_candidate_id: string;
      satisfaction_score: number;
      clarity_score: number;
      comment: string | null;
    } | null;
    retrievals: Array<{ chunk_id: string; score: number; text: string }>;
    created_at: string;
  }>;
};

export function LogsWorkspace() {
  const [userId, setUserId] = useState("");
  const [logs, setLogs] = useState<SessionLog[]>([]);
  const [error, setError] = useState("");

  async function handleLoad(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await apiFetch<SessionLog[]>(`/api/chat/logs/${userId}`);
      setLogs(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "会話ログの取得に失敗しました。");
      setLogs([]);
    }
  }

  return (
    <div className="stack">
      <section className="card stack">
        <div>
          <p className="muted">会話ログ確認</p>
          <h1>セッション、回答候補、検索結果、評価を確認</h1>
        </div>
        <form className="grid-2" onSubmit={handleLoad}>
          <label className="field">
            <span>ユーザーID</span>
            <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="学習者の user_id を入力" />
          </label>
          <div style={{ alignSelf: "end" }}>
            <button className="button" type="submit">
              会話ログを読み込む
            </button>
          </div>
        </form>
        {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
      </section>

      {logs.map((session) => (
        <section className="card stack" key={session.session_id}>
          <div>
            <h2>セッション {session.session_id}</h2>
            <p className="muted">ユーザー: {session.user_id}</p>
          </div>
          {session.messages.map((message) => (
            <article className="card stack" key={message.chat_message_id} style={{ padding: 16 }}>
              <div>
                <p className="muted">{new Date(message.created_at).toLocaleString()}</p>
                <h3>{message.question_text}</h3>
                <p className="muted">
                  スキル有効={String(message.skills_enabled)} / 有効リビジョン={message.active_skill_revision_id ?? "なし"}
                </p>
              </div>
              <div className="grid-3">
                {message.candidates.map((candidate) => (
                  <div className="candidate" key={candidate.candidate_id}>
                    <strong>{candidate.title}</strong>
                    <div className="tag-row">
                      {candidate.style_tags.map((tag) => (
                        <span className="tag" key={tag}>
                          {tag}
                        </span>
                      ))}
                    </div>
                    <p>{candidate.answer_text}</p>
                  </div>
                ))}
              </div>
              <div className="grid-2">
                <div className="card" style={{ padding: 14 }}>
                  <strong>選択結果</strong>
                  {message.selection ? (
                    <>
                      <p className="muted">選択候補: {message.selection.selected_candidate_id}</p>
                      <p className="muted">満足度: {message.selection.satisfaction_score}</p>
                      <p className="muted">わかりやすさ: {message.selection.clarity_score}</p>
                      <p>{message.selection.comment}</p>
                    </>
                  ) : (
                    <p className="muted">まだ選択結果は保存されていません。</p>
                  )}
                </div>
                <div className="card" style={{ padding: 14 }}>
                  <strong>検索結果</strong>
                  {message.retrievals.length ? (
                    message.retrievals.map((retrieval) => (
                      <div key={retrieval.chunk_id}>
                        <p className="muted">
                          {retrieval.chunk_id} / {retrieval.score.toFixed(4)}
                        </p>
                        <p>{retrieval.text}</p>
                      </div>
                    ))
                  ) : (
                    <p className="muted">検索ログは保存されていません。</p>
                  )}
                </div>
              </div>
            </article>
          ))}
        </section>
      ))}
    </div>
  );
}
