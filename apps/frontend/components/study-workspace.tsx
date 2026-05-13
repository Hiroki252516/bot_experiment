"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { apiFetch } from "../lib/api";

type AuthUser = { user_id: string; username: string; display_name: string | null };
type SourceDocument = { document_id: string; title: string; filename: string; status: string };
type RunState = { run_id: string; state: string; cycle_count: number; current_cycle_index: number; next_action: string };
type RunStart = { run_id: string; state: string; cycle_count: number };
type Question = {
  question_id: string;
  topic: string;
  difficulty: string;
  stem: string;
  choices: string[];
  correct_answer: string;
};
type Assessment = { assessment_id: string; title: string; questions: Question[] };
type Material = {
  material_id: string;
  cycle_index: number;
  title: string;
  content_markdown: string;
  focus_topics: string[];
  created_at: string;
};
type Result = {
  initial_score: number;
  final_score: number;
  gain_score: number;
  initial_accuracy: number;
  final_accuracy: number;
  accuracy_gain: number;
  cycle_score_trend: Array<{ cycle_index: number; score: number; max_score: number }>;
  improved_topics: string[];
  remaining_weak_topics: string[];
  ai_summary: string;
};

function stateLabel(state: string) {
  const labels: Record<string, string> = {
    RUN_STARTED: "初回テスト生成待ち",
    INITIAL_TEST_GENERATED: "初回テスト回答中",
    INITIAL_TEST_SUBMITTED: "Cycle 教材生成待ち",
    CYCLE_MATERIAL_GENERATED: "教材閲覧中",
    CYCLE_MATERIAL_READ: "Cycle テスト生成待ち",
    CYCLE_TEST_GENERATED: "Cycle テスト回答中",
    CYCLE_TEST_SUBMITTED: "次 Cycle または最終テスト待ち",
    FINAL_TEST_GENERATED: "最終テスト回答中",
    RESULT_READY: "結果表示可能",
  };
  return labels[state] ?? state;
}

export function StudyWorkspace() {
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [documentId, setDocumentId] = useState("");
  const [run, setRun] = useState<RunStart | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [material, setMaterial] = useState<Material | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const currentCycle = runState?.current_cycle_index || 1;
  const allAnswered = useMemo(() => {
    const questions = assessment?.questions ?? [];
    return questions.length > 0 && questions.every((question) => answers[question.question_id]);
  }, [answers, assessment]);

  useEffect(() => {
    async function boot() {
      try {
        const [me, docs] = await Promise.all([
          apiFetch<AuthUser>("/api/auth/me").catch(() => null),
          apiFetch<SourceDocument[]>("/api/admin/documents").catch(() => []),
        ]);
        setAuthUser(me);
        setDocuments(docs.filter((doc) => doc.status === "ready"));
        setDocumentId(docs.find((doc) => doc.status === "ready")?.document_id ?? "");
      } finally {
        setAuthLoading(false);
      }
    }
    void boot();
  }, []);

  async function refreshState(runId = run?.run_id) {
    if (!runId) return null;
    const state = await apiFetch<RunState>(`/api/runs/${runId}/state`);
    setRunState(state);
    return state;
  }

  async function startRun(event: FormEvent) {
    event.preventDefault();
    if (!authUser || !documentId) return;
    setError("");
    setStatus("run を開始しています...");
    try {
      const started = await apiFetch<RunStart>("/api/runs/start", {
        method: "POST",
        body: JSON.stringify({ user_id: authUser.user_id, document_id: documentId, cycle_count: 10 }),
      });
      setRun(started);
      setAssessment(null);
      setMaterial(null);
      setResult(null);
      setAnswers({});
      await refreshState(started.run_id);
      setStatus("run を開始しました。初回テストを生成してください。");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "run 開始に失敗しました。");
      setStatus("");
    }
  }

  async function generateInitial() {
    if (!run) return;
    setError("");
    setStatus("初回テストを生成しています...");
    await apiFetch(`/api/runs/${run.run_id}/initial-test/generate`, { method: "POST" });
    const test = await apiFetch<Assessment>(`/api/runs/${run.run_id}/initial-test`);
    setAssessment(test);
    setAnswers({});
    await refreshState();
    setStatus("初回テストを生成しました。");
  }

  async function submitInitial() {
    if (!run || !assessment) return;
    setError("");
    setStatus("初回テストを提出しています...");
    await apiFetch(`/api/runs/${run.run_id}/initial-test/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })) }),
    });
    setAssessment(null);
    setAnswers({});
    await refreshState();
    setStatus("初回テストを提出しました。Cycle 1 教材へ進んでください。");
  }

  async function generateMaterial() {
    if (!run || !runState) return;
    setError("");
    setStatus(`Cycle ${currentCycle} 教材を生成しています...`);
    await apiFetch(`/api/runs/${run.run_id}/cycles/${currentCycle}/material/generate`, { method: "POST" });
    const generated = await apiFetch<Material>(`/api/runs/${run.run_id}/cycles/${currentCycle}/material`);
    setMaterial(generated);
    await refreshState();
    setStatus("教材を生成しました。読み終えたら読了を記録してください。");
  }

  async function confirmRead() {
    if (!run || !runState) return;
    setError("");
    setStatus("読了を記録しています...");
    await apiFetch(`/api/runs/${run.run_id}/cycles/${currentCycle}/material/read-confirm`, { method: "POST" });
    await refreshState();
    setStatus("読了を記録しました。Cycle テストを生成してください。");
  }

  async function generateCycleTest() {
    if (!run || !runState) return;
    setError("");
    setStatus(`Cycle ${currentCycle} テストを生成しています...`);
    await apiFetch(`/api/runs/${run.run_id}/cycles/${currentCycle}/test/generate`, { method: "POST" });
    const test = await apiFetch<Assessment>(`/api/runs/${run.run_id}/cycles/${currentCycle}/test`);
    setAssessment(test);
    setAnswers({});
    await refreshState();
    setStatus("Cycle テストを生成しました。");
  }

  async function submitCycleTest() {
    if (!run || !assessment || !runState) return;
    setError("");
    setStatus(`Cycle ${currentCycle} テストを提出しています...`);
    await apiFetch(`/api/runs/${run.run_id}/cycles/${currentCycle}/test/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })) }),
    });
    setAssessment(null);
    setMaterial(null);
    setAnswers({});
    await refreshState();
    setStatus(currentCycle < 10 ? `Cycle ${currentCycle} を提出しました。次の教材へ進んでください。` : "Cycle 10 を提出しました。最終テストへ進んでください。");
  }

  async function generateFinal() {
    if (!run) return;
    setError("");
    setStatus("最終テストを生成しています...");
    await apiFetch(`/api/runs/${run.run_id}/final-test/generate`, { method: "POST" });
    const test = await apiFetch<Assessment>(`/api/runs/${run.run_id}/final-test`);
    setAssessment(test);
    setAnswers({});
    await refreshState();
    setStatus("最終テストを生成しました。");
  }

  async function submitFinal() {
    if (!run || !assessment) return;
    setError("");
    setStatus("最終テストを提出しています...");
    await apiFetch(`/api/runs/${run.run_id}/final-test/submit`, {
      method: "POST",
      body: JSON.stringify({ answers: Object.entries(answers).map(([question_id, answer]) => ({ question_id, answer })) }),
    });
    const summary = await apiFetch<Result>(`/api/runs/${run.run_id}/results`);
    setResult(summary);
    setAssessment(null);
    setAnswers({});
    await refreshState();
    setStatus("結果を作成しました。");
  }

  if (authLoading) {
    return <section className="card">ログイン状態を確認しています...</section>;
  }

  if (!authUser) {
    return (
      <section className="card stack" style={{ maxWidth: 720, margin: "0 auto" }}>
        <h1>ログインが必要です</h1>
        <p className="muted">10サイクル学習実験を開始するにはログインしてください。</p>
        <div className="inline" style={{ gap: 12 }}>
          <Link className="button" href="/login">ログイン</Link>
          <Link className="button secondary" href="/register">新規登録</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="stack" style={{ maxWidth: 1040, margin: "0 auto" }}>
      <header className="card stack">
        <p className="muted">Agent Skills 型 10サイクル学習実験</p>
        <h1>学習セッション</h1>
        <p className="muted">RAG ではなく、PDF から抽出した Document Agent Skill と Learner Agent Skill を使って教材・テストを生成します。</p>
        {runState ? (
          <div className="inline" style={{ gap: 10, flexWrap: "wrap" }}>
            <span className="badge">state: {stateLabel(runState.state)}</span>
            <span className="badge">cycle: {runState.current_cycle_index}/10</span>
            <span className="badge">next: {runState.next_action}</span>
          </div>
        ) : null}
        {status ? <p className="muted">{status}</p> : null}
        {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
      </header>

      {!run ? (
        <form className="card stack" onSubmit={startRun}>
          <h2>run を開始</h2>
          <label className="field">
            <span>教材</span>
            <select value={documentId} onChange={(event) => setDocumentId(event.target.value)}>
              <option value="">ready な教材を選択</option>
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>{doc.title} / {doc.filename}</option>
              ))}
            </select>
          </label>
          <button className="button" disabled={!documentId} type="submit">10サイクル run を開始</button>
          <p className="muted">ready な教材がない場合は Admin 画面で PDF upload と Document Skill extraction を実行してください。</p>
        </form>
      ) : null}

      {runState?.state === "RUN_STARTED" ? <button className="button" onClick={generateInitial}>初回テストを生成</button> : null}
      {runState?.state === "INITIAL_TEST_SUBMITTED" || (runState?.state === "CYCLE_TEST_SUBMITTED" && runState.current_cycle_index < 10) ? (
        <button className="button" onClick={generateMaterial}>Cycle {currentCycle} 教材を生成</button>
      ) : null}
      {runState?.state === "CYCLE_MATERIAL_READ" ? <button className="button" onClick={generateCycleTest}>Cycle {currentCycle} テストを生成</button> : null}
      {runState?.state === "CYCLE_TEST_SUBMITTED" && runState.current_cycle_index === 10 ? (
        <button className="button" onClick={generateFinal}>最終テストを生成</button>
      ) : null}

      {material && runState?.state === "CYCLE_MATERIAL_GENERATED" ? (
        <article className="card stack">
          <h2>{material.title}</h2>
          <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{material.content_markdown}</pre>
          <button className="button" onClick={confirmRead}>読了してテストへ進む</button>
        </article>
      ) : null}

      {assessment ? (
        <section className="card stack">
          <h2>{assessment.title}</h2>
          {assessment.questions.map((question, index) => (
            <div className="card stack" key={question.question_id} style={{ padding: 16 }}>
              <p className="muted">Q{index + 1} / {question.topic} / {question.difficulty}</p>
              <p style={{ fontWeight: 700 }}>{question.stem}</p>
              {question.choices.map((choice, choiceIndex) => (
                <label className="inline" key={choiceIndex} style={{ gap: 8 }}>
                  <input
                    checked={answers[question.question_id] === choice}
                    name={question.question_id}
                    onChange={() => setAnswers((current) => ({ ...current, [question.question_id]: choice }))}
                    type="radio"
                  />
                  <span>{choice}</span>
                </label>
              ))}
            </div>
          ))}
          {runState?.state === "INITIAL_TEST_GENERATED" ? (
            <button className="button" disabled={!allAnswered} onClick={submitInitial}>初回テストを提出</button>
          ) : null}
          {runState?.state === "CYCLE_TEST_GENERATED" ? (
            <button className="button" disabled={!allAnswered} onClick={submitCycleTest}>Cycle {currentCycle} テストを提出</button>
          ) : null}
          {runState?.state === "FINAL_TEST_GENERATED" ? (
            <button className="button" disabled={!allAnswered} onClick={submitFinal}>最終テストを提出</button>
          ) : null}
        </section>
      ) : null}

      {result ? (
        <section className="card stack">
          <h2>成績向上結果</h2>
          <div className="grid-2">
            <p>初回スコア: {result.initial_score}</p>
            <p>最終スコア: {result.final_score}</p>
            <p>点数差: {result.gain_score}</p>
            <p>正答率差: {(result.accuracy_gain * 100).toFixed(1)}%</p>
          </div>
          <p>{result.ai_summary}</p>
          <h3>Cycle score trend</h3>
          <ul>
            {result.cycle_score_trend.map((row) => (
              <li key={row.cycle_index}>Cycle {row.cycle_index}: {row.score}/{row.max_score}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
