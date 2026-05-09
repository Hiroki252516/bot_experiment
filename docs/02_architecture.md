# 02 Architecture（研究用：適応型学習サイクル）

本ドキュメントは、研究フロー（Pre → Cycle1..3 → Post）と A/B/C 条件を実装するためのシステム構成を定義する。
研究仕様の正本は `docs/07_adaptive_learning_design.md` とし、本書は実装視点で要点をまとめる。

> 2026-05 update: 新規 runtime answer-generation path は embedding / vector retrieval を使わず、ingestion 時に抽出した **Document Skill entries** を参照する。pgvector と RAG テーブルは legacy として保持する。

## 1. 採用アーキテクチャ
### Monorepo
- `apps/frontend`（Next.js）
- `apps/backend`（FastAPI）
- `apps/worker`（Python worker）
- `packages/shared-schemas`（Pydantic/TS 共有スキーマ想定）

理由:
- Docker Compose で一括起動しやすい
- frontend/backend/worker の境界が明確
- スキーマを共有しやすく、研究ログの一貫性を保ちやすい

## 2. 技術選定（研究要件との整合）
### Backend: FastAPI
- OpenAPI により研究用 UI/API の仕様が明確
- Pydantic により JSON スキーマを固定しやすい

### DB: PostgreSQL + pgvector
理由:
- 通常のリレーショナルデータとベクトル検索を同居できる
- ログ、実験データ、candidate、skill revision を一元管理できる
- 新規 Document Skill tables と legacy vector tables を同一 DB で管理できる
### DB: PostgreSQL（+ pgvector は維持）
- 実験 run、教材、テスト、所要時間、推定値、Skills 履歴を一元管理する
- 本研究では RAG を主題にしないが、インフラ制約として pgvector を残しても運用可能にする（RAG 未使用でも起動可能）

### Frontend: Next.js
- 研究フローを「状態遷移」として UI に落とし込みやすい
- ログ/実験 run の確認 UI を作りやすい

### Worker
理由:
- Preference Skill 更新、Document Skill extraction などを API リクエストから分離できる
- Skills 更新や理解度推定を API リクエストから切り離す（将来の再実行・再計算が容易）
- 研究段階では同期実行でもよいが、非同期ジョブに分離できる構成を維持する

## 3. Docker Compose 構成
必須サービス:
1. `frontend`
2. `backend`
3. `worker`
4. `db`

要件:
- named volume で DB 永続化
- backend/worker は db healthcheck 成功後に起動
- `.env` を読み込む

## 4. コンポーネント責務（研究フロー中心）
### frontend
- 実験 run 開始（A/B/C の選択または割当表示）
- Pre-test（MCQ）画面
- 教材閲覧画面（読了ボタン、チャット入力は教材閲覧中のみ）
- Mini-test（MCQ）画面（Cycle 1..3）
- Post-test（MCQ）画面
- 進捗表示（Cycle の現在地）
- 研究ログ確認（最低限：run 一覧と詳細）

### backend
- REST API
- session / conversation 管理
- Document Skill context 構築
- skill 読み出し
- LLM candidate generation
- 選択結果保存
- CSV export

### worker
- document ingestion
- Document Skill extraction
- Document Skill revision / entries 保存
- skill updater
- 非同期ジョブ管理

### db
- 学習資料
- Document Skill revision / entries
- embeddings
- users
- conversations
- turns
- candidates
- feedback
- skills
- skill revisions
- experiment runs
- 研究フロー API（run 開始/終了、教材提示、テスト開始/提出、採点、推定）
- チャット API（教材閲覧中のみ許可）
- Skills ON/OFF の厳密な差分を担保（A は参照/更新/反映、B はしない）
- エクスポート（CSV/JSONL）

### worker
- skill updater（A のみ）
- mastery estimator（必要なら job として分離）
- 再計算系（管理 API から再実行できる余地を残す）

### db
研究に必要な正本データ:
- users / runs（A/B/C 条件、skills_enabled）
- materials（教材本文）
- material_reads（教材閲覧の開始/読了/所要時間）
- assessments（テスト定義：pre/mini/post）
- assessment_attempts（回答、採点、開始/提出/所要時間）
- mastery_estimates（理解度推定履歴）
- chat_turns（教材紐付け、A/Bのみ）
- skills / skill_revisions（Aのみ更新）

## 5. Provider abstraction（RAG 依存を分離）
本研究で必須なのは「教材生成・ミニテスト生成・読解支援回答・理解度推定・Skills 更新」であり、いずれも LLM による structured output（JSON）を前提とする。

### GenerationProvider（必須）
例:
- `generate_material(input) -> MaterialJson`
- `generate_quiz(input) -> AssessmentJson`
- `answer_question(input) -> ChatAnswerJson`
- `estimate_mastery(input) -> MasteryEstimateJson`
- `extract_skill_delta(input) -> SkillDeltaJson`（Aのみ）

### EmbeddingProvider（任意 / 将来）
RAG を使う実験に拡張する場合に備えて保持するが、本研究の主要フローでは必須としない。

## 6. 主要フロー（Pre → Cycle1..3 → Post）
### A. Run 開始から Pre-test
1. frontend が run を開始（group=A/B/C, skills_enabled を確定）
2. Pre-test を開始し回答を提出
3. backend が採点し、結果を保存

### B. サイクル（Cycle 1..3）
1. backend が教材を提示（A/B: 生成、C: 固定）
2. ユーザーが教材を閲覧し、読了ボタンで確定（所要時間保存）
3. ミニテスト開始 → 回答提出 → 採点（所要時間保存）
4. backend/worker が理解度推定を保存
5. A の場合のみ、worker が skill 更新を実行し次回に反映

### C. Post-test と終了
1. Post-test 開始 → 回答提出 → 採点
2. run を終了し、エクスポート可能な状態にする

## 7. Prompt 設計方針（A/B差分の担保）
- すべての LLM 生成は strict JSON schema を前提とする
- A（Skillsあり）:
  - `skill_profile` を生成入力に含める
  - 学習ログ（直近の誤答、所要時間、質問履歴）を要約して入力に含める
- B（Skillsなし）:
  - `skill_profile` を入力に含めない
  - 学習ログは保存のみ（生成入力の「学習者特性」として使わない）
- チャットは教材閲覧中のみ許可し、教材本文を入力に含める（逸脱防止）

## 8. 障害時方針
- LLM 呼び出し失敗時は 5xx と相関 ID を返す
- skill 更新失敗時:
  - A の run 自体は継続可能（推定や次教材生成は継続）
  - skill update job は再試行可能な形でログを残す
- 時間制限は設けないが、開始/提出/読了イベントが欠けた場合は run を完走できないため、UI と API で必須入力を強制する
