# AGENTS.md

## 1. このファイルの目的

このファイルは、本リポジトリで作業する Codex / AI コーディングエージェント向けの実装指示書である。

実装エージェントは、必ず `docs/` 配下の仕様、とくに `docs/07_adaptive_learning_design.md` を正本として扱うこと。本ファイルは、その `docs/` の内容を実装時に迷わないよう要約し、禁止事項・実装順序・完了条件を明確化するためのものである。

---

## 2. プロジェクトの目的

本リポジトリは、PDF 教材をもとに被験者の学習効果を測定する研究用 Web アプリを実装する。

実験の基本フローは以下である。

1. 管理者が、実験前に学習対象を解説した PDF 教材をアップロードする。
2. システムは、アップロードされた PDF を解析し、Document Agent Skill として構造化・保存する。
3. 被験者が Web アプリにログインする。
4. 被験者が「初回テストを生成」ボタンを押す。
5. システムは、PDF 教材の範囲に基づき、被験者の初期習熟度を測る初回テストを生成する。
6. 被験者が初回テストを解き、送信する。
7. システムは初回テストを採点し、AI が被験者の理解済み領域・未理解領域・誤概念を推定する。
8. システムは、その推定結果を Learner Agent Skill として保存する。
9. システムは、被験者の理解が甘い部分を重点的に補う教科書・参考書のような学習教材を生成する。
10. 被験者は生成教材を読む。
11. 被験者が読み終えたら「テスト開始」ボタンを押す。
12. システムは、同じ学習範囲内でサイクルテストを生成する。
13. サイクルテストは、初回テストや過去のサイクルテストと完全に同一にならないようにする。
14. 被験者がサイクルテストを解き、送信する。
15. システムはテスト結果を分析し、Learner Agent Skill を更新する。
16. システムは、更新された Learner Agent Skill に基づき、次の弱点補強教材を生成する。
17. 9〜16 のループを合計 10 回行う。
18. 10 回目のサイクル完了後、システムは最終テストを生成する。
19. 被験者が最終テストを解き、送信する。
20. システムは、初回テストと最終テストを比較し、成績がどれくらい向上したかを分かりやすく表示する。
21. 管理者または実験者は、結果画面や CSV export から実験結果を確認する。

---

## 3. 最重要方針

このプロジェクトでは、RAG を使わない。

教材参照、学習者状態参照、テスト履歴参照、生成時の文脈構築は、すべて Agent Skills によって行う。

ここでいう Agent Skill は、本アプリケーション内で DB に保存される versioned JSON knowledge / state object である。

OpenAI API の hosted Skills を直接使うことは必須ではない。実装上は、PDF 教材由来の Document Agent Skill と、被験者の学習履歴由来の Learner Agent Skill を DB に revision として保存し、LLM 呼び出し時に deterministic に prompt context へ変換する。

---

## 4. 絶対に実装してはいけないこと

新しい実験 runtime path では、以下を実装してはいけない。

- RAG
- embedding-based retrieval
- pgvector similarity search
- runtime chunk retrieval
- retrieval pipeline
- retrieval logs を生成根拠として使う設計
- PDF を chunk 化してベクトル検索する設計
- local sentence-transformers を必須 component とする設計
- `rag_document_chunks` を正式な教材参照経路にする設計
- `embeddings` を正式な教材参照経路にする設計
- `retrieval_logs` を正式な評価・生成経路にする設計

互換性や既存コード整理のために legacy table や legacy module が残ることは許容する。ただし、新仕様の実験フローでは使ってはいけない。

---

## 5. 技術スタック

原則として、以下の構成を使う。

- Monorepo
- Docker / Docker Compose
- Backend: Python 3.12 + FastAPI
- Frontend: Next.js + TypeScript
- Database: PostgreSQL 16
- Worker: Python worker service
- ORM: SQLAlchemy 2.x
- Migration: Alembic
- API schema: Pydantic
- LLM provider: provider abstraction を必ず挟む
- Default LLM provider: Ollama (`gemma4:e2b`)
- Configuration: `.env`
- Tests: pytest / frontend test tools

`docker compose up --build` で、backend / frontend / worker / database が起動すること。

---

## 6. Repository 構成

推奨構成は以下である。

```text
.
├── apps/
│   ├── backend/
│   ├── frontend/
│   └── worker/
├── packages/
│   └── shared-schemas/
├── docs/
├── AGENTS.md
├── docker-compose.yml
└── README.md
```

実装時は、この構成を大きく崩さないこと。

---

## 7. 正本仕様

仕様判断で迷った場合は、以下の優先順位で判断する。

1. `docs/07_adaptive_learning_design.md`
2. `docs/03_api_db.md`
3. `docs/02_architecture.md`
4. `docs/04_implementation_plan.md`
5. `docs/00_codex_task.md`
6. `docs/01_prd.md`
7. `docs/05_evaluation_protocol.md`
8. `docs/06_references.md`
9. 本 `AGENTS.md`

`AGENTS.md` と `docs/` が矛盾する場合は、`docs/07_adaptive_learning_design.md` を優先すること。

---

## 8. Agent Skill 設計

### 8.1 Document Agent Skill

Document Agent Skill は、管理者がアップロードした PDF 教材から抽出される、教材側の構造化知識である。

含めるべき情報の例:

- document_id
- skill_version
- title
- source_pdf_metadata
- learning_scope
- topics
- subtopics
- concept_definitions
- prerequisite_knowledge
- examples
- common_misconceptions
- assessment_blueprint
- difficulty_distribution
- terminology
- generated_at
- prompt_version
- model_name

Document Agent Skill は、PDF アップロード時または明示的な skill extraction 実行時に生成する。

runtime で PDF 全文を検索して必要箇所を探すのではなく、事前に構造化された Document Agent Skill を生成文脈として使う。

### 8.2 Learner Agent Skill

Learner Agent Skill は、被験者ごとの理解状態を表す構造化 state である。

含めるべき情報の例:

- user_id
- run_id
- skill_version
- current_cycle_index
- overall_mastery
- known_topics
- weak_topics
- misconceptions
- topic_mastery
- evidence_from_assessments
- recommended_focus
- recommended_difficulty
- used_question_fingerprints
- learning_history_summary
- updated_at
- prompt_version
- model_name

Learner Agent Skill は、初回テスト提出後に作成し、各サイクルテスト提出後に revision として更新する。

更新は破壊的 overwrite ではなく、append-only revision を基本とする。

---

## 9. LLM context 構築ルール

LLM 呼び出し時は、以下を deterministic に context 化する。

- Document Agent Skill
- 最新の Learner Agent Skill
- run state
- 現在の cycle index
- 過去の assessment summary
- used_question_fingerprints
- 生成対象の種類
  - initial_test
  - weak_topic_material
  - cycle_test
  - final_test
  - mastery_analysis
  - result_summary

LLM に不要な全履歴を丸ごと渡してはいけない。必要な情報を schema に従って要約・構造化して渡すこと。

---

## 10. テスト生成ルール

### 10.1 初回テスト

初回テストは、PDF 教材が扱う学習範囲全体の初期習熟度を測るために生成する。

要件:

- Document Agent Skill の learning_scope 全体を対象にする。
- 特定の弱点に偏らせすぎない。
- トピックごとの理解度を推定できる構成にする。
- 採点可能な形式にする。
- 問題ごとに topic / subtopic / difficulty / correct_answer / rubric を保存する。

### 10.2 サイクルテスト

サイクルテストは、直前までの Learner Agent Skill に基づいて生成する。

要件:

- 弱点領域を重点的に扱う。
- ただし学習範囲全体との関係も保つ。
- 過去問題と完全一致させない。
- `used_question_fingerprints` を参照する。
- 初回テストや過去サイクルテストの単純な言い換えだけにしない。
- 採点可能な形式にする。

### 10.3 最終テスト

最終テストは、初回テストと同じ学習範囲を測る。

要件:

- 初回テストと同じ構成比・難易度分布に近づける。
- ただし同一問題の丸写しは避ける。
- 初回テストとの比較が可能な topic mapping を保存する。
- gain score / gain rate / topic improvement を算出できるようにする。

---

## 11. 教材生成ルール

弱点補強教材は、教科書・参考書のように読める形式で生成する。

要件:

- 被験者の weak_topics を重点的に扱う。
- 既に理解済みの topic は必要最小限にする。
- 誤概念を明示的に修正する。
- 例・反例・練習観点を含める。
- PDF 教材の範囲外に大きく逸脱しない。
- 生成教材の対象 topic / subtopic / difficulty を保存する。
- 被験者の読了確認と読了時間を保存する。

---

## 12. 実験状態管理

run は以下の状態を持つ。

- created
- initial_test_generated
- initial_test_submitted
- initial_analysis_completed
- cycle_material_generated
- cycle_material_read
- cycle_test_generated
- cycle_test_submitted
- cycle_analysis_completed
- final_test_generated
- final_test_submitted
- completed

10 サイクルを完了するまで final test に進めてはいけない。

Pre / cycle / final の各 assessment 中は、状態遷移を明確にし、二重送信や順序違反を防ぐこと。

---

## 13. API 実装方針

必要な API 群は以下である。

### Health

- `GET /api/health`

### Admin Documents

- `POST /api/admin/documents/upload`
- `GET /api/admin/documents`
- `GET /api/admin/documents/{document_id}`
- `POST /api/admin/documents/{document_id}/extract-skill`

### Runs

- `POST /api/runs/start`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/finish`

### Initial Test

- `POST /api/runs/{run_id}/initial-test/generate`
- `POST /api/runs/{run_id}/initial-test/submit`

### Materials

- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/generate`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm`

### Cycle Tests

- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/generate`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/submit`

### Final Test

- `POST /api/runs/{run_id}/final-test/generate`
- `POST /api/runs/{run_id}/final-test/submit`

### Results

- `GET /api/runs/{run_id}/results`
- `GET /api/admin/runs`
- `GET /api/admin/runs/{run_id}`
- `GET /api/admin/runs/{run_id}/export.csv`

---

## 14. DB 実装方針

最低限、以下の概念を保存できること。

- users
- documents
- document_skill_revisions
- document_skill_entries
- runs
- generated_materials
- material_reads
- assessments
- assessment_items
- assessment_attempts
- learner_skill_revisions
- generation_logs
- result_summaries

すべての LLM 生成について、以下を保存すること。

- provider
- model_name
- prompt_version
- temperature
- input_schema_version
- output_schema_version
- generated_at
- raw_output または validated_output
- validation_status

---

## 15. Frontend 実装方針

### 管理者画面

必要な機能:

- PDF 教材アップロード
- PDF 一覧
- Document Agent Skill 抽出
- Document Agent Skill revision 確認
- run 一覧
- run 詳細
- 被験者の進捗確認
- 結果確認
- CSV export

### 被験者画面

必要な機能:

- ログインまたは user_id 入力
- 実験開始
- 初回テスト生成
- 初回テスト回答・送信
- 生成教材の閲覧
- 読了確認
- サイクルテスト開始
- サイクルテスト回答・送信
- 10 サイクルの進捗表示
- 最終テスト回答・送信
- 成績向上結果の表示

---

## 16. 結果表示要件

最終結果画面では、最低限以下を表示する。

- initial_score
- final_score
- gain_score
- gain_rate
- cycle_score_trend
- topic_mastery_before_after
- improved_topics
- remaining_weak_topics
- misconception_reduction
- material_read_duration_summary
- test_duration_summary

人間の実験者が、初回テストから最終テストまでにどれくらい成績が向上したかを一目で確認できる UI にすること。

---

## 17. CSV export 要件

管理者は、少なくとも以下を export できること。

- runs.csv
- assessments.csv
- assessment_items.csv
- assessment_attempts.csv
- generated_materials.csv
- material_reads.csv
- learner_skill_revisions.csv
- document_skill_revisions.csv
- generation_logs.csv
- result_summaries.csv

研究分析に必要な raw data と summary data の両方を出力すること。

---

## 18. 実装順序

実装は以下の順序を推奨する。

1. Monorepo skeleton を作る。
2. Docker / Docker Compose を整備する。
3. Backend の health check / settings / DB connection / migration を作る。
4. Frontend の基本ページを作る。
5. Admin PDF upload を実装する。
6. PDF parsing を実装する。
7. Document Agent Skill extraction を実装する。
8. Participant login / run start を実装する。
9. Initial test generation を実装する。
10. Initial test submission / grading を実装する。
11. Learner Agent Skill initial revision を実装する。
12. Weak-topic material generation を実装する。
13. Material read confirmation を実装する。
14. Cycle test generation を実装する。
15. Cycle test submission / grading を実装する。
16. Learner Agent Skill update を実装する。
17. 10-cycle state machine を実装する。
18. Final test generation / submission / grading を実装する。
19. Result dashboard を実装する。
20. Admin dashboard / CSV export を実装する。
21. Tests / seed data / README を整備する。

---

## 19. Coding rules

- 小さく、読みやすく、テストしやすい関数を書く。
- API 入出力は Pydantic schema で定義する。
- DB schema 変更は Alembic migration で管理する。
- LLM 出力は structured JSON を基本とする。
- LLM 出力は必ず schema validation する。
- generation provider abstraction を必ず使う。
- provider 固有コードを business logic に直接混ぜない。
- secret / API key を commit しない。
- `.env.example` を用意する。
- エラー時は原因を追える log を残す。
- 状態遷移は明示的に実装する。
- 研究ログは欠損しにくい設計にする。
- prompt_version を保存する。
- magic number を避ける。
- ただし cycle_count は仕様上 10 を正本とする。

---

## 20. Testing rules

最低限、以下をテストする。

- PDF upload
- Document Agent Skill extraction
- run start
- initial test generation
- initial test submission
- learner skill creation
- material generation
- material read confirmation
- cycle test generation
- cycle test submission
- learner skill update
- 10-cycle progression
- final test generation
- final test submission
- result summary calculation
- CSV export
- invalid state transition rejection
- duplicate question avoidance

---

## 21. Definition of Done

実装完了条件は以下である。

- `docker compose up --build` で全サービスが起動する。
- 管理者が PDF 教材をアップロードできる。
- PDF から Document Agent Skill を抽出・保存できる。
- 被験者が run を開始できる。
- 被験者が初回テストを生成・回答・送信できる。
- システムが初回テストを採点できる。
- システムが Learner Agent Skill を作成できる。
- システムが弱点補強教材を生成できる。
- 被験者が教材を閲覧し、読了確認できる。
- システムがサイクルテストを生成できる。
- サイクルテストが過去問題と完全重複しない。
- 被験者がサイクルテストを回答・送信できる。
- システムが各サイクル後に Learner Agent Skill を更新できる。
- 1 人の被験者が 10 サイクルを end-to-end で完走できる。
- システムが最終テストを生成・採点できる。
- 結果画面で初回点、最終点、gain、topic improvement、remaining weak topics を確認できる。
- 管理者が run / assessment / material / Agent Skill revision / generation log を確認できる。
- 管理者が CSV export できる。
- critical backend tests が通る。
- 新 runtime path で RAG / embedding / pgvector retrieval を使っていない。



---

## 23. 最終確認チェックリスト

実装エージェントは作業完了前に以下を確認する。

- `docs/07_adaptive_learning_design.md` と矛盾していない。
- 10 サイクル固定の実験フローになっている。
- PDF upload から final result display までつながっている。
- Document Agent Skill を使っている。
- Learner Agent Skill を使っている。
- RAG を使っていない。
- embedding retrieval を使っていない。
- pgvector similarity search を使っていない。
- 過去問題との重複回避がある。
- 初回テストと最終テストの比較ができる。
- 管理者が実験結果を確認できる。
- CSV export がある。
- Docker で起動できる。
- tests が通る。
