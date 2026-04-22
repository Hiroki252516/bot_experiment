# 04 Implementation Plan

## 1. Phase 1 — Repo skeleton
受け入れ条件:
- monorepo ができている
- frontend/backend/worker が分かれている
- Dockerfiles がある
- docker compose で空コンテナ起動できる

## 2. Phase 2 — Backend foundation
実装:
- FastAPI app
- settings
- DB connection
- Alembic
- health endpoint
- SQLAlchemy models

受け入れ条件:
- `/health` が通る
- migration が適用できる

## 3. Phase 3 — Frontend foundation
実装:
- chat page
- log page
- admin page
- API client
- basic styling only

受け入れ条件:
- 画面遷移できる
- mock API でも表示できる

## 4. Phase 4 — Document ingestion / RAG
実装:
- upload endpoint
- parser
- chunker
- embeddings
- pgvector 保存
- retrieval service

受け入れ条件:
- サンプル文書を ingest できる
- top-k を返せる

## 5. Phase 5 — Candidate generation
実装:
- LLM provider abstraction
- Gemini provider
- structured output schema
- candidate persistence

受け入れ条件:
- 3 候補が返る
- retrieval と skill が prompt に反映される
- 生成ログが保存される

## 6. Phase 6 — Selection / Feedback
実装:
- select API
- feedback save
- selected flag update
- log page reflect

受け入れ条件:
- 選択と評価が DB に保存される
- ログ画面で確認できる

## 7. Phase 7 — SkillUpdater
実装:
- worker job
- chosen / rejected 比較
- next skill revision save
- active revision swap

受け入れ条件:
- revision が増える
- 次回生成で新 skill が使われる

## 8. Phase 8 — Experiment mode
実装:
- skills_enabled flag
- UI toggle
- experiment_runs logging
- CSV export

受け入れ条件:
- 同一条件比較が可能
- export できる

## 9. テスト方針
### backend
- settings test
- generate endpoint test
- select endpoint test
- skill merge logic test
- retrieval repository test

### frontend
- component render test
- API integration smoke test

### e2e
- document ingest
- ask question
- select candidate
- skill updated

## 10. 実装優先度
### P0
- Docker
- DB
- generate
- select
- skill update

### P1
- logs
- export
- admin page

### P2
- UI polishing
- richer analytics

## 11. Codex への注意
- まず P0 を終わらせる
- 実装途中で凝った最適化を入れない
- 動く縦スライスを優先
- 失敗したら mock provider で先に通す
