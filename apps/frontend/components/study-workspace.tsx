"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { apiFetch } from "../lib/api";

type AuthUserResponse = {
  user_id: string;
  username: string;
  display_name: string | null;
  active_skill_revision_id: string | null;
};

type GroupName = "A" | "B" | "C";
type AssessmentType = "pre_test" | "mini_test" | "post_test";

type RunStartResponse = {
  run_id: string;
  user_id: string;
  group: GroupName;
  skills_enabled: boolean;
  cycle_count: number;
  created_at: string;
};

type MaterialResponse = {
  material_id: string;
  run_id: string;
  cycle_index: number;
  group: GroupName;
  source_type: "generated" | "fixed";
  content_text: string;
  difficulty: string | null;
  created_at: string;
};

type McqQuestion = {
  question_id: string;
  stem: string;
  choices: string[];
  correct_choice_index: number;
};

type AssessmentStartResponse = {
  assessment_attempt_id: string;
  assessment_id: string;
  assessment_type: AssessmentType;
  cycle_index: number | null;
  started_at: string;
  content_json: { questions: McqQuestion[] };
};

type AssessmentSubmitResponse = {
  assessment_attempt_id: string;
  submitted_at: string;
  duration_seconds: number;
  score: number;
  max_score: number;
  per_question_correct: Array<{ question_id: string; is_correct: boolean }>;
};

type MasteryEstimateResponse = {
  mastery_estimate_id: string;
  run_id: string;
  cycle_index: number;
  estimate_json: {
    mastery_estimate: number;
    confidence: number;
    evidence_summary: string;
    next_difficulty_recommendation: "easy" | "medium" | "hard";
  };
  created_at: string;
};

type ChatAskResponse = {
  chat_turn_id: string;
  answer_text: string;
  created_at: string;
};

type Step =
  | { kind: "idle" }
  | { kind: "pre_test" }
  | { kind: "material"; cycle_index: number }
  | { kind: "mini_test"; cycle_index: number }
  | { kind: "post_test" }
  | { kind: "finished" };

function formatSeconds(seconds: number | null | undefined) {
  if (seconds == null) return "-";
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return minutes ? `${minutes}分${remainder}秒` : `${remainder}秒`;
}

export function StudyWorkspace() {
  const [authUser, setAuthUser] = useState<AuthUserResponse | null>(null);
  const [authLoading, setAuthLoading] = useState(true);

  const [group, setGroup] = useState<GroupName>("A");
  const [cycleCount] = useState(3);

  const [run, setRun] = useState<RunStartResponse | null>(null);
  const [step, setStep] = useState<Step>({ kind: "idle" });

  const [material, setMaterial] = useState<MaterialResponse | null>(null);
  const [materialPresentedAt, setMaterialPresentedAt] = useState<Date | null>(null);
  const [materialReadConfirmedAt, setMaterialReadConfirmedAt] = useState<Date | null>(null);
  const [materialReadDurationSeconds, setMaterialReadDurationSeconds] = useState<number | null>(null);

  const [assessment, setAssessment] = useState<AssessmentStartResponse | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitted, setSubmitted] = useState<AssessmentSubmitResponse | null>(null);

  const [mastery, setMastery] = useState<MasteryEstimateResponse | null>(null);

  const [chatQuestion, setChatQuestion] = useState("");
  const [chatHistory, setChatHistory] = useState<Array<{ q: string; a: string; at: string }>>([]);
  const [chatStatus, setChatStatus] = useState("");

  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const canChat = useMemo(() => {
    if (!run) return false;
    if (run.group === "C") return false;
    if (!material) return false;
    if (step.kind !== "material") return false;
    // backend guard: chat allowed only before read_confirm is saved
    return materialReadConfirmedAt === null;
  }, [run, material, step.kind, materialReadConfirmedAt]);

  useEffect(() => {
    async function loadAuth() {
      try {
        const currentUser = await apiFetch<AuthUserResponse>("/api/auth/me");
        setAuthUser(currentUser);
      } catch {
        setAuthUser(null);
      } finally {
        setAuthLoading(false);
      }
    }
    loadAuth();
  }, []);

  async function startRun(event: FormEvent) {
    event.preventDefault();
    if (!authUser) {
      setError("学習フローを開始するにはログインが必要です。");
      return;
    }
    setError("");
    setStatus("run を開始しています...");
    try {
      const created = await apiFetch<RunStartResponse>("/api/runs/start", {
        method: "POST",
        body: JSON.stringify({ user_id: authUser.user_id, group, cycle_count: cycleCount }),
      });
      setRun(created);
      setStep({ kind: "pre_test" });
      setMaterial(null);
      setAssessment(null);
      setAnswers({});
      setSubmitted(null);
      setMastery(null);
      setChatHistory([]);
      setMaterialPresentedAt(null);
      setMaterialReadConfirmedAt(null);
      setMaterialReadDurationSeconds(null);
      setStatus("Pre-test を開始します。");
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "run の開始に失敗しました。");
    }
  }

  async function startAssessment(assessmentType: AssessmentType, cycleIndex: number | null) {
    if (!run) return;
    setError("");
    setStatus("テストを準備しています...");
    setAssessment(null);
    setSubmitted(null);
    setAnswers({});
    try {
      const started = await apiFetch<AssessmentStartResponse>("/api/assessments/start", {
        method: "POST",
        body: JSON.stringify({ run_id: run.run_id, assessment_type: assessmentType, cycle_index: cycleIndex }),
      });
      setAssessment(started);
      setStatus("テストを開始しました。回答して送信してください（時間制限なし）。");
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "テスト開始に失敗しました。");
    }
  }

  async function submitAssessment() {
    if (!assessment) return;
    setError("");
    setStatus("回答を送信して採点しています...");
    try {
      const payloadAnswers = Object.entries(answers).map(([question_id, choice_index]) => ({
        question_id,
        choice_index,
      }));
      const response = await apiFetch<AssessmentSubmitResponse>("/api/assessments/submit", {
        method: "POST",
        body: JSON.stringify({
          assessment_attempt_id: assessment.assessment_attempt_id,
          submitted_at: new Date().toISOString(),
          answers: payloadAnswers,
        }),
      });
      setSubmitted(response);
      setStatus(`採点が完了しました（${response.score}/${response.max_score}）。`);
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "提出に失敗しました。");
    }
  }

  async function loadNextMaterial(cycleIndex: number) {
    if (!run) return;
    setError("");
    setStatus("教材を準備しています...");
    setMaterial(null);
    setMaterialPresentedAt(null);
    setMaterialReadConfirmedAt(null);
    setMaterialReadDurationSeconds(null);
    setChatHistory([]);
    try {
      const response = await apiFetch<MaterialResponse>("/api/materials/next", {
        method: "POST",
        body: JSON.stringify({ run_id: run.run_id, cycle_index: cycleIndex }),
      });
      setMaterial(response);
      setMaterialPresentedAt(new Date());
      setStep({ kind: "material", cycle_index: cycleIndex });
      setStatus("教材を読み、読了したら「読了」ボタンを押してください。");
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "教材取得に失敗しました。");
    }
  }

  async function confirmRead() {
    if (!run || !material || !materialPresentedAt) return;
    const readConfirmedAt = new Date();
    setMaterialReadConfirmedAt(readConfirmedAt);
    setError("");
    setStatus("読了を記録しています...");
    try {
      const response = await apiFetch<{ material_read_id: string; duration_seconds: number }>("/api/materials/read_confirm", {
        method: "POST",
        body: JSON.stringify({
          run_id: run.run_id,
          material_id: material.material_id,
          presented_at: materialPresentedAt.toISOString(),
          read_confirmed_at: readConfirmedAt.toISOString(),
        }),
      });
      setMaterialReadDurationSeconds(response.duration_seconds);
      setStatus(`読了を記録しました（所要時間: ${formatSeconds(response.duration_seconds)}）。ミニテストを開始してください。`);
      setStep({ kind: "mini_test", cycle_index: material.cycle_index });
    } catch (requestError) {
      setMaterialReadConfirmedAt(null);
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "読了記録に失敗しました。");
    }
  }

  async function handleChatAsk(event: FormEvent) {
    event.preventDefault();
    if (!run || !material) return;
    if (!canChat) return;
    const question = chatQuestion.trim();
    if (!question) return;
    setChatQuestion("");
    setChatStatus("回答を生成しています...");
    setError("");
    try {
      const response = await apiFetch<ChatAskResponse>("/api/chat/ask", {
        method: "POST",
        body: JSON.stringify({ run_id: run.run_id, material_id: material.material_id, question_text: question }),
      });
      setChatHistory((current) => [...current, { q: question, a: response.answer_text, at: response.created_at }]);
      setChatStatus("");
    } catch (requestError) {
      setChatStatus("");
      setError(requestError instanceof Error ? requestError.message : "チャットに失敗しました。");
    }
  }

  async function estimateAndAdvance(cycleIndex: number) {
    if (!run) return;
    setError("");
    setStatus("理解度を推定しています...");
    try {
      const response = await apiFetch<MasteryEstimateResponse>("/api/mastery/estimate", {
        method: "POST",
        body: JSON.stringify({ run_id: run.run_id, cycle_index: cycleIndex }),
      });
      setMastery(response);
      if (cycleIndex < run.cycle_count) {
        setStatus(`理解度推定が完了しました（mastery=${response.estimate_json.mastery_estimate.toFixed(2)}）。次の教材へ進みます。`);
        await loadNextMaterial(cycleIndex + 1);
      } else {
        setStatus(`理解度推定が完了しました（mastery=${response.estimate_json.mastery_estimate.toFixed(2)}）。最終テストへ進みます。`);
        setStep({ kind: "post_test" });
        setMaterial(null);
        setAssessment(null);
        setAnswers({});
        setSubmitted(null);
      }
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "理解度推定に失敗しました。");
    }
  }

  async function finish() {
    if (!run) return;
    setError("");
    setStatus("run を終了しています...");
    try {
      await apiFetch("/api/runs/finish", { method: "POST", body: JSON.stringify({ run_id: run.run_id }) });
      setStep({ kind: "finished" });
      setStatus("run を終了しました。");
    } catch (requestError) {
      setStatus("");
      setError(requestError instanceof Error ? requestError.message : "run の終了に失敗しました。");
    }
  }

  useEffect(() => {
    if (!run) return;
    if (step.kind === "pre_test") {
      void startAssessment("pre_test", null);
    }
    if (step.kind === "post_test") {
      void startAssessment("post_test", null);
    }
  }, [run, step.kind]);

  // Auto advance from pre-test submit → cycle1 material
  useEffect(() => {
    if (!run) return;
    if (step.kind !== "pre_test") return;
    if (!submitted) return;
    void loadNextMaterial(1);
  }, [run, step.kind, submitted]);

  // Auto advance from post-test submit → finish run
  useEffect(() => {
    if (!run) return;
    if (step.kind !== "post_test") return;
    if (!submitted) return;
    void finish();
  }, [run, step.kind, submitted]);

  const currentQuestions = assessment?.content_json?.questions ?? [];
  const answeredCount = useMemo(() => Object.keys(answers).length, [answers]);
  const allAnswered = currentQuestions.length > 0 && answeredCount === currentQuestions.length;

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
          <h1>学習フローを開始するにはログインしてください</h1>
          <p className="muted">実験 run と学習ログをユーザーに紐づけるため、ログイン済みユーザーのみ利用できます。</p>
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
    <section className="stack" style={{ maxWidth: 960, margin: "0 auto" }}>
      <header className="card stack">
        <p className="muted">Study flow（Pre → Cycle1..3 → Post）</p>
        <h1>学習セッション</h1>
        <p className="muted">
          チャットは教材閲覧中のみ利用できます。教材・テストとも時間制限はありませんが、所要時間はログとして保存されます。
        </p>
        {run ? (
          <div className="inline" style={{ gap: 16, flexWrap: "wrap" }}>
            <span className="badge">run_id: {run.run_id}</span>
            <span className="badge">group: {run.group}</span>
            <span className="badge">skills_enabled: {String(run.skills_enabled)}</span>
            <span className="badge">cycle_count: {run.cycle_count}</span>
          </div>
        ) : null}
      </header>

      {!run ? (
        <form className="card stack" onSubmit={startRun}>
          <h2>run を開始</h2>
          <label className="field">
            <span>条件（Group）</span>
            <select onChange={(event) => setGroup(event.target.value as GroupName)} value={group}>
              <option value="A">A（Skillsあり / 適応）</option>
              <option value="B">B（Skillsなし / 非適応）</option>
              <option value="C">C（書籍学習 / 固定教材）</option>
            </select>
          </label>
          <button className="button" type="submit">
            開始
          </button>
          <p className="muted">cycle_count は MVP では {cycleCount} 固定です。</p>
        </form>
      ) : null}

      {run && (step.kind === "pre_test" || step.kind === "mini_test" || step.kind === "post_test") ? (
        <div className="card stack">
          <h2>
            {step.kind === "pre_test"
              ? "初回テスト（Pre-test）"
              : step.kind === "post_test"
              ? "最終テスト（Post-test）"
              : `ミニテスト（Cycle ${step.cycle_index}）`}
          </h2>
          <p className="muted">時間制限なし。開始・提出時刻と所要時間をログ保存します。</p>

          {!assessment ? <p className="muted">テストを読み込んでいます...</p> : null}

          {assessment ? (
            <div className="stack">
              {currentQuestions.map((q, idx) => (
                <div className="card stack" key={q.question_id} style={{ padding: 16 }}>
                  <p className="muted">
                    Q{idx + 1}（{q.question_id}）
                  </p>
                  <p style={{ fontWeight: 600 }}>{q.stem}</p>
                  <div className="stack" style={{ gap: 8 }}>
                    {q.choices.map((choice, choiceIndex) => (
                      <label className="inline" key={choiceIndex} style={{ alignItems: "center", gap: 8 }}>
                        <input
                          checked={answers[q.question_id] === choiceIndex}
                          disabled={Boolean(submitted)}
                          name={q.question_id}
                          onChange={() => setAnswers((cur) => ({ ...cur, [q.question_id]: choiceIndex }))}
                          type="radio"
                        />
                        <span>{choice}</span>
                      </label>
                    ))}
                  </div>
                  {submitted ? (
                    <p className="muted">
                      {submitted.per_question_correct.find((item) => item.question_id === q.question_id)?.is_correct ? "✅ 正解" : "❌ 不正解"}
                    </p>
                  ) : null}
                </div>
              ))}

              <div className="inline" style={{ gap: 12, alignItems: "center" }}>
                <button className="button" disabled={!assessment || Boolean(submitted) || !allAnswered} onClick={submitAssessment} type="button">
                  回答を送信して採点
                </button>
                <span className="muted">
                  回答済み: {answeredCount}/{currentQuestions.length}
                </span>
              </div>

              {submitted ? (
                <p className="muted">
                  得点: {submitted.score}/{submitted.max_score}（所要時間: {formatSeconds(submitted.duration_seconds)}）
                </p>
              ) : null}

              {step.kind === "mini_test" && submitted ? (
                <button className="button" onClick={() => estimateAndAdvance(step.cycle_index)} type="button">
                  理解度を推定して次へ
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {run && step.kind === "material" && material ? (
        <div className="card stack">
          <div className="inline" style={{ justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <h2>教材（Cycle {step.cycle_index}）</h2>
            <span className="badge">source: {material.source_type}</span>
          </div>
          <p className="muted">
            チャットは教材閲覧中のみ利用できます（読了後は不可）。時間制限はありません。
          </p>

          <article className="card" style={{ padding: 16, whiteSpace: "pre-wrap" }}>
            {material.content_text}
          </article>

          <div className="inline" style={{ gap: 12, flexWrap: "wrap" }}>
            <button className="button" disabled={Boolean(materialReadConfirmedAt)} onClick={confirmRead} type="button">
              読了
            </button>
            <span className="muted">
              閲覧開始: {materialPresentedAt ? materialPresentedAt.toLocaleTimeString() : "-"} / 読了:{" "}
              {materialReadConfirmedAt ? materialReadConfirmedAt.toLocaleTimeString() : "-"} / 所要時間:{" "}
              {formatSeconds(materialReadDurationSeconds)}
            </span>
          </div>

          <div className="card stack" style={{ padding: 16 }}>
            <h3>教材について質問（教材閲覧中のみ）</h3>
            {run.group === "C" ? <p className="muted">Group C ではチャットは利用できません。</p> : null}
            {!canChat ? <p className="muted">チャットは「読了」前のみ利用できます。</p> : null}
            <form className="inline" onSubmit={handleChatAsk} style={{ gap: 12, alignItems: "center" }}>
              <input
                disabled={!canChat}
                onChange={(event) => setChatQuestion(event.target.value)}
                placeholder="例: この段落の要点は？"
                value={chatQuestion}
              />
              <button className="button secondary" disabled={!canChat || !chatQuestion.trim()} type="submit">
                質問する
              </button>
            </form>
            {chatStatus ? <p className="muted">{chatStatus}</p> : null}
            {chatHistory.length ? (
              <div className="stack" style={{ gap: 12 }}>
                {chatHistory.map((item, idx) => (
                  <div className="card stack" key={idx} style={{ padding: 12 }}>
                    <p style={{ fontWeight: 600 }}>Q: {item.q}</p>
                    <p style={{ whiteSpace: "pre-wrap" }}>A: {item.a}</p>
                    <p className="muted">{new Date(item.at).toLocaleString()}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">まだ質問はありません。</p>
            )}
          </div>

          <p className="muted">読了後、ミニテストへ進みます（画面遷移は自動）。</p>
        </div>
      ) : null}

      {step.kind === "finished" ? (
        <section className="card stack">
          <h2>完了</h2>
          <p className="muted">run を終了しました。ログのエクスポートはバックエンドの `/api/experiments/export.csv` を利用してください。</p>
          <button
            className="button"
            onClick={() => {
              setRun(null);
              setStep({ kind: "idle" });
              setStatus("");
              setError("");
            }}
            type="button"
          >
            もう一度実施
          </button>
        </section>
      ) : null}

      {status ? <p className="muted">{status}</p> : null}
      {error ? <p style={{ color: "#8d3f24" }}>{error}</p> : null}
      {mastery ? (
        <div className="card stack">
          <h3>直近の理解度推定</h3>
          <p className="muted">
            Cycle {mastery.cycle_index}: mastery={mastery.estimate_json.mastery_estimate.toFixed(2)} / confidence=
            {mastery.estimate_json.confidence.toFixed(2)} / next={mastery.estimate_json.next_difficulty_recommendation}
          </p>
          <p className="muted">{mastery.estimate_json.evidence_summary}</p>
        </div>
      ) : null}
    </section>
  );
}

