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
- run start page（A/B/C の条件表示）
- study flow pages（Pre → Material → Mini → Post）
- log page（run 一覧 / 詳細）
- admin page（skills history / recompute）
- API client
- basic styling only

受け入れ条件:
- 画面遷移できる
- mock API でも表示できる

## 4. Phase 4 — Study flow（Pre → Cycle1..3 → Post）
本研究の正本仕様は `docs/07_adaptive_learning_design.md` を参照。

実装:
- run 管理（A/B/C, skills_enabled, cycle_count=3）
- Pre-test（MCQ）: start/submit, 自動採点, 所要時間ログ
- Material: next/present, 読了 confirm, 所要時間ログ
- Chat（教材閲覧中のみ）: ask, ログ保存（A/Bのみ）
- Mini-test（MCQ）: start/submit, 自動採点, 所要時間ログ（Cycle 1..3）
- Mastery estimate: 推定保存（Cycle 1..3）
- Post-test（MCQ）: start/submit, 自動採点, 所要時間ログ
- export（CSV/JSONL）: run/material/read/assessment/attempt/mastery/chat/skills を出力

受け入れ条件:
- Pre → Cycle1..3 → Post を 1 user で完走できる
- 教材閲覧時間・テスト所要時間が必ず保存される（時間制限は設けない）
- チャットは教材閲覧中のみ実行できる（それ以外は拒否）

## 5. Phase 5 — Generation provider（教材/テスト/回答/推定）
実装:
- `GenerationProvider` 抽象（教材生成・ミニテスト生成・教材中Q&A・理解度推定・skill delta 抽出）
- Gemini provider 実装（structured output）
- prompt_version / model_name / temperature 等メタデータ保存

受け入れ条件:
- A/B で同一入力に対して、差分が Skills の有無だけになる（B は skill_profile を入力に含めない）
- 教材・テスト・回答・推定が JSON schema 通りに生成できる

## 6. Phase 6 — Skills（Aのみ）/ ON-OFF 差分担保
実装:
- skill_profile（テキスト/JSON）の保存・履歴（skill_revisions）
- worker job: skill update（Aのみ）
- B/C: skill 参照・更新・反映を無効化（ログは保存）

受け入れ条件:
- A で revision が増え、次サイクルの生成に反映される
- B で skill_revision が増えない（または更新処理が走らない）

## 7. Phase 7 — Group C（固定教材・同一フロー）
実装:
- C 用の固定教材リポジトリ（テキスト）
- Material/Assessment の API は同一だが、C は `source_type=fixed` を返す
- チャット UI/ API を C では無効化

受け入れ条件:
- C でも Pre → Cycle1..3 → Post を完走できる
- ログは A/B と同一粒度で保存される（比較可能）

## 9. テスト方針
### backend
- settings test
- run start/finish test
- pre/mini/post start/submit test（時間ログ含む）
- materials next/read_confirm test（時間ログ含む）
- chat ask state guard test（教材閲覧中のみ）
- mastery estimate persistence test
- skill merge logic test

### frontend
- component render test
- API integration smoke test

### e2e
- run start
- pre-test submit
- cycle1..3: material → read_confirm → mini-test submit → mastery estimate
- post-test submit
- export contains durations
- (A) skill updated and reflected

## 10. 実装優先度
### P0
- Docker
- DB
- run/start-finish + study flow endpoints
- time logging (material/read + assessment attempts)
- generation provider (material/quiz/answer/estimate)

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
