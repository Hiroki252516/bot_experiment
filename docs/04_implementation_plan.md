# 04 Implementation Plan

## 1. 実装方針

最初に、1 つの PDF 教材、1 人の被験者、10 サイクル、最終テスト、結果表示までを end-to-end で完走する MVP を作る。RAG は実装しない。PDF は Document Agent Skill に変換し、被験者の状態は Learner Agent Skill として revision 保存する。

## Phase 0: 仕様同期

### 作業

- docs の更新
- RAG 非採用方針の明記
- 10 サイクル固定の定義
- Agent Skill schema の確定

### 受け入れ条件

- `docs/00`〜`docs/07` が同じ実験フローを指している。
- `cycle_count=10` が正本仕様になっている。

## Phase 1: Monorepo / Docker skeleton

### 作業

- `apps/backend`
- `apps/frontend`
- `apps/worker`
- `packages/shared-schemas`
- Dockerfile
- docker-compose.yml
- env sample

### 受け入れ条件

- `docker compose up --build` で backend/frontend/db/worker が起動する。
- `GET /api/health` が 200 を返す。

## Phase 2: DB schema / migrations

### 作業

- SQLAlchemy models
- Alembic migration
- Pydantic schemas
- seed data

### 対象テーブル

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

### 受け入れ条件

- migration が通る。
- seed user を作成できる。
- RAG 用テーブルを新規 runtime path に含めない。

## Phase 3: Admin PDF upload

### 作業

- admin upload UI
- upload API
- file storage
- document list UI
- document detail UI

### 受け入れ条件

- 管理者が PDF を upload できる。
- `source_documents.status=uploaded` で保存される。

## Phase 4: Document Agent Skill extraction

### 作業

- PDF parser interface
- extraction prompt
- Document Agent Skill JSON schema
- schema validation
- revision save
- entry normalization
- admin preview UI

### 受け入れ条件

- PDF から Document Agent Skill が生成される。
- `document_skill_revisions` と `document_skill_entries` に保存される。
- 管理者画面で skill 内容を確認できる。

## Phase 5: Run start / participant flow

### 作業

- participant login
- run start API
- run state machine
- participant dashboard

### 受け入れ条件

- 被験者が `user_id` でログインできる。
- ready な PDF 教材に紐づく run を開始できる。
- `cycle_count=10` で保存される。

## Phase 6: Initial test generation / submission

### 作業

- initial test generation API
- initial test UI
- answer submission
- scoring
- initial mastery analysis
- Learner Agent Skill initial revision

### 受け入れ条件

- 「初回テストを生成」ボタンから問題が生成される。
- 回答を送信できる。
- スコアと分析結果が保存される。
- Learner Agent Skill revision 1 が作成される。

## Phase 7: Cycle material generation

### 作業

- material generation API
- Prompt Context Builder
- material UI
- read-confirm API
- read duration logging

### 受け入れ条件

- Learner Agent Skill の weak_topics を重点化した教材が生成される。
- 被験者が教材を閲覧できる。
- 読了ボタンで閲覧時間が保存される。

## Phase 8: Cycle test generation / submission

### 作業

- cycle test generation API
- used question fingerprint handling
- cycle test UI
- answer submission
- scoring
- Learner Agent Skill update

### 受け入れ条件

- Cycle 1〜10 のテストを生成できる。
- 過去問題 fingerprint と重複しない。
- 各テスト提出後に Learner Agent Skill revision が増える。

## Phase 9: 10-cycle orchestration

### 作業

- state transition enforcement
- current cycle display
- next action UI
- edge case handling

### 受け入れ条件

- 初回テスト後、Cycle 1〜10 を順番に完走できる。
- 順序外 API は 409 を返す。
- Cycle 10 submit 後、final test generation が可能になる。

## Phase 10: Final test / result page

### 作業

- final test generation
- final test UI
- final scoring
- result summary generation
- improvement dashboard

### 受け入れ条件

- 最終テストを生成・提出できる。
- 初回スコア、最終スコア、gain、gain rate を表示できる。
- サイクルごとの点数推移を表示できる。

## Phase 11: Admin analytics / export

### 作業

- run list
- run detail
- skill history
- score trend
- CSV export

### 受け入れ条件

- 管理者が各被験者の進捗と結果を確認できる。
- CSV を出力できる。

## Phase 12: Tests / Quality

### 作業

- backend unit tests
- API tests
- state transition tests
- schema validation tests
- frontend lint
- backend lint/type check

### 受け入れ条件

- CI 相当のコマンドが README に記載されている。
- 主要 API の happy path がテストされている。

## 優先順位

### P0

- Docker 起動
- DB schema
- PDF upload
- Document Agent Skill extraction
- run start
- initial test
- Learner Agent Skill
- 10 cycle loop
- final test
- result page

### P1

- admin analytics
- CSV export
- detailed generation logs
- retry handling

### P2

- UI polish
- charts
- multiple PDF experiments
- richer item analysis

## 実装上の注意

- RAG を shortcut として追加しない。
- PDF 本文を毎回丸ごと prompt に入れない。
- Document Agent Skill は ingestion 時に確定する。
- Learner Agent Skill は append-only revision とする。
- 問題重複防止のため fingerprint を必ず保存する。
