# Learning Skill Accumulation Chatbot

研究用プロトタイプとして、学習者の回答選択と主観評価をもとにユーザー別 `Skill` を更新し、次回以降の回答生成に反映するローカル実行前提のチュータリングチャットボットです。

## Repo Structure
- `apps/backend`: FastAPI API, SQLAlchemy models, Alembic migrations, RAG, LLM abstraction, export logic
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

## Tech Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- Frontend: Next.js 15, TypeScript
- Database: PostgreSQL 16, pgvector
- Worker: Python polling worker
- Default LLM provider: Gemini Developer API
- Test/dev fallback provider: `mock`

## Environment Setup
1. `.env` を用意します。
```bash
cp .env.example .env
```
2. Gemini を使う場合は `.env` の `GEMINI_API_KEY` を設定します。
3. API キーなしでローカル挙動だけ確認したい場合は `.env` の `LLM_PROVIDER=mock` を使ってください。

主な環境変数:
- `DATABASE_URL`
- `LLM_PROVIDER`
- `GEMINI_API_KEY`
- `GEMINI_MODEL_GENERATE`
- `GEMINI_MODEL_EMBED`
- `UPLOAD_DIR`
- `EXPORT_DIR`
- `NEXT_PUBLIC_API_BASE_URL`

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
1. `POST /api/users` で user を作成するか、Chat UI から自動発行する
2. Admin 画面から教材を upload し、ingest job を作成する
3. worker が chunking と embedding を実行する
4. Chat 画面で質問し、3候補を受け取る
5. 候補を1つ選択して満足度・わかりやすさ・コメントを送る
6. worker が `skill_update_job` を処理し、新 revision を保存する
7. 次回生成時に `skills_enabled=true` なら最新 skill を prompt に反映する

## Key API Endpoints
- `GET /health`
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

## Seed Data
サンプル教材:
- [algebra_intro.md](/Users/hiroki/bot_experiment/seeds/sample_corpus/algebra_intro.md)

サンプル user seed:
```bash
docker compose run --rm backend python -m app.scripts.seed_sample_data
```

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
- `GeminiProvider` は Google AI Developer API の `generateContent` / `embedContent` を使う実装です。
- `MockProvider` は API キーなしで縦スライスを確認するための決定的なテスト用実装です。
- skill 更新は `LLM で差分抽出` と `アプリ側の deterministic merge` を分けています。
- export は単一 CSV ではなく、研究評価向けの複数 CSV を zip 化しています。

## Current Verification Status
- `python3 -m compileall apps/backend/app apps/worker/app`: 実行済み
- `docker compose config`: 実行済み
- `cd apps/frontend && npm run lint && npm run build`: 実行済み
- `docker compose up --build` と backend `pytest`: この実行環境では Docker デーモン停止中のため未実行
