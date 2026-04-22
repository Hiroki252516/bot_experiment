# 02 Architecture

## 1. 採用アーキテクチャ
### Monorepo
- `apps/frontend`
- `apps/backend`
- `apps/worker`
- `packages/shared-schemas`
- `infra`

この構成にする理由:
- Codex が全体を横断的に編集しやすい
- Docker Compose で一括起動しやすい
- shared schema を frontend/backend で共有しやすい

## 2. 技術選定
### Backend: FastAPI
理由:
- Python で LLM/RAG 実装と相性が良い
- OpenAPI を自動生成できる
- 型付き API を作りやすい

### DB: PostgreSQL + pgvector
理由:
- 通常のリレーショナルデータとベクトル検索を同居できる
- ログ、実験データ、candidate、skill revision を一元管理できる

### Frontend: Next.js
理由:
- 画面構築が速い
- API ベースの研究用 UI を作りやすい

### Worker
理由:
- skill 更新、embedding 作成、ingest などを API リクエストから分離できる

## 3. Docker Compose 構成
必須サービス:
1. `frontend`
2. `backend`
3. `worker`
4. `db`
5. `adminer` または `pgadmin`（任意だが推奨）

### 期待する compose の要件
- named volume で DB 永続化
- backend, worker は db healthcheck 成功後に起動
- `.env` を読み込む
- 開発時は bind mount を使う
- 本番想定ではなく開発再現性重視

## 4. コンポーネント責務
### frontend
- チャット画面
- 候補回答表示
- 回答選択
- 満足度入力
- チャットログ表示
- 管理画面

### backend
- REST API
- session / conversation 管理
- RAG retrieval
- skill 読み出し
- LLM candidate generation
- 選択結果保存
- CSV export

### worker
- document ingestion
- chunking
- embedding 生成
- vector 保存
- skill updater
- 非同期ジョブ管理

### db
- 学習資料
- chunk
- embeddings
- users
- conversations
- turns
- candidates
- feedback
- skills
- skill revisions
- experiment runs

## 5. LLM Provider abstraction
`LLMProvider` インターフェースを定義し、少なくとも以下メソッドを持たせる。
- `generate_candidates(input) -> CandidateSet`
- `extract_skill_delta(input) -> SkillDelta`
- `embed_texts(texts) -> list[vector]`

初期実装:
- `GeminiProvider`

将来:
- `OpenAIProvider`
- `MockProvider`（テスト用）

## 6. 主要フロー
### A. 質問から候補生成まで
1. user が質問
2. backend が user の active skill を取得
3. backend が vector retrieval 実行
4. backend が prompt を構成
5. provider が 3 件の候補回答を JSON で返す
6. backend が candidate を DB 保存
7. frontend に返却

### B. 選択から skill 更新まで
1. user が 1 件選択
2. 評価値と自由記述を送信
3. backend が selection を保存
4. worker が skill update job を実行
5. chosen vs non-chosen の差分を抽出
6. 正規化した skill rule を新 revision として保存
7. user の active skill revision を更新

## 7. Prompt 設計方針
### candidate generation
LLM には以下を必ず渡す:
- user question
- retrieved contexts
- current skill profile
- experiment flag (skills enabled/disabled)
- strict JSON schema

### skill update
LLM には以下を渡す:
- chosen candidate
- non-chosen candidates
- optional user comment
- previous skill profile
- JSON schema for skill delta

## 8. 障害時方針
- LLM 呼び出し失敗時は 5xx と相関 ID を返す
- embedding 失敗時は job status=failed
- skill update 失敗時は会話自体は成功扱い、skill update のみ再試行可能
