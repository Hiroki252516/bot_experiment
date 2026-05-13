# 03 API and DB

## 1. 概要

本書は、PDF教材アップロード、Agent Skill extraction、初回テスト、10 回の教材生成・サイクルテスト、最終テスト、成績向上表示を実装するための API / DB / JSON schema を定義する。

RAG は使わない。`document_skill_revisions` / `document_skill_entries` / `learner_skill_revisions` を正式な参照経路とする。

## 2. API 一覧

### Health

- `GET /api/health`

### Admin Documents

- `POST /api/admin/documents/upload`
- `GET /api/admin/documents`
- `GET /api/admin/documents/{document_id}`
- `POST /api/admin/documents/{document_id}/extract-skill`
- `GET /api/admin/documents/{document_id}/skill-revisions`
- `GET /api/admin/document-skill-revisions/{revision_id}`

### Runs

- `POST /api/runs/start`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/state`
- `POST /api/runs/{run_id}/finish`

### Initial Test

- `POST /api/runs/{run_id}/initial-test/generate`
- `GET /api/runs/{run_id}/initial-test`
- `POST /api/runs/{run_id}/initial-test/submit`

### Cycle Materials

- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/generate`
- `GET /api/runs/{run_id}/cycles/{cycle_index}/material`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm`

### Cycle Tests

- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/generate`
- `GET /api/runs/{run_id}/cycles/{cycle_index}/test`
- `POST /api/runs/{run_id}/cycles/{cycle_index}/test/submit`

### Final Test

- `POST /api/runs/{run_id}/final-test/generate`
- `GET /api/runs/{run_id}/final-test`
- `POST /api/runs/{run_id}/final-test/submit`

### Results

- `GET /api/runs/{run_id}/results`

### Admin Exports

- `POST /api/admin/exports/runs/{run_id}`
- `GET /api/admin/exports/{export_job_id}`

## 3. API 詳細

### `POST /api/admin/documents/upload`

PDF 教材をアップロードする。

Request: multipart/form-data

- `file`: PDF
- `title`: string
- `description`: string | null

Response:

```json
{
  "document_id": "uuid",
  "status": "uploaded",
  "title": "仮定法教材",
  "created_at": "2026-05-09T00:00:00Z"
}
```

### `POST /api/admin/documents/{document_id}/extract-skill`

PDF から Document Agent Skill を生成する。

Response:

```json
{
  "document_id": "uuid",
  "document_skill_revision_id": "uuid",
  "status": "ready",
  "entry_count": 42
}
```

### `POST /api/runs/start`

被験者の実験 run を開始する。

Request:

```json
{
  "user_id": "participant-001",
  "document_id": "uuid",
  "cycle_count": 10
}
```

Response:

```json
{
  "run_id": "uuid",
  "state": "RUN_STARTED",
  "cycle_count": 10
}
```

### `POST /api/runs/{run_id}/initial-test/generate`

初回テストを生成する。

Response:

```json
{
  "assessment_id": "uuid",
  "assessment_type": "initial",
  "question_count": 20,
  "state": "INITIAL_TEST_GENERATED"
}
```

### `POST /api/runs/{run_id}/initial-test/submit`

初回テストを提出し、採点・理解度推定・Learner Agent Skill 作成を行う。

Request:

```json
{
  "answers": [
    {"question_id": "q1", "answer": "B"}
  ]
}
```

Response:

```json
{
  "attempt_id": "uuid",
  "score": 12,
  "max_score": 20,
  "learner_skill_revision_id": "uuid",
  "state": "INITIAL_TEST_SUBMITTED"
}
```

### `POST /api/runs/{run_id}/cycles/{cycle_index}/material/generate`

弱点補強用教材を生成する。

- `cycle_index`: 1〜10
- 入力 context: Document Agent Skill + Learner Agent Skill

Response:

```json
{
  "material_id": "uuid",
  "cycle_index": 1,
  "title": "仮定法過去の基礎整理",
  "state": "CYCLE_MATERIAL_GENERATED"
}
```

### `POST /api/runs/{run_id}/cycles/{cycle_index}/material/read-confirm`

被験者が教材読了を通知する。

Response:

```json
{
  "material_read_id": "uuid",
  "read_duration_seconds": 540,
  "state": "CYCLE_MATERIAL_READ"
}
```

### `POST /api/runs/{run_id}/cycles/{cycle_index}/test/generate`

サイクルテストを生成する。過去問題 fingerprint を input に含め、同一問題を避ける。

Response:

```json
{
  "assessment_id": "uuid",
  "assessment_type": "cycle",
  "cycle_index": 1,
  "question_count": 10,
  "state": "CYCLE_TEST_GENERATED"
}
```

### `POST /api/runs/{run_id}/cycles/{cycle_index}/test/submit`

サイクルテストを提出し、採点・理解度推定・Learner Agent Skill 更新を行う。

Response:

```json
{
  "attempt_id": "uuid",
  "score": 7,
  "max_score": 10,
  "learner_skill_revision_id": "uuid",
  "next_cycle_index": 2
}
```

### `POST /api/runs/{run_id}/final-test/generate`

Cycle 10 完了後に最終テストを生成する。

Response:

```json
{
  "assessment_id": "uuid",
  "assessment_type": "final",
  "question_count": 20,
  "state": "FINAL_TEST_GENERATED"
}
```

### `POST /api/runs/{run_id}/final-test/submit`

最終テストを提出し、結果を確定する。

Response:

```json
{
  "attempt_id": "uuid",
  "initial_score": 12,
  "final_score": 17,
  "gain_score": 5,
  "gain_rate": 0.25,
  "state": "RESULT_READY"
}
```

## 4. DB Tables

### users

- id
- user_id
- created_at

### source_documents

- id
- title
- description
- file_path
- mime_type
- status: uploaded | processing | ready | failed
- created_at
- updated_at

### document_skill_revisions

- id
- document_id
- revision
- skill_json
- extraction_prompt_version
- provider
- model
- schema_version
- created_at

### document_skill_entries

- id
- document_skill_revision_id
- entry_type
- topic_key
- title
- content_json
- difficulty
- order_index
- created_at

### experiment_runs

- id
- user_id
- document_id
- document_skill_revision_id
- state
- cycle_count default 10
- current_cycle_index
- started_at
- finished_at
- created_at

### generated_assessments

- id
- run_id
- assessment_type: initial | cycle | final
- cycle_index nullable
- title
- questions_json
- blueprint_json
- question_fingerprints_json
- provider
- model
- prompt_version
- temperature
- created_at

### assessment_attempts

- id
- assessment_id
- run_id
- started_at
- submitted_at
- duration_seconds
- answers_json
- score
- max_score
- per_question_correct_json
- analysis_json
- created_at

### generated_materials

- id
- run_id
- cycle_index
- learner_skill_revision_id
- title
- content_markdown
- focus_topics_json
- provider
- model
- prompt_version
- temperature
- created_at

### material_reads

- id
- material_id
- run_id
- cycle_index
- presented_at
- read_confirmed_at
- read_duration_seconds

### learner_skill_revisions

- id
- run_id
- user_id
- revision
- source_attempt_id
- skill_json
- update_reason
- provider
- model
- prompt_version
- created_at

### generation_logs

- id
- run_id nullable
- generation_type
- input_summary_json
- output_json
- validation_status
- error_message nullable
- provider
- model
- prompt_version
- temperature
- created_at

### export_jobs

- id
- run_id nullable
- status
- file_path
- created_at
- completed_at

## 5. JSON Schema 概要

### Document Agent Skill

```json
{
  "learning_objectives": [],
  "topic_map": [],
  "concept_definitions": [],
  "prerequisite_concepts": [],
  "examples": [],
  "common_misconceptions": [],
  "difficulty_map": [],
  "assessment_blueprint": [],
  "canonical_explanations": [],
  "out_of_scope": []
}
```

### Learner Agent Skill

```json
{
  "overall_mastery": 0.0,
  "mastery_by_topic": {},
  "known_topics": [],
  "weak_topics": [],
  "common_mistakes": [],
  "misconception_hypotheses": [],
  "recommended_next_focus": [],
  "recommended_difficulty": "basic",
  "used_question_fingerprints": [],
  "evidence_from_attempts": []
}
```

### Assessment

```json
{
  "title": "string",
  "questions": [
    {
      "question_id": "string",
      "topic_key": "string",
      "difficulty": "basic|standard|advanced",
      "stem": "string",
      "choices": ["string"],
      "correct_answer": "string",
      "explanation": "string",
      "fingerprint": "string"
    }
  ]
}
```

## 6. 状態制約

- initial-test generate は RUN_STARTED のみ許可。
- initial-test submit は INITIAL_TEST_GENERATED のみ許可。
- cycle material generate は initial submitted または前 cycle submitted 後のみ許可。
- cycle test generate は material read-confirm 後のみ許可。
- final-test generate は cycle 10 submitted 後のみ許可。
- final-test submit 後は result ready となる。

## 7. CSV Export

最低限、以下を出力する。

- runs.csv
- document_skills.csv
- learner_skill_revisions.csv
- assessments.csv
- attempts.csv
- materials.csv
- material_reads.csv
- score_trend.csv
- generation_logs.csv
