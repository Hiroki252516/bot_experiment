# Agent Skills Adaptive Learning App

PDF 教材を Document Agent Skill に変換し、被験者のテスト結果から Learner Agent Skill を更新しながら、10 サイクルの教材生成・テスト・最終評価を行う研究用 Web アプリです。

新 runtime path では RAG、embedding-based retrieval、pgvector similarity search、runtime chunk retrieval を使いません。既存の chat / RAG / 3候補回答選択関連コードと legacy テーブルは後方互換用に残っていますが、Agent Skills 型実験フローからは参照しません。

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- Frontend: Next.js 15, TypeScript
- DB: PostgreSQL 16 + pgvector
- Worker: Python polling worker（legacy ingestion / skill-update 用）
- Default generation provider: Ollama `gemma4:e2b`
- Test provider: `mock`

## Setup
```bash
cp .env.example .env
```

Ollama を使う場合は macOS host 側で起動します。

```bash
ollama pull gemma4:e2b
```

`.env` の主な設定:

```env
GENERATION_PROVIDER=ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL_GENERATE=gemma4:e2b
OLLAMA_REQUEST_TIMEOUT_SECONDS=120
```

Ollama なしで E2E を確認する場合:

```env
GENERATION_PROVIDER=mock
LLM_PROVIDER=mock
```

## Run
```bash
docker compose up --build
```

開発時:

```bash
docker compose -f compose.yaml -f compose.dev.yaml up --build
```

URLs:
- Frontend: `http://localhost:3000`
- Backend OpenAPI: `http://localhost:8000/docs`
- pgAdmin: `http://localhost:5050`（dev compose）

## Experiment Flow
1. `/register` で被験者ユーザーを作成する。
2. `/admin` で PDF / md / txt 教材を upload する。
3. `/admin` で `Document Skill 抽出` を実行し、教材を `ready` にする。
4. `/` で ready な教材を選び、10 サイクル run を開始する。
5. 初回テストを生成・回答・提出する。
6. Cycle 1〜10 で教材生成、読了記録、Cycle テスト生成、回答・提出を順に行う。
7. Cycle 10 提出後、最終テストを生成・回答・提出する。
8. 結果画面で initial / final score、gain、cycle trend、AI 総評を確認する。
9. `/admin` で run_id を指定して CSV export を作成する。

順序外 API 呼び出しは `409 Conflict` を返します。

## New Adaptive APIs
- `POST /api/admin/documents/upload`
- `GET /api/admin/documents`
- `POST /api/admin/documents/{document_id}/extract-skill`
- `POST /api/runs/start`
- `GET /api/runs/{run_id}/state`
- `POST /api/runs/{run_id}/initial-test/generate`
- `GET /api/runs/{run_id}/initial-test`
- `POST /api/runs/{run_id}/initial-test/submit`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/generate`
- `GET /api/runs/{run_id}/cycles/{cycle_index}/material`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/generate`
- `GET /api/runs/{run_id}/cycles/{cycle_index}/test`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/submit`
- `POST /api/runs/{run_id}/final-test/generate`
- `GET /api/runs/{run_id}/final-test`
- `POST /api/runs/{run_id}/final-test/submit`
- `GET /api/runs/{run_id}/results`
- `POST /api/admin/exports/runs/{run_id}`
- `GET /api/admin/exports/{export_job_id}`

## DB Schema
New adaptive runtime tables:
- `source_documents`
- `adaptive_document_skill_revisions`
- `adaptive_document_skill_entries`
- `experiment_runs`
- `generated_assessments`
- `assessment_items`
- `assessment_attempts`
- `generated_materials`
- `material_reads`
- `learner_skill_revisions`
- `generation_logs`
- `result_summaries`
- `export_jobs`

`rag_documents`、`rag_document_chunks`、`embeddings`、`retrieval_logs`、chat 系テーブルは legacy です。新 adaptive API からは呼びません。

## CSV Export
`POST /api/admin/exports/runs/{run_id}` は zip を作成し、以下の CSV を含めます。

- `runs.csv`
- `source_documents.csv`
- `document_skill_revisions.csv`
- `document_skill_entries.csv`
- `generated_assessments.csv`
- `assessment_items.csv`
- `assessment_attempts.csv`
- `generated_materials.csv`
- `material_reads.csv`
- `learner_skill_revisions.csv`
- `generation_logs.csv`
- `result_summaries.csv`

## Tests
Backend:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend python -m pytest app/tests -q
```

Frontend:

```bash
cd apps/frontend
npm install
npm run lint
npm run build
```

Migration:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm backend alembic upgrade head
```

## Legacy Notes
旧 chat UI、3候補回答、answer selection、legacy RAG ingestion/retrieval、pgvector similarity search は残っています。新仕様の被験者 flow / admin flow / generation path では、教材参照は Document Agent Skill、学習者状態は Learner Agent Skill のみを使います。
