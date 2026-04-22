# 03 API / DB / JSON Schema

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
      rag/
      skills/
      workers/
      schemas/
      tests/
```

## 2. 主要 API
### Health
- `GET /health`

### Users
- `POST /api/users`
- `GET /api/users/{user_id}`
- `GET /api/users/{user_id}/skills`

### Documents / Ingestion
- `POST /api/documents/upload`
- `POST /api/documents/ingest`
- `GET /api/documents`
- `GET /api/documents/{document_id}/chunks`

### Chat
- `POST /api/chat/generate`
- `POST /api/chat/select`
- `GET /api/chat/logs/{user_id}`
- `GET /api/chat/turns/{turn_id}`

### Experiments
- `POST /api/experiments/runs`
- `GET /api/experiments/runs`
- `GET /api/experiments/runs/{run_id}`
- `GET /api/experiments/export.csv`

### Admin
- `POST /api/admin/skills/recompute/{user_id}`
- `GET /api/admin/skills/history/{user_id}`

## 3. `/api/chat/generate` request example
```json
{
  "user_id": "u_001",
  "question": "二次方程式の解き方を教えて",
  "course_context": "math",
  "candidate_count": 3,
  "skills_enabled": true,
  "conversation_id": "optional"
}
```

## 4. `/api/chat/generate` response example
```json
{
  "conversation_id": "conv_xxx",
  "turn_id": "turn_xxx",
  "skills_enabled": true,
  "retrievals": [
    {
      "chunk_id": "chunk_1",
      "document_id": "doc_1",
      "score": 0.88,
      "text": "..."
    }
  ],
  "candidates": [
    {
      "candidate_id": "cand_1",
      "title": "ヒント中心",
      "style_tags": ["hint-first", "stepwise"],
      "answer_text": "..."
    },
    {
      "candidate_id": "cand_2",
      "title": "例題中心",
      "style_tags": ["example-first"],
      "answer_text": "..."
    },
    {
      "candidate_id": "cand_3",
      "title": "簡潔説明",
      "style_tags": ["short", "direct"],
      "answer_text": "..."
    }
  ]
}
```

## 5. `/api/chat/select` request example
```json
{
  "user_id": "u_001",
  "turn_id": "turn_xxx",
  "selected_candidate_id": "cand_2",
  "satisfaction_score": 8,
  "clarity_score": 9,
  "comment": "例題がある方がわかりやすい"
}
```

## 6. 推奨テーブル
### users
- id
- display_name
- created_at

### conversations
- id
- user_id
- created_at

### turns
- id
- conversation_id
- user_id
- question_text
- skills_enabled
- created_at

### candidate_sets
- id
- turn_id
- model_name
- prompt_version
- created_at

### candidates
- id
- candidate_set_id
- rank
- title
- answer_text
- style_tags (jsonb)
- is_selected
- created_at

### feedback
- id
- turn_id
- selected_candidate_id
- satisfaction_score
- clarity_score
- comment
- created_at

### documents
- id
- filename
- mime_type
- source_type
- created_at

### chunks
- id
- document_id
- chunk_index
- content
- token_count
- embedding vector
- metadata jsonb

### turn_retrievals
- id
- turn_id
- chunk_id
- similarity_score

### skills
- id
- user_id
- active_revision_id
- created_at
- updated_at

### skill_revisions
- id
- skill_id
- revision
- profile_json
- update_reason
- created_at

### skill_update_jobs
- id
- user_id
- turn_id
- status
- error_message
- created_at
- updated_at

### experiment_runs
- id
- user_id
- turn_id
- condition_name
- skills_enabled
- created_at

## 7. Skill profile JSON
```json
{
  "preferred_explanation_style": ["hint-first", "socratic"],
  "preferred_structure_pattern": ["example-then-steps-then-check"],
  "preferred_hint_level": "medium",
  "preferred_answer_length": "medium",
  "disliked_patterns": ["too-abstract", "answer-only"],
  "evidence_preference": "cite-retrieved-context",
  "notes": ["likes worked examples"]
}
```

## 8. Candidate generation schema
LLM に期待する structured output:
```json
{
  "candidates": [
    {
      "title": "string",
      "style_tags": ["string"],
      "answer_text": "string",
      "rationale": "string"
    }
  ]
}
```

### ルール
- candidates 数は request の candidate_count と一致
- 候補ごとにスタイル差分を明確にする
- answer_text は learner-facing
- rationale は internal use

## 9. Skill delta schema
```json
{
  "add_preferences": {
    "preferred_explanation_style": ["hint-first"],
    "preferred_structure_pattern": ["example-then-steps-then-check"],
    "preferred_hint_level": "medium",
    "preferred_answer_length": "medium",
    "evidence_preference": "cite-retrieved-context"
  },
  "add_dislikes": ["too-abstract"],
  "summary_rule": "Use worked examples before formal explanation when possible."
}
```

## 10. SkillUpdater ロジック
### 入力
- previous skill
- chosen candidate
- rejected candidates
- user comment
- optional retrieval context

### 出力
- normalized delta
- merged next skill profile
- human-readable update_reason

### マージ方針
- enum 値は新しい evidence を優先
- list 値は重複除去して追記
- disliked_patterns は強い負例として扱う
- revision を +1 する

## 11. 実装上の注意
- `is_selected` は candidates にも持たせるが、正本は feedback.selected_candidate_id
- vector は pgvector の `vector(n)` を使う
- embedding 次元数は provider 実装に合わせて設定可能にする
- prompt_version, model_name, temperature など再現性に関わるメタデータを保存する
