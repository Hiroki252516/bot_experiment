# Learning Skill Accumulation Chatbot

研究用プロトタイプとして、学習者の回答選択と主観評価をもとにユーザー別 `Skill` を更新し、次回以降の回答生成に反映するローカル実行前提のチュータリングチャットボットです。

## Repo Structure
- `apps/backend`: FastAPI API, SQLAlchemy models, Alembic migrations, RAG, generation/embedding provider abstractions, export logic
- `apps/frontend`: Next.js App Router UI for chat, logs, and admin workflows
- `apps/worker`: PostgreSQL polling worker for ingestion and skill-update jobs
- `packages/shared-schemas`: OpenAPI 由来の共有型を置くための予約領域
- `seeds/sample_corpus`: サンプル教材
- `docs`: 要件、アーキテクチャ、評価プロトコル

## Implemented Scope
- Docker Compose ベースの monorepo 構成
- PostgreSQL + pgvector 前提の初期スキーマ
- 文書 upload と ingest job 作成
- chunking / embedding / retrieval の worker 処理
- 質問送信時の retrieval + 3候補生成
- 候補選択、満足度・わかりやすさ・コメント保存
- chosen / non-chosen を使う `SkillUpdater`
- `skills_enabled` ON/OFF 実験ログ保存
- `turns.csv`、`candidates.csv`、`feedback.csv`、`skill_revisions.csv`、`retrievals.csv` を含む `logs.zip` export
- Chat / Logs / Admin の最低限 UI
- ユーザー名/パスワード登録、ログイン、HttpOnly Cookie セッション

## Tech Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- Frontend: Next.js 15, TypeScript
- Database: PostgreSQL 16, pgvector
- Worker: Python polling worker
- Default generation provider: Gemini Developer API
- Default embedding provider: local `sentence-transformers`
- Test/dev fallback providers: `mock`

## Environment Setup
1. `.env` を用意します。
```bash
cp .env.example .env
```
2. Gemini で回答生成する場合は `.env` の `GEMINI_API_KEY` を設定します。
3. Mac host の Ollama で回答生成する場合は、host 側で Ollama を起動し、`.env` に `GENERATION_PROVIDER=ollama` と `LLM_PROVIDER=ollama` を設定します。
4. API キーなしでローカル挙動だけ確認したい場合は `.env` の `GENERATION_PROVIDER=mock` と `EMBEDDING_PROVIDER=mock` を使ってください。
5. 既定では RAG embedding に `pkshatech/GLuCoSE-base-ja` を使います。初回 ingest または prefetch 時にモデルをダウンロードし、`model_cache` volume に保存します。

主な環境変数:
- `DATABASE_URL`
- `GENERATION_PROVIDER`
- `EMBEDDING_PROVIDER`
- `GEMINI_API_KEY`
- `GEMINI_MODEL_GENERATE`
- `GEMINI_MODEL_EMBED`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL_GENERATE`
- `OLLAMA_REQUEST_TIMEOUT_SECONDS`
- `LOCAL_EMBED_MODEL`
- `LOCAL_EMBED_DEVICE`
- `EMBEDDING_DIMENSIONS`
- `MIN_RETRIEVAL_SCORE`
- `HF_HOME`
- `SENTENCE_TRANSFORMERS_HOME`
- `UPLOAD_DIR`
- `EXPORT_DIR`
- `NEXT_PUBLIC_API_BASE_URL`
- `AUTH_COOKIE_NAME`
- `AUTH_COOKIE_SECURE`
- `AUTH_SESSION_DAYS`

## Run With Docker Compose
通常起動:
```bash
docker compose up --build
```

開発向けオーバーレイ:
```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

研究再現向けオーバーレイ:
```bash
docker compose -f compose.yaml -f compose.research.yaml up --build
```

想定ポート:
- Frontend: `http://localhost:3000`
- Backend / OpenAPI: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- pgAdmin: `http://localhost:5050` (`compose.dev.yaml` 使用時)

## Minimal Workflow
1. Chat UI の利用前に `/register` で新規登録するか `/login` でログインする
2. Admin 画面から教材を upload し、ingest job を作成する
3. worker が chunking と embedding を実行する
4. Chat 画面で質問し、3候補を受け取る
5. 候補を1つ選択して満足度・わかりやすさ・コメントを送る
6. worker が `skill_update_job` を処理し、新 revision を保存する
7. 次回生成時に `skills_enabled=true` なら最新 skill を prompt に反映する

## Key API Endpoints
- `GET /health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `POST /api/users`
- `GET /api/users/{user_id}`
- `GET /api/users/{user_id}/skills`
- `POST /api/documents/upload`
- `POST /api/documents/{document_id}/ingest`
- `GET /api/documents`
- `GET /api/documents/{document_id}/chunks`
- `POST /api/chat/generate`
- `POST /api/chat/select`
- `GET /api/chat/sessions/{session_id}`
- `GET /api/chat/logs/{user_id}`
- `GET /api/chat/turns/{chat_message_id}`
- `POST /api/admin/skills/recompute/{user_id}`
- `GET /api/admin/skills/history/{user_id}`
- `POST /api/experiments/runs`
- `GET /api/experiments/runs`
- `GET /api/experiments/runs/{run_id}`
- `GET /api/experiments/exports/logs.zip`

## Login And Chat Access
Chat 画面と `/api/chat/generate`、`/api/chat/select` はログイン済みユーザーのみ利用できます。認証は `username + password` と HttpOnly Cookie の opaque session token で行います。

```env
AUTH_COOKIE_NAME=tutorbot_session
AUTH_COOKIE_SECURE=false
AUTH_SESSION_DAYS=7
```

研究用ローカル環境では `AUTH_COOKIE_SECURE=false` が既定です。HTTPS 前提の環境で使う場合は `AUTH_COOKIE_SECURE=true` にしてください。`Admin` と `Logs` は研究運用を壊さないため、現時点ではログイン必須にしていません。

既存の匿名 `POST /api/users` は互換用に残していますが、Chat UI からは使いません。過去の匿名ユーザーデータは保持されますが、匿名ユーザーを後からログインアカウントへ紐づける移行 UI はありません。

## Seed Data
サンプル教材:
- [algebra_intro.md](/Users/hiroki/bot_experiment/seeds/sample_corpus/algebra_intro.md)

サンプル user seed:
```bash
docker compose run --rm backend python -m app.scripts.seed_sample_data
```

## Local Embeddings
回答生成と SkillUpdater は `GENERATION_PROVIDER` を使い、RAG の document/query embedding は `EMBEDDING_PROVIDER` を使います。既定は以下です。

```env
GENERATION_PROVIDER=gemini
EMBEDDING_PROVIDER=local-sentence-transformers
LOCAL_EMBED_MODEL=pkshatech/GLuCoSE-base-ja
LOCAL_EMBED_DEVICE=auto
EMBEDDING_DIMENSIONS=768
```

Docker Compose 内では CPU fallback を前提にします。Apple Silicon の MPS を使いたい場合、Linux container から直接 MPS を使う前提にはせず、将来用の `EMBEDDING_PROVIDER=local-http` で macOS host 側の embedding service を呼ぶ設計です。

モデルを事前取得したい場合:
```bash
docker compose run --rm worker python -m app.scripts.prefetch_embedding_model
```

Gemini embedding 由来の既存 vector と local embedding は同じ 768 次元でも混在検索しません。実装上は active `provider_name/model_name/dimensions` で retrieval を絞りますが、検索品質を保つため、provider/model を切り替えた後は対象 document を再 ingest してください。

Chat 画面では検索対象教材を選択できます。初期状態では直近の uploaded かつ completed の教材が選択されます。未選択の場合、通常検索では `source_type=seed` の教材を除外し、uploaded 教材全体を検索します。seed 教材を使いたい場合は明示的に選択してください。

`MIN_RETRIEVAL_SCORE` 未満の検索結果しかない場合、まず日本語キーワードの LIKE fallback を実行します。それでも閾値を超える候補がなければ LLM 生成を行わず、回答候補は「資料中に該当箇所が見つかりません。」になります。

## Ollama Generation
回答生成と SkillUpdater は `GENERATION_PROVIDER=ollama` で Mac host 側の Ollama に切り替えられます。embedding は `EMBEDDING_PROVIDER=local-sentence-transformers` のまま使えます。

```env
GENERATION_PROVIDER=ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL_GENERATE=gemma4:e2b
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
EMBEDDING_PROVIDER=local-sentence-transformers
```

Ollama は Docker container 内ではなく macOS host 側で起動します。backend container からは Docker Desktop の `host.docker.internal:11434` 経由で接続します。

事前確認:
```bash
ollama pull gemma4:e2b
curl http://localhost:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemma4:e2b","messages":[{"role":"user","content":"JSONで {\"ok\": true} だけ返してください"}],"stream":false,"format":{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}}'
docker compose exec backend python -c "import httpx; print(httpx.get('http://host.docker.internal:11434/api/tags').status_code)"
```

`.env` を Ollama 設定にした後、`docker compose up --build` で起動し、PDF ingest 完了後に Chat で質問して3候補が返ることを確認してください。Ollama が未起動、モデル未取得、または JSON schema に合わない応答を返した場合、`/api/chat/generate` は 502 を返します。
初回モデルロードや長い回答で時間がかかる場合は、`OLLAMA_REQUEST_TIMEOUT_SECONDS` を増やしてください。

失敗または途中停止した ingest を再試行したい場合は、対象 document の状態と job 状態を `pending` に戻します。

```sql
UPDATE rag_documents
SET ingest_status = 'pending'
WHERE id = '<document_id>';

UPDATE ingestion_jobs
SET status = 'pending',
    error_message = NULL,
    updated_at = now()
WHERE document_id = '<document_id>'
  AND status IN ('failed', 'running');
```

document 全体を一括で再試行する場合:

```sql
UPDATE rag_documents
SET ingest_status = 'pending'
WHERE ingest_status IN ('failed', 'running');

UPDATE ingestion_jobs
SET status = 'pending',
    error_message = NULL,
    updated_at = now()
WHERE status IN ('failed', 'running');
```

Admin 画面から教材を削除すると、対象の `ingestion_jobs`、`rag_document_chunks`、`embeddings`、該当 chunk に紐づく `retrieval_logs`、`rag_documents`、保存済みファイル本体を hard delete します。実験本番後に削除すると、過去の検索ログや評価データの解釈に影響するため注意してください。研究ログを保持したい段階では、削除前に export を取得するか、将来的な soft delete 化を検討してください。

## Tests And Checks
frontend:
```bash
cd apps/frontend
npm install
npm run lint
npm run build
```

backend tests は Docker コンテナ内の Python 3.12 実行を想定しています:
```bash
docker compose run --rm backend pytest app/tests -q
```

## Notes
- `GeminiGenerationProvider` は Google AI Developer API の `generateContent` を使う実装です。
- `OllamaGenerationProvider` は Mac host 側 Ollama の `/api/chat` を使い、`stream=false` と JSON schema `format` で構造化 JSON 応答を要求します。
- `GeminiEmbeddingProvider` は後方互換・比較用に残していますが、既定の embedding provider ではありません。
- `MockGenerationProvider` と `MockEmbeddingProvider` は API キーなしで縦スライスを確認するための決定的なテスト用実装です。
- skill 更新は `LLM で差分抽出` と `アプリ側の deterministic merge` を分けています。
- export は単一 CSV ではなく、研究評価向けの複数 CSV を zip 化しています。

## Current Verification Status
- `python3 -m compileall apps/backend/app apps/worker/app`: 実行済み
- `docker compose config`: 実行済み
- `cd apps/frontend && npm run lint && npm run build`: 実行済み
- `docker compose up --build` と backend `pytest`: この実行環境では Docker デーモン停止中のため未実行
