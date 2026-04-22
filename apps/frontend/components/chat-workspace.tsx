"use client";

import { FormEvent, useState } from "react";

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
  retrievals: Array<{ chunk_id: string; document_id: string; score: number; text: string }>;
  candidates: Candidate[];
};

export function ChatWorkspace() {
  const [displayName, setDisplayName] = useState("Research Learner");
  const [userId, setUserId] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [question, setQuestion] = useState("二次方程式の解き方を教えて");
  const [skillsEnabled, setSkillsEnabled] = useState(true);
  const [candidateCount, setCandidateCount] = useState(3);
  const [chatResult, setChatResult] = useState<ChatGenerateResponse | null>(null);
  const [selectedCandidateId, setSelectedCandidateId] = useState("");
  const [satisfactionScore, setSatisfactionScore] = useState(8);
  const [clarityScore, setClarityScore] = useState(8);
  const [comment, setComment] = useState("例題つきの説明がわかりやすい");
  const [status, setStatus] = useState<string>("");
  const [error, setError] = useState<string>("");

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
    setStatus("Generating candidates...");
    try {
      const resolvedUserId = await ensureUser();
      const response = await apiFetch<ChatGenerateResponse>("/api/chat/generate", {
        method: "POST",
        body: JSON.stringify({
          user_id: resolvedUserId,
          question,
          candidate_count: candidateCount,
          skills_enabled: skillsEnabled,
          session_id: sessionId || null,
          experiment_condition: skillsEnabled ? "skills_on" : "skills_off",
        }),
      });
      setChatResult(response);
      setSessionId(response.session_id);
      setSelectedCandidateId(response.candidates[0]?.candidate_id ?? "");
      setStatus("Candidates generated.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Generation failed");
      setStatus("");
    }
  }

  async function handleSelection(candidateId: string) {
    if (!chatResult) return;
    setError("");
    setStatus("Saving selection...");
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
      setStatus("Selection saved. Worker will update the skill revision.");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Selection failed");
      setStatus("");
    }
  }

  return (
    <div className="stack">
      <section className="hero">
        <div className="card stack">
          <div>
            <p className="muted">Research Prototype</p>
            <h1>Adaptive tutoring with answer-choice feedback</h1>
            <p className="muted">
              Generate three answer candidates, let the learner choose one, and feed that back into the next turn.
            </p>
          </div>
          <form className="stack" onSubmit={handleGenerate}>
            <div className="grid-2">
              <label className="field">
                <span>Display name</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
              </label>
              <label className="field">
                <span>User ID</span>
                <input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="Auto-created if blank" />
              </label>
            </div>
            <div className="grid-2">
              <label className="field">
                <span>Session ID</span>
                <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="Continue a previous chat session" />
              </label>
              <label className="field">
                <span>Candidate count</span>
                <select value={candidateCount} onChange={(event) => setCandidateCount(Number(event.target.value))}>
                  <option value={3}>3</option>
                  <option value={2}>2</option>
                  <option value={4}>4</option>
                </select>
              </label>
            </div>
            <label className="field">
              <span>Question</span>
              <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
            </label>
            <label className="field">
              <span>Experiment condition</span>
              <select value={skillsEnabled ? "on" : "off"} onChange={(event) => setSkillsEnabled(event.target.value === "on")}>
                <option value="on">skills_enabled = true</option>
                <option value="off">skills_enabled = false</option>
              </select>
            </label>
            <button className="button" type="submit">
              Generate candidates
            </button>
          </form>
        </div>

        <div className="card stack">
          <div>
            <h2>Selection feedback</h2>
            <p className="muted">These values are submitted when a candidate is selected.</p>
          </div>
          <label className="field">
            <span>Satisfaction (1-10)</span>
            <input type="number" min={1} max={10} value={satisfactionScore} onChange={(event) => setSatisfactionScore(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>Clarity (1-10)</span>
            <input type="number" min={1} max={10} value={clarityScore} onChange={(event) => setClarityScore(Number(event.target.value))} />
          </label>
          <label className="field">
            <span>Comment</span>
            <textarea value={comment} onChange={(event) => setComment(event.target.value)} />
          </label>
          <div className="card" style={{ padding: 14 }}>
            <strong>Current status</strong>
            <p className="muted">{status || "Idle"}</p>
            {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
          </div>
        </div>
      </section>

      {chatResult ? (
        <section className="stack">
          <div className="card stack">
            <div className="grid-2">
              <div>
                <h2>Run metadata</h2>
                <p className="muted">Session: {chatResult.session_id}</p>
                <p className="muted">Chat message: {chatResult.chat_message_id}</p>
              </div>
              <div>
                <h2>Retrievals</h2>
                <p className="muted">{chatResult.retrievals.length} chunk(s) were used.</p>
              </div>
            </div>
            <div className="stack">
              {chatResult.retrievals.map((retrieval) => (
                <div className="card" key={retrieval.chunk_id} style={{ padding: 14 }}>
                  <strong>{retrieval.chunk_id}</strong>
                  <p className="muted">Score: {retrieval.score.toFixed(4)}</p>
                  <p>{retrieval.text}</p>
                </div>
              ))}
              {chatResult.retrievals.length === 0 ? <p className="muted">No indexed chunks yet. Ingest a document from Admin first.</p> : null}
            </div>
          </div>

          <div className="grid-3">
            {chatResult.candidates.map((candidate) => (
              <article className="candidate" key={candidate.candidate_id}>
                <div>
                  <p className="muted">Candidate {candidate.rank}</p>
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
                  {selectedCandidateId === candidate.candidate_id ? "Selected" : "Choose this answer"}
                </button>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

