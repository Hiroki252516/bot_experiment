# 02 Architecture

## 1. 設計方針

本システムは、PDF教材を Agent Skills 化し、被験者のテスト結果から Learner Agent Skill を更新しながら、10 回の教材生成・テスト生成・理解度推定ループを実行する研究用 Web アプリである。

runtime で RAG、embedding search、vector DB retrieval は行わない。PDF 教材は ingestion 時に構造化し、Document Agent Skill として保存する。学習者の理解状態はテスト結果から Learner Agent Skill として保存する。生成時には、これらの Agent Skill JSON を deterministic に prompt context へ変換して LLM に渡す。

## 2. Monorepo 構成

```text
.
├── apps/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── api/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   └── generation/
│   │   └── tests/
│   ├── frontend/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── types/
│   └── worker/
│       ├── app/
│       │   ├── ingestion/
│       │   ├── skills/
│       │   └── jobs/
│       └── tests/
├── packages/
│   └── shared-schemas/
├── docs/
├── docker-compose.yml
└── README.md
```

## 3. コンポーネント責務

### frontend

- 管理者画面
- PDF upload UI
- 被験者ログイン
- 初回テスト生成・受験 UI
- 教材閲覧 UI
- サイクルテスト UI
- 最終テスト UI
- 成績向上 dashboard
- 実験進捗表示

### backend

- REST API
- run 状態管理
- PDF upload 受付
- worker job 起動
- Document Agent Skill 読み出し
- Learner Agent Skill 読み出し・更新
- LLM provider 呼び出し
- テスト生成
- 教材生成
- 採点
- 理解度推定
- CSV export

### worker

- PDF parsing
- Document Agent Skill extraction
- Document Agent Skill validation
- 長時間 LLM job の実行
- optional async material/test generation

### database

- users
- source_documents
- document_skill_revisions
- document_skill_entries
- experiment_runs
- generated_assessments
- assessment_attempts
- generated_materials
- material_reads
- learner_skill_revisions
- generation_logs
- export_jobs

## 4. Agent Skills Architecture

### 4.1 Document Agent Skill

PDF 教材から抽出した学習対象の構造化表現である。教材本文を毎回検索するのではなく、ingestion 時点で以下を確定する。

- 学習目標
- トピック階層
- 重要概念
- 前提知識
- 例文・例題
- よくある誤解
- 難易度マップ
- テスト設計 blueprint
- 正答根拠
- 教材範囲外として扱う内容

### 4.2 Learner Agent Skill

被験者の現在の理解状態を表す構造化プロファイルである。初回テスト後に作成し、各サイクルテスト後に更新する。

- 総合理解度
- トピック別理解度
- 理解済み項目
- 弱点項目
- 誤概念
- 次に重点化すべき項目
- 推奨難易度
- 過去生成問題 fingerprint
- evidence

### 4.3 Prompt Context Builder

generation 時に Document Agent Skill と Learner Agent Skill を deterministic に整形する。

- 初回テスト生成: Document Agent Skill のみ使用
- 初回テスト分析: Document Agent Skill + attempt result
- 教材生成: Document Agent Skill + Learner Agent Skill
- サイクルテスト生成: Document Agent Skill + Learner Agent Skill + used question fingerprints
- 最終テスト生成: Document Agent Skill + used question fingerprints
- 結果表示: attempts + Learner Agent Skill history

## 5. 状態遷移

```text
CREATED
  -> PDF_SKILL_READY
  -> RUN_STARTED
  -> INITIAL_TEST_GENERATED
  -> INITIAL_TEST_SUBMITTED
  -> CYCLE_MATERIAL_GENERATED(cycle=1)
  -> CYCLE_MATERIAL_READ(cycle=1)
  -> CYCLE_TEST_GENERATED(cycle=1)
  -> CYCLE_TEST_SUBMITTED(cycle=1)
  -> ... repeat until cycle=10
  -> FINAL_TEST_GENERATED
  -> FINAL_TEST_SUBMITTED
  -> RESULT_READY
  -> FINISHED
```

不正な状態遷移は backend で拒否し、409 Conflict を返す。

## 6. LLM Provider Layer

`GenerationProvider` 抽象を用意する。

```text
GenerationProvider
├── generate_initial_test
├── analyze_attempt
├── generate_learning_material
├── generate_cycle_test
├── update_learner_skill
├── generate_final_test
└── generate_result_summary
```

すべてのメソッドは JSON schema で出力を検証する。失敗時は retry し、最終的に validation error を generation_logs に残す。

## 7. PDF Ingestion Flow

1. 管理者が PDF を upload する。
2. backend が `source_documents` を作成する。
3. worker が PDF を parse する。
4. LLM が Document Agent Skill JSON を生成する。
5. schema validation を行う。
6. `document_skill_revisions` と `document_skill_entries` に保存する。
7. 管理者画面で ready 状態にする。

## 8. Runtime Generation Flow

### 初回テスト

- 入力: Document Agent Skill
- 出力: 学習範囲全体を覆う initial assessment
- 保存: generated_assessments

### 教材生成

- 入力: Document Agent Skill + Learner Agent Skill
- 出力: 弱点補強用教材
- 保存: generated_materials

### サイクルテスト

- 入力: Document Agent Skill + Learner Agent Skill + 過去問題 fingerprint
- 出力: 新規問題
- 保存: generated_assessments

### 最終テスト

- 入力: Document Agent Skill + 過去問題 fingerprint
- 出力: 範囲全体を測る final assessment
- 保存: generated_assessments

## 9. 非採用: Runtime RAG

以下の処理は行わない。

- PDF chunk embedding
- query embedding
- vector similarity search
- top-k chunk retrieval
- retrieval result を prompt に差し込む処理

必要な文脈は ingestion 時に構造化された Agent Skill から得る。

## 10. セキュリティ・再現性

- PDF upload は管理者のみ。
- provider/model/prompt_version/temperature/schema_version を全 generation に保存。
- PDF 原本と Document Agent Skill revision を immutable に扱う。
- Learner Agent Skill は revision append-only とする。
- テスト問題は fingerprint を保存し、重複抑制に使う。
