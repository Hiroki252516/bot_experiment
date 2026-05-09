# 03 API / DB / JSON Schema（研究フロー：Pre → Cycle1..3 → Post）

本書は研究フローに必要な API/DB/JSON schema を定義する。研究仕様の正本は `docs/07_adaptive_learning_design.md`。

## 1. 推奨ディレクトリ
```text
apps/
  backend/
    app/
      api/
      core/
      db/
      models/
      repositories/
      services/
      llm/
      skills/
      workers/
      schemas/
      tests/
```

## 2. 主要 API（研究 run 中心）
### Health
- `GET /health`

### Users（簡易）
- `POST /api/users`
- `GET /api/users/{user_id}`
- `GET /api/users/{user_id}/skills`（Aのみ有効、B/C は空 or 404 でもよいが仕様を固定する）

### Runs / Experiments
- `POST /api/runs/start`
- `POST /api/runs/finish`
- `GET /api/runs/{run_id}`
- `GET /api/experiments/export.csv`
- `GET /api/experiments/export.jsonl`（任意だが推奨）

### Materials（教材）
- `POST /api/materials/next`
- `POST /api/materials/read_confirm`

### Assessments（テスト）
- `POST /api/assessments/pre/start`
- `POST /api/assessments/pre/submit`
- `POST /api/assessments/mini/start`
- `POST /api/assessments/mini/submit`
- `POST /api/assessments/post/start`
- `POST /api/assessments/post/submit`

### Mastery
- `POST /api/mastery/estimate`

### Chat（教材閲覧中のみ許可）
- `POST /api/chat/ask`
- `GET /api/chat/logs/{run_id}`（任意）

### Admin（再計算/履歴）
- `POST /api/admin/skills/recompute/{user_id}`（Aのみ）
- `GET /api/admin/skills/history/{user_id}`（Aのみ）

## 3. `POST /api/runs/start`
目的: A/B/C 条件を確定し、Pre-test を開始できる状態を作る。

request example:
```json
{
  "user_id": "u_001",
  "group": "A",
  "cycle_count": 3
}
```

response example:
```json
{
  "run_id": "run_xxx",
  "user_id": "u_001",
  "group": "A",
  "skills_enabled": true,
  "cycle_count": 3,
  "created_at": "2026-05-09T12:00:00Z"
}
```

ルール:
- `cycle_count` は MVP では 3 固定でもよいが、ログに保存する
- `skills_enabled` は `group == "A"` のときのみ true

## 4. `POST /api/materials/next`
目的: cycle の現在地に応じて次教材を提示する（A/Bは生成、Cは固定取得）。

request example:
```json
{
  "run_id": "run_xxx",
  "cycle_index": 1
}
```

response example:
```json
{
  "material_id": "mat_xxx",
  "run_id": "run_xxx",
  "cycle_index": 1,
  "group": "A",
  "content_text": "...",
  "difficulty": "medium",
  "learning_objectives": ["..."],
  "created_at": "2026-05-09T12:10:00Z"
}
```

ルール:
- 時間制限は設けない
- `content_text` は教材本文（テキスト）

## 5. `POST /api/materials/read_confirm`
目的: 読了ボタン押下を記録し、教材閲覧の所要時間を確定する。

request example:
```json
{
  "run_id": "run_xxx",
  "material_id": "mat_xxx",
  "presented_at": "2026-05-09T12:10:00Z",
  "read_confirmed_at": "2026-05-09T12:20:00Z"
}
```

response example:
```json
{
  "material_read_id": "mr_xxx",
  "duration_seconds": 600
}
```

ルール:
- 読了判定はボタンのみ
- 最低閲覧時間の制約は設けない
- `duration_seconds` は必須ログ

## 6. `POST /api/assessments/*/start` と `submit`
目的: Pre/Mini/Post の開始時刻と提出時刻を保存し、所要時間を残す（時間制限なし）。

### start response example
```json
{
  "assessment_attempt_id": "aa_xxx",
  "assessment_id": "asmt_xxx",
  "assessment_type": "mini_test",
  "cycle_index": 1,
  "started_at": "2026-05-09T12:21:00Z"
}
```

### submit request example（MCQ）
```json
{
  "assessment_attempt_id": "aa_xxx",
  "submitted_at": "2026-05-09T12:25:00Z",
  "answers": [
    {"question_id": "q1", "choice_index": 2},
    {"question_id": "q2", "choice_index": 0}
  ]
}
```

### submit response example
```json
{
  "assessment_attempt_id": "aa_xxx",
  "submitted_at": "2026-05-09T12:25:00Z",
  "duration_seconds": 240,
  "score": 1,
  "max_score": 2,
  "per_question_correct": [
    {"question_id": "q1", "is_correct": true},
    {"question_id": "q2", "is_correct": false}
  ]
}
```

## 7. `POST /api/chat/ask`（教材閲覧中のみ）
目的: 教材についての質問に回答する（読解支援）。A/Bのみ。

request example:
```json
{
  "run_id": "run_xxx",
  "material_id": "mat_xxx",
  "question_text": "この段落の要点は？"
}
```

response example:
```json
{
  "chat_turn_id": "ct_xxx",
  "answer_text": "...",
  "created_at": "2026-05-09T12:15:00Z"
}
```

ルール:
- API は「教材閲覧中」状態以外では 409 などで拒否する
- A は `skill_profile` を入力に含めてよい
- B は `skill_profile` を入力に含めない（参照/更新もしない）

## 8. JSON Schema（MVP）
### 8.1 Skill profile JSON（Aのみ）
```json
{
  "mastery": 0.55,
  "known_topics": ["..."],
  "weak_topics": ["..."],
  "common_mistakes": ["..."],
  "recommended_difficulty": "medium",
  "version": 3,
  "updated_at": "2026-05-09T12:30:00Z"
}
```

### 8.2 Material generation schema（A/B）
```json
{
  "title": "string",
  "difficulty": "easy|medium|hard",
  "learning_objectives": ["string"],
  "content_text": "string"
}
```

### 8.3 MCQ assessment schema（pre/mini/post 共通）
```json
{
  "questions": [
    {
      "question_id": "string",
      "stem": "string",
      "choices": ["string"],
      "correct_choice_index": 0
    }
  ]
}
```

### 8.4 Mastery estimate schema
```json
{
  "mastery_estimate": 0.0,
  "confidence": 0.0,
  "evidence_summary": "string",
  "next_difficulty_recommendation": "easy|medium|hard"
}
```

## 9. 推奨テーブル（研究 run 仕様）
### users
- id
- display_name (optional)
- created_at

### runs
- id
- user_id
- group (A|B|C)
- skills_enabled (bool)
- cycle_count (int, MVP=3)
- created_at
- finished_at

### materials
- id
- run_id
- cycle_index (1..cycle_count)
- source_type (generated|fixed)
- content_text
- difficulty
- created_at

### material_reads
- id
- run_id
- material_id
- presented_at
- read_confirmed_at
- duration_seconds

### assessments
- id
- run_id
- assessment_type (pre_test|mini_test|post_test)
- cycle_index (mini only)
- content_json (questions/choices/correct)
- created_at

### assessment_attempts
- id
- run_id
- assessment_id
- assessment_type
- cycle_index (mini only)
- started_at
- submitted_at
- duration_seconds
- answers_json
- score
- max_score

### mastery_estimates
- id
- run_id
- cycle_index (mini only, or include pre/post estimate if needed)
- estimate_json
- created_at

### chat_turns（A/Bのみ）
- id
- run_id
- material_id
- question_text
- answer_text
- created_at

### skills（Aのみ）
- id
- user_id
- active_revision_id
- created_at
- updated_at

### skill_revisions（Aのみ）
- id
- skill_id
- revision
- profile_json
- update_reason
- created_at

## 10. 実装上の注意（研究の再現性）
- A/B/C 全てで「教材閲覧時間」「テスト所要時間」を必須ログにする
- 時間制限は設けない（強制終了・タイムアウト採点はしない）
- provider/model/prompt_version/temperature など再現性メタデータは run と生成物（教材/テスト/回答）に保存する
